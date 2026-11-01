"""Hand landmark detection and rule-based static gesture recognition.

Only the *pose* layer lives here.  Mapping a pose to an application action is
the job of :mod:`aircanvas.mapping`; this separation makes gesture mappings
customisable without retraining or editing the recogniser.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from .config import GestureSettings, Pose
from .geometry import angle_at
from .models import FingerState, GestureReading, HandObservation
from .resources import ensure_matplotlib_cache, hand_model_path

def _fix_python315_lazy_futures() -> None:
    """Work around a Python 3.15/PySide6 lazy-import interaction.

    Python 3.15 uses lazy imports for ``concurrent.futures`` submodules.  In a
    process that has already initialized Qt, a lazy ``ThreadPoolExecutor``
    attribute can remain a ``lazy_import`` object; MediaPipe's serial dispatcher
    then raises ``TypeError: 'lazy_import' object is not callable``.  Resolve the
    concrete stdlib classes and pin them onto the module before MediaPipe starts.
    """
    import concurrent.futures as futures

    try:
        from concurrent.futures.thread import ThreadPoolExecutor

        if not isinstance(futures.ThreadPoolExecutor, type):
            futures.ThreadPoolExecutor = ThreadPoolExecutor
    except (ImportError, AttributeError):
        pass
    try:
        from concurrent.futures.process import ProcessPoolExecutor

        if not isinstance(futures.ProcessPoolExecutor, type):
            futures.ProcessPoolExecutor = ProcessPoolExecutor
    except (ImportError, AttributeError):
        pass


_fix_python315_lazy_futures()

# MediaPipe hand landmark indices.
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

HAND_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)


def _finger_extended(hand: HandObservation, mcp: int, pip: int, dip: int, tip: int) -> bool:
    joint_angle = angle_at(hand.point(mcp), hand.point(pip), hand.point(tip))
    # The distance-to-wrist check disambiguates a bent fingertip that happens
    # to point at the camera.
    return joint_angle >= 148.0 and hand.point(tip).distance(hand.wrist) > hand.point(pip).distance(hand.wrist) * 1.03


def _thumb_extended(hand: HandObservation) -> bool:
    angle_mcp = angle_at(hand.point(THUMB_CMC), hand.point(THUMB_MCP), hand.point(THUMB_TIP))
    angle_ip = angle_at(hand.point(THUMB_MCP), hand.point(THUMB_IP), hand.point(THUMB_TIP))
    reach = hand.thumb_tip.distance(hand.index_mcp) / hand.scale
    return angle_mcp >= 138.0 and angle_ip >= 142.0 and reach > 0.78


def detect_fingers(hand: HandObservation) -> FingerState:
    return FingerState(
        thumb=_thumb_extended(hand),
        index=_finger_extended(hand, INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP),
        middle=_finger_extended(hand, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP),
        ring=_finger_extended(hand, RING_MCP, RING_PIP, RING_DIP, RING_TIP),
        pinky=_finger_extended(hand, PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP),
    )


def classify_hand(hand: HandObservation, settings: GestureSettings | None = None) -> GestureReading:
    """Classify a single frame into one of the application's static poses."""
    settings = settings or GestureSettings()
    fingers = detect_fingers(hand)
    pinch_ratio = hand.thumb_tip.distance(hand.index_tip) / max(1e-6, hand.scale)
    # Higher sensitivity increases the tolerated thumb-index distance.  Require
    # an extended index finger so a closed fist with the thumb across the palm
    # is never mistaken for a pinch.
    pinch_threshold = 0.28 + 0.14 * float(settings.pinch_sensitivity)
    pinch = pinch_ratio < pinch_threshold and fingers.index

    count = fingers.count
    confidence = 0.55 + 0.35 * min(1.0, hand.score if hand.score > 0 else 0.85)

    if pinch:
        pose = Pose.PINCH
        # Stronger confidence the tighter the pinch.
        confidence = min(0.99, confidence + 0.08 * (1.0 - pinch_ratio / max(pinch_threshold, 1e-6)))
    elif count >= 4 and fingers.index and fingers.middle and fingers.ring:
        pose = Pose.OPEN_PALM
    elif fingers.index and fingers.middle and fingers.ring and not fingers.pinky:
        pose = Pose.THREE
    elif fingers.index and fingers.middle and not fingers.ring and not fingers.pinky:
        pose = Pose.PEACE
    elif fingers.index and not fingers.middle and not fingers.ring and not fingers.pinky:
        pose = Pose.POINT
    elif count <= 1:
        pose = Pose.FIST
    else:
        pose = Pose.UNKNOWN
        confidence = 0.45

    # A pose is less certain when the hand is near the frame edge / tiny.
    palm_area = hand.scale
    if palm_area < 0.045:
        confidence *= 0.85
    return GestureReading(
        raw=pose.value,
        stable=pose.value,
        confidence=round(confidence, 3),
        pinch_ratio=pinch_ratio,
        fingers=fingers,
        thumb_index_gap=round(hand.thumb_tip.distance(hand.index_tip), 4),
    )


