"""Pluggable hand-landmark backends.

AirCanvas needs a single contract: given a BGR frame, return up to two
``HandObservation`` objects with 21 normalised landmarks.  MediaPipe is the
bundled default.  RTMPose-Hand and YOLO Pose are optional adapters for users who
already have (or train) a 21-keypoint hand model.

The adapters are deliberately lazy: importing this module does not import
``rtmlib`` or ``ultralytics``, so the default MediaPipe path stays lightweight.
"""

from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .config import AppConfig
from .geometry import Point
from .models import HandObservation
from .resources import hand_model_path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackendStatus:
    key: str
    label: str
    available: bool
    reason: str = ""
    requires: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "available": self.available,
            "reason": self.reason,
            "requires": self.requires,
            "note": self.note,
        }


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _path_ok(value: str) -> bool:
    if not value:
        return False
    return value.startswith(("http://", "https://", "hf://")) or Path(value).exists()


def _normalise_keypoints(
    keypoints: np.ndarray,
    scores: np.ndarray | None,
    width: int,
    height: int,
) -> list[HandObservation]:
    """Convert pixel keypoints from a third-party model to HandObservation."""
    points = np.asarray(keypoints, dtype=np.float32)
    if points.ndim == 2:
        points = points[None, ...]
    if points.ndim != 3 or points.shape[1] != 21:
        raise ValueError(
            f"Hand model returned keypoint shape {tuple(points.shape)}; AirCanvas needs 21 hand keypoints."
        )
    if scores is None:
        score_array = np.ones(points.shape[:2], dtype=np.float32)
    else:
        score_array = np.asarray(scores, dtype=np.float32)
        if score_array.ndim == 1:
            score_array = score_array[None, ...]
        if score_array.shape[:2] != points.shape[:2]:
            score_array = np.ones(points.shape[:2], dtype=np.float32)
    observations: list[HandObservation] = []
    for index in range(points.shape[0]):
        hand_points = points[index]
        hand_scores = score_array[index]
        confidence = float(np.nanmean(hand_scores)) if hand_scores.size else 0.5
        if not np.isfinite(confidence) or confidence < 0.15:
            continue
        normalized = [
            Point(
                float(np.clip(x / max(1, width), 0.0, 1.0)),
                float(np.clip(y / max(1, height), 0.0, 1.0)),
            )
            for x, y in hand_points
        ]
        if not all(np.isfinite([p.x, p.y]).all() for p in normalized):
            continue
        observations.append(
            HandObservation(
                landmarks=normalized,
                handedness="Unknown",
                score=confidence,
                tracking_id=index,
            )
        )
    return observations


def _best(observations: list[HandObservation], dominant_hand: str) -> HandObservation | None:
    if not observations:
        return None
    preferred = (dominant_hand or "auto").lower()
    if preferred in ("left", "right"):
        labelled = [hand for hand in observations if hand.handedness.lower() == preferred]
        if labelled:
            observations = labelled
    return max(observations, key=lambda hand: hand.score)


class HandLandmarkBackend:
    """Interface implemented by all hand landmark providers."""

    key = "base"
    label = "Hand model"

    def status(self) -> BackendStatus:
        return BackendStatus(self.key, self.label, available=False, reason="Not implemented")

    def initialize(self) -> None:
        raise NotImplementedError

    def detect(
        self,
        frame_bgr: np.ndarray,
        now: float | None = None,
        dominant_hand: str = "auto",
    ) -> HandObservation | None:
        raise NotImplementedError

    def close(self) -> None:
        pass


class MediaPipeBackend(HandLandmarkBackend):
    key = "mediapipe"
    label = "MediaPipe Hands"

    def __init__(self, model_path: str | None = None, *, tracker: Any | None = None) -> None:
        self.model_path = str(model_path or hand_model_path())
        self._tracker = tracker

    @classmethod
    def probe(cls, model_path: str | None = None) -> BackendStatus:
        path = Path(model_path) if model_path else hand_model_path()
        if not _module_available("mediapipe"):
            return BackendStatus(
                cls.key,
                cls.label,
                False,
                "mediapipe is not installed",
                "pip install mediapipe",
                "Bundled 21-keypoint model; CPU-friendly Tasks API.",
            )
        if not path.exists():
            return BackendStatus(
                cls.key,
                cls.label,
                False,
                f"model not found: {path}",
                "python scripts/fetch_model.py",
                "Bundled 21-keypoint model; CPU-friendly Tasks API.",
            )
        return BackendStatus(
            cls.key,
            cls.label,
            True,
            "",
            "mediapipe",
            "Bundled 21-keypoint model; CPU-friendly Tasks API.",
        )

    def status(self) -> BackendStatus:
        return self.probe(self.model_path)

    def initialize(self) -> None:
        if self._tracker is None:
            from .gestures import HandTracker

            self._tracker = HandTracker(self.model_path)
        self._tracker.initialize()

    def detect(self, frame_bgr, now=None, dominant_hand="auto"):
        if self._tracker is None:
            self.initialize()
        return self._tracker.detect(frame_bgr, now, dominant_hand)

    def close(self) -> None:
        if self._tracker is not None:
            self._tracker.close()
            self._tracker = None


