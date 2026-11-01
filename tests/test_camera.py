from __future__ import annotations

from aircanvas.camera import CameraAttempt, CameraInfo, camera_backend_candidates


def test_windows_backend_order_prefers_media_foundation():
    candidates = camera_backend_candidates(platform="win32")
    assert [name for name, _ in candidates][:3] == ["MSMF", "DSHOW", "ANY"]


def test_forced_backend_is_respected():
    candidates = camera_backend_candidates("dshow", platform="win32")
    assert [name for name, _ in candidates] == ["DSHOW"]


def test_unknown_backend_falls_back_to_auto():
    candidates = camera_backend_candidates("not-a-backend", platform="win32")
    assert len(candidates) >= 2


def test_environment_backend_override_works_when_ui_says_auto(monkeypatch):
    monkeypatch.setenv("AIRCANVAS_CAMERA_BACKEND", "dshow")
    candidates = camera_backend_candidates("auto", platform="win32")
    assert [name for name, _ in candidates] == ["DSHOW"]


def test_camera_info_serialises_attempts():
    info = CameraInfo(index=2, backend="MSMF")
    info.attempts.append(CameraAttempt(backend="MSMF", index=2, opened=True, delivered_frame=False))
    data = info.to_dict()
    assert data["index"] == 2
    assert data["attempts"][0]["backend"] == "MSMF"
    assert data["attempts"][0]["delivered_frame"] is False