class GestureStabilizer:
    """Majority-vote stability filter with a hold duration output.

    Directional navigation already has its own debouncing.  This layer removes
    the one-frame flicker that would otherwise start/stop a stroke or produce a
    burst of clicks when two poses are close together.
    """

    def __init__(self, window: int = 5) -> None:
        self.window = max(3, min(11, int(window)))
        self._history: deque[str] = deque(maxlen=self.window)
        self._stable = Pose.NONE.value
        self._stable_since = 0.0
        self._last_timestamp = 0.0
        self._missing_since: float | None = None
        self._lock = threading.Lock()

    def set_window(self, window: int) -> None:
        window = max(3, min(11, int(window)))
        if window != self.window:
            self.window = window
            self._history = deque(self._history, maxlen=window)

    def reset(self) -> None:
        with self._lock:
            self._history.clear()
            self._stable = Pose.NONE.value
            self._stable_since = 0.0
            self._missing_since = None

    def update(self, reading: GestureReading | None, now: float) -> GestureReading:
        with self._lock:
            self._last_timestamp = now
            if reading is None:
                if self._missing_since is None:
                    self._missing_since = now
                if now - self._missing_since > 0.18:
                    self._history.clear()
                    self._stable = Pose.NONE.value
                    self._stable_since = now
                held = max(0.0, now - self._stable_since)
                return GestureReading(
                    raw=Pose.NONE.value,
                    stable=Pose.NONE.value,
                    confidence=0.0,
                    held_s=held,
                )
            self._missing_since = None
            self._history.append(reading.raw)
            counts: dict[str, int] = {}
            for pose in self._history:
                counts[pose] = counts.get(pose, 0) + 1
            candidate, votes = max(counts.items(), key=lambda pair: pair[1])
            needed = max(2, math.ceil(self.window * 0.6))
            if votes >= needed and candidate != self._stable:
                self._stable = candidate
                self._stable_since = now
            held = max(0.0, now - self._stable_since)
            return GestureReading(
                raw=reading.raw,
                stable=self._stable,
                confidence=reading.confidence,
                held_s=held,
                pinch_ratio=reading.pinch_ratio,
                fingers=reading.fingers,
                thumb_index_gap=reading.thumb_index_gap,
            )