class RTMPoseHandBackend(HandLandmarkBackend):
    """RTMPose-Hand through rtmlib (RTMDet hand detector + RTMPose hand).

    RTMPose-m/l **body** models do not output 21 hand landmarks.  This adapter
    targets the RTMPose-Hand model family, which is the model rtmlib's ``Hand``
    solution uses.  The default rtmlib hand ONNX bundle is downloaded on first
    use; a local .onnx/.zip path or URL can be supplied instead.
    """

    key = "rtmpose"
    label = "RTMPose-Hand"

    def __init__(
        self,
        model_path: str = "",
        detector_path: str = "",
        device: str = "auto",
    ) -> None:
        self.model_path = model_path.strip()
        self.detector_path = detector_path.strip()
        self.device = device
        self._hand: Any = None

    @classmethod
    def probe(cls, model_path: str = "", detector_path: str = "", device: str = "auto") -> BackendStatus:
        note = (
            "Top-down RTMPose-Hand (21 keypoints) with RTMDet hand detector. "
            "RTMPose-m/l body models are not valid hand landmark models."
        )
        if not _module_available("rtmlib"):
            return BackendStatus(
                cls.key,
                cls.label,
                False,
                "rtmlib is not installed",
                "pip install rtmlib onnxruntime",
                note,
            )
        if model_path and not _path_ok(model_path):
            return BackendStatus(cls.key, cls.label, False, f"pose model not found: {model_path}", "", note)
        if detector_path and not _path_ok(detector_path):
            return BackendStatus(cls.key, cls.label, False, f"detector model not found: {detector_path}", "", note)
        return BackendStatus(
            cls.key,
            cls.label,
            True,
            "",
            "rtmlib + onnxruntime",
            note,
        )

    def status(self) -> BackendStatus:
        return self.probe(self.model_path, self.detector_path, self.device)

    def initialize(self) -> None:
        if self._hand is not None:
            return
        try:
            from rtmlib import Hand
        except ImportError as exc:
            raise RuntimeError(
                "RTMPose backend needs rtmlib. Install with: pip install rtmlib onnxruntime"
            ) from exc
        kwargs: dict[str, Any] = {
            "to_openpose": False,
            "backend": "onnxruntime" if _module_available("onnxruntime") else "opencv",
            "device": "cpu" if self.device in ("", "auto") else self.device,
        }
        if self.model_path:
            kwargs["pose"] = self.model_path
        if self.detector_path:
            kwargs["det"] = self.detector_path
        self._hand = Hand(**kwargs)

    def detect(self, frame_bgr, now=None, dominant_hand="auto"):
        if self._hand is None:
            self.initialize()
        try:
            keypoints, scores = self._hand(frame_bgr)
        except Exception as exc:
            raise RuntimeError(f"RTMPose-Hand inference failed: {exc}") from exc
        if keypoints is None or len(keypoints) == 0:
            return None
        height, width = frame_bgr.shape[:2]
        observations = _normalise_keypoints(np.asarray(keypoints), np.asarray(scores), width, height)
        for observation in observations:
            observation.timestamp = 0.0 if now is None else now
        return _best(observations, dominant_hand)

    def close(self) -> None:
        self._hand = None


