"""Tests for selectable hand landmark backends and configuration."""

from __future__ import annotations

import numpy as np

from aircanvas.config import AppConfig
from aircanvas.geometry import Point
from aircanvas.hand_models import (
    HandLandmarkBackend,
    MediaPipeBackend,
    RTMPoseHandBackend,
    YOLOPoseBackend,
    backend_catalog,
    backend_status,
)
from aircanvas.models import HandObservation
from aircanvas.session import InteractionSession


def test_hand_backend_config_validation() -> None:
    cfg = AppConfig(hand_backend="not-a-model", hand_device="tpu", hand_model_path="  model.onnx ")
    cfg.validate()
    assert cfg.hand_backend == "mediapipe"
    assert cfg.hand_device == "auto"
    assert cfg.hand_model_path == "model.onnx"


def test_backend_catalog_and_mediapipe_default() -> None:
    statuses = backend_catalog(AppConfig())
    keys = [status.key for status in statuses]
    assert keys == ["mediapipe", "rtmpose", "yolo_pose"]
    assert backend_status(AppConfig()).key == "mediapipe"
    assert MediaPipeBackend.probe().available is True


def test_optional_backends_report_actionable_reasons(monkeypatch) -> None:
    monkeypatch.setattr("aircanvas.hand_models._module_available", lambda _name: False)
    rtm = RTMPoseHandBackend.probe()
    yolo = YOLOPoseBackend.probe("")
    assert rtm.available is False
    assert "rtmlib" in rtm.reason
    assert "rtmlib" in rtm.requires
    assert yolo.available is False
    assert "ultralytics" in yolo.reason
    assert "21-keypoint" in yolo.note


class _FakeBackend(HandLandmarkBackend):
    key = "fake"
    label = "Fake"

    def __init__(self) -> None:
        self.initialized = False
        self.closed = False

    def status(self):
        from aircanvas.hand_models import BackendStatus

        return BackendStatus(self.key, self.label, True)

    def initialize(self) -> None:
        self.initialized = True

    def detect(self, frame_bgr, now=None, dominant_hand="auto"):
        return HandObservation(
            landmarks=[Point(0.5, 0.5) for _ in range(21)],
            handedness="Right",
            score=0.9,
            timestamp=now or 0.0,
        )

    def close(self) -> None:
        self.closed = True


def test_session_uses_injected_hand_backend() -> None:
    fake = _FakeBackend()
    session = InteractionSession(hand_tracker=fake)
    try:
        observation = session._detect(np.zeros((16, 16, 3), dtype=np.uint8), 2.0)
        assert observation is not None
        assert fake.initialized is True
        assert len(observation.landmarks) == 21
        assert session.snapshot()["status"]["hand_backend"]["key"] == "fake"
    finally:
        session.close()
    assert fake.closed is True