class HandTracker:
    """MediaPipe Tasks wrapper with lazy model initialisation.

    The class is thread-confined: create one instance per processing worker /
    browser session.  Initialisation is explicit so the UI can show a useful
    "model missing" error instead of crashing at import time.
    """

    def __init__(
        self,
        model_path: str | None = None,
        *,
        min_detection_confidence: float = 0.55,
        min_presence_confidence: float = 0.55,
        min_tracking_confidence: float = 0.55,
        num_hands: int = 2,
    ) -> None:
        self.model_path = str(model_path or hand_model_path())
        self._landmarker = None
        self._lock = threading.Lock()
        self._last_timestamp_ms = -1
        self._min_detection = min_detection_confidence
        self._min_presence = min_presence_confidence
        self._min_tracking = min_tracking_confidence
        self._num_hands = num_hands

    @property
    def ready(self) -> bool:
        return self._landmarker is not None

    def initialize(self) -> None:
        if self._landmarker is not None:
            return
        ensure_matplotlib_cache()
        from mediapipe.tasks.python.core.base_options import BaseOptions
        from mediapipe.tasks.python.vision import hand_landmarker
        from mediapipe.tasks.python.vision.core.vision_task_running_mode import (
            VisionTaskRunningMode,
        )

        if not Path(self.model_path).exists():
            raise FileNotFoundError(
                f"MediaPipe hand model not found at {self.model_path}. "
                "Run scripts/fetch_model.py or set AIRCANVAS_HAND_MODEL."
            )
        options = hand_landmarker.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=self.model_path),
            running_mode=VisionTaskRunningMode.VIDEO,
            num_hands=self._num_hands,
            min_hand_detection_confidence=self._min_detection,
            min_hand_presence_confidence=self._min_presence,
            min_tracking_confidence=self._min_tracking,
        )
        self._landmarker = hand_landmarker.HandLandmarker.create_from_options(options)

    def detect(
        self,
        frame_bgr: np.ndarray,
        now: float | None = None,
        dominant_hand: str = "auto",
    ) -> HandObservation | None:
        """Detect the most relevant hand in a BGR frame.

        ``now`` is a monotonically increasing wall-clock value in seconds.  The
        caller should mirror the frame *before* calling this method when the
        preview is mirrored, so landmarks and displayed pixels share an origin.
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return None
        with self._lock:
            self.initialize()
            import cv2
            import mediapipe as mp

            timestamp_ms = int((time.time() if now is None else now) * 1000)
            if timestamp_ms <= self._last_timestamp_ms:
                timestamp_ms = self._last_timestamp_ms + 1
            self._last_timestamp_ms = timestamp_ms
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            rgb = np.ascontiguousarray(rgb)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self._landmarker.detect_for_video(image, timestamp_ms)

        if not result.hand_landmarks:
            return None
        candidates: list[HandObservation] = []
        for index, landmark_list in enumerate(result.hand_landmarks):
            score = 1.0
            label = "Unknown"
            if index < len(result.handedness) and result.handedness[index]:
                category = result.handedness[index][0]
                score = float(category.score or 0.0)
                label = str(category.category_name or "Unknown")
            # Use the real Point class for useful helpers.
            from .geometry import Point

            observation = HandObservation(
                landmarks=[Point(float(lm.x), float(lm.y)) for lm in landmark_list],
                handedness=label,
                score=score,
                timestamp=time.time() if now is None else now,
                tracking_id=int(index),
            )
            candidates.append(observation)
        if not candidates:
            return None
        preferred = (dominant_hand or "auto").lower()
        if preferred in ("left", "right"):
            matching = [c for c in candidates if c.handedness.lower() == preferred]
            if matching:
                candidates = matching
        # Prefer a well-framed hand over a tiny/partial hand.
        def rank(hand: HandObservation) -> float:
            cx, cy = hand.palm_center.x, hand.palm_center.y
            centrality = 1.0 - min(1.0, math.hypot(cx - 0.5, cy - 0.5))
            return hand.score * 0.55 + centrality * 0.25 + min(0.2, hand.scale * 2.0)

        return max(candidates, key=rank)

    def close(self) -> None:
        with self._lock:
            if self._landmarker is not None:
                try:
                    self._landmarker.close()
                finally:
                    self._landmarker = None

    def __enter__(self) -> HandTracker:
        self.initialize()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def landmark_list_to_observation(landmarks: Sequence[Sequence[float]], handedness: str = "Right") -> HandObservation:
    """Build an observation from an iterable of 21 x/y pairs (tests/demo)."""
    from .geometry import Point

    if len(landmarks) != 21:
        raise ValueError("A hand observation needs exactly 21 landmarks")
    return HandObservation([Point(float(p[0]), float(p[1])) for p in landmarks], handedness=handedness, score=0.95)