class YOLOPoseBackend(HandLandmarkBackend):
    """YOLOv8/v11 Pose adapter for a custom **21-keypoint hand** model.

    Stock ``yolov8*-pose.pt`` / ``yolo11*-pose.pt`` models produce 17 COCO body
    keypoints and cannot drive AirCanvas.  Train a model on a 21-keypoint hand
    pose dataset (for example the Ultralytics hand-keypoints dataset) and point
    ``hand_model_path`` at those weights.
    """

    key = "yolo_pose"
    label = "YOLO Pose (21-kp)"

    def __init__(self, model_path: str = "", device: str = "auto") -> None:
        self.model_path = model_path.strip()
        self.device = device
        self._model: Any = None

    @classmethod
    def probe(cls, model_path: str = "", device: str = "auto") -> BackendStatus:
        note = (
            "Requires a custom 21-keypoint hand pose .pt. Stock YOLOv8/v11-pose "
            "weights have 17 body keypoints and are rejected."
        )
        if not _module_available("ultralytics"):
            return BackendStatus(
                cls.key,
                cls.label,
                False,
                "ultralytics is not installed",
                "pip install ultralytics",
                note,
            )
        if not model_path:
            return BackendStatus(cls.key, cls.label, False, "choose a 21-keypoint .pt model", "", note)
        if not Path(model_path).exists():
            return BackendStatus(cls.key, cls.label, False, f"model not found: {model_path}", "", note)
        return BackendStatus(cls.key, cls.label, True, "", "ultralytics", note)

    def status(self) -> BackendStatus:
        return self.probe(self.model_path, self.device)

    def initialize(self) -> None:
        if self._model is not None:
            return
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "YOLO Pose backend needs ultralytics. Install with: pip install ultralytics"
            ) from exc
        if not self.model_path or not Path(self.model_path).exists():
            raise FileNotFoundError("Choose a 21-keypoint YOLO Pose .pt model")
        self._model = YOLO(self.model_path)
        task = getattr(self._model, "task", "")
        if task and task != "pose":
            raise ValueError(f"YOLO model task is {task!r}, expected 'pose'")
        kpt_shape = None
        try:
            kpt_shape = self._model.model.yaml.get("kpt_shape")
        except Exception:
            kpt_shape = None
        if kpt_shape and int(kpt_shape[0]) != 21:
            raise ValueError(
                f"YOLO model has {int(kpt_shape[0])} keypoints, but AirCanvas needs 21 hand keypoints. "
                "Stock YOLOv8/v11-pose models have 17 COCO body keypoints; train a hand-keypoints model."
            )

    def detect(self, frame_bgr, now=None, dominant_hand="auto"):
        if self._model is None:
            self.initialize()
        kwargs: dict[str, Any] = {"source": frame_bgr, "verbose": False, "conf": 0.25}
        if self.device not in ("", "auto"):
            kwargs["device"] = self.device
        results = self._model.predict(**kwargs)
        observations: list[HandObservation] = []
        height, width = frame_bgr.shape[:2]
        for result in results:
            keypoints = getattr(result, "keypoints", None)
            if keypoints is None or keypoints.xy is None or len(keypoints.xy) == 0:
                continue
            xy = keypoints.xy
            if hasattr(xy, "cpu"):
                xy = xy.cpu().numpy()
            xy = np.asarray(xy)
            confidence = None
            if getattr(keypoints, "conf", None) is not None:
                confidence = keypoints.conf
                if hasattr(confidence, "cpu"):
                    confidence = confidence.cpu().numpy()
                confidence = np.asarray(confidence)
            observations.extend(_normalise_keypoints(xy, confidence, width, height))
        for observation in observations:
            observation.timestamp = 0.0 if now is None else now
        return _best(observations, dominant_hand)

    def close(self) -> None:
        self._model = None


def backend_catalog(config: AppConfig | None = None) -> list[BackendStatus]:
    config = config or AppConfig()
    model_path = config.hand_model_path
    statuses = [
        MediaPipeBackend.probe(model_path if config.hand_backend == "mediapipe" else ""),
        RTMPoseHandBackend.probe(
            model_path if config.hand_backend == "rtmpose" else "",
            config.hand_detector_path,
            config.hand_device,
        ),
        YOLOPoseBackend.probe(model_path if config.hand_backend == "yolo_pose" else "", config.hand_device),
    ]
    return statuses


def create_hand_backend(config: AppConfig) -> HandLandmarkBackend:
    if config.hand_backend == "rtmpose":
        return RTMPoseHandBackend(config.hand_model_path, config.hand_detector_path, config.hand_device)
    if config.hand_backend == "yolo_pose":
        return YOLOPoseBackend(config.hand_model_path, config.hand_device)
    return MediaPipeBackend(config.hand_model_path or None)


def backend_status(config: AppConfig) -> BackendStatus:
    if config.hand_backend == "rtmpose":
        return RTMPoseHandBackend.probe(config.hand_model_path, config.hand_detector_path, config.hand_device)
    if config.hand_backend == "yolo_pose":
        return YOLOPoseBackend.probe(config.hand_model_path, config.hand_device)
    return MediaPipeBackend.probe(config.hand_model_path or None)
