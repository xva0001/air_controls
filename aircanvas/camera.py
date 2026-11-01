"""Camera abstraction and background capture stream.

The desktop shell uses :class:`OpenCVCamera`; the browser supplies frames over
a WebSocket instead.  Both paths feed the same :class:`InteractionSession`.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

log = logging.getLogger(__name__)

_BACKEND_ENV = "AIRCANVAS_CAMERA_BACKEND"


@dataclass
class CameraAttempt:
    backend: str
    index: int
    opened: bool = False
    delivered_frame: bool = False
    error: str = ""
    elapsed_ms: float = 0.0
    backend_name: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "backend": self.backend,
            "index": self.index,
            "opened": self.opened,
            "delivered_frame": self.delivered_frame,
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "backend_name": self.backend_name,
        }


@dataclass
class CameraInfo:
    status: str = "idle"  # idle | starting | live | error | stopped
    message: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    index: int = 0
    backend: str = ""
    attempts: list[CameraAttempt] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "message": self.message,
            "width": self.width,
            "height": self.height,
            "fps": round(self.fps, 1),
            "index": self.index,
            "backend": self.backend,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
        }


def _backend_value(name: str) -> int | None:
    return {
        "msmf": getattr(cv2, "CAP_MSMF", None),
        "dshow": getattr(cv2, "CAP_DSHOW", None),
        "any": cv2.CAP_ANY,
        "v4l2": getattr(cv2, "CAP_V4L2", None),
        "avfoundation": getattr(cv2, "CAP_AVFOUNDATION", None),
    }.get(name)


def camera_backend_candidates(
    preferred: str | None = None,
    *,
    platform: str | None = None,
) -> list[tuple[str, int]]:
    """Return backend attempts in priority order.

    On Windows OpenCV's DirectShow backend can be present yet unusable for
    cameras exposed only through Media Foundation (common on modern laptops
    and remote sessions).  MSMF is therefore tried first, then DSHOW, then the
    auto backend.  ``AIRCANVAS_CAMERA_BACKEND`` can force a single backend.
    """
    platform = platform or sys.platform
    preferred_name = (preferred or "").strip().lower()
    if preferred_name in ("", "auto"):
        preferred_name = (os.environ.get(_BACKEND_ENV) or "auto").strip().lower()
    forced = preferred_name or "auto"
    candidates: list[str]
    if platform.startswith("win"):
        candidates = ["msmf", "dshow", "any"]
    elif platform == "darwin":
        candidates = ["avfoundation", "any"]
    else:
        candidates = ["v4l2", "any"]
    if forced not in ("", "auto"):
        if forced not in candidates and forced not in {"msmf", "dshow", "any", "v4l2", "avfoundation"}:
            log.warning("Unknown AIRCANVAS_CAMERA_BACKEND=%s; using auto", forced)
        else:
            candidates = [forced]
    resolved: list[tuple[str, int]] = []
    for name in candidates:
        value = _backend_value(name)
        if value is not None:
            resolved.append((name.upper(), int(value)))
    if not resolved:
        resolved.append(("ANY", cv2.CAP_ANY))
    return resolved


class OpenCVCamera:
    def __init__(
        self,
        index: int = 0,
        width: int = 1280,
        height: int = 720,
        *,
        backend: str | None = None,
        on_status: Callable[[CameraInfo], None] | None = None,
    ) -> None:
        self.index = index
        self.width = width
        self.height = height
        self.backend = backend
        self.on_status = on_status
        self.info = CameraInfo(index=index)
        self._capture: cv2.VideoCapture | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._latest: np.ndarray | None = None
        self._sequence = 0
        self._last_frame_at = 0.0
        self._fps = 0.0

    def _set_status(self, status: str, message: str = "") -> None:
        self.info.status = status
        self.info.message = message
        self.info.index = self.index
        if self.on_status:
            try:
                self.on_status(self.info)
            except Exception:
                log.exception("Camera status callback failed")

    def open(self) -> bool:
        self._stop.clear()
        self.info.attempts = []
        self._set_status("starting", "Opening camera...")
        candidates = camera_backend_candidates(self.backend)
        capture: cv2.VideoCapture | None = None
        first_frame: np.ndarray | None = None
        chosen_backend = ""
        for name, api in candidates:
            started = time.perf_counter()
            attempt = CameraAttempt(backend=name, index=self.index)
            candidate: cv2.VideoCapture | None = None
            try:
                # Do not pass CAP_PROP_OPEN_TIMEOUT_MSEC/READ_TIMEOUT to MSMF:
                # OpenCV 5.0's MSMF backend rejects property 53 during
                # openFinalize on some devices.  Open with the backend only and
                # validate by reading a real frame instead.
                candidate = cv2.VideoCapture(self.index, api)
                attempt.opened = bool(candidate is not None and candidate.isOpened())
                if not attempt.opened:
                    attempt.error = "backend did not open the device"
                    if candidate is not None:
                        candidate.release()
                    continue
                try:
                    attempt.backend_name = str(candidate.getBackendName())
                except Exception:
                    attempt.backend_name = name
                candidate.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                candidate.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                candidate.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                # Validate that a real frame arrives. Some backends report
                # isOpened() and then never deliver a frame.
                for _ in range(6):
                    ok, frame = candidate.read()
                    if ok and frame is not None and getattr(frame, "size", 0):
                        first_frame = frame
                        break
                    time.sleep(0.05)
                attempt.delivered_frame = first_frame is not None
                if first_frame is None:
                    attempt.error = "opened but delivered no frame"
                    candidate.release()
                    continue
                capture = candidate
                chosen_backend = name
                attempt.error = ""
                break
            except Exception as exc:
                attempt.error = f"{type(exc).__name__}: {exc}"
                if candidate is not None:
                    try:
                        candidate.release()
                    except Exception:
                        pass
            finally:
                attempt.elapsed_ms = (time.perf_counter() - started) * 1000
                self.info.attempts.append(attempt)

        if capture is None or first_frame is None:
            tried = ", ".join(attempt.backend for attempt in self.info.attempts)
            log.warning(
                "Could not open camera index %s. Attempts: %s",
                self.index,
                [attempt.to_dict() for attempt in self.info.attempts],
            )
            message = (
                f"No camera opened at index {self.index} (tried {tried}). "
                "This session may not expose a webcam. Check Windows Settings > Privacy & security > Camera, "
                "close other camera apps, or use the simulated feed. "
                "For backend details run: python scripts/diagnose_camera.py"
            )
            self._set_status("error", message)
            self.info.backend = ""
            return False
        actual_w = int(first_frame.shape[1])
        actual_h = int(first_frame.shape[0])
        with self._lock:
            self._capture = capture
            self._latest = first_frame
            self._sequence = 1
            self.info.width = actual_w
            self.info.height = actual_h
            self.info.backend = chosen_backend
        try:
            backend_name = capture.getBackendName() if capture is not None else chosen_backend
        except Exception:
            backend_name = chosen_backend
        self._set_status("live", f"Camera live via {backend_name or chosen_backend} ({actual_w}×{actual_h})")
        self._thread = threading.Thread(target=self._run, name="aircanvas-camera", daemon=True)
        self._thread.start()
        return True

    def _run(self) -> None:
        fail_count = 0
        while not self._stop.is_set():
            with self._lock:
                capture = self._capture
            if capture is None:
                break
            ok, frame = capture.read()
            now = time.monotonic()
            if not ok or frame is None:
                fail_count += 1
                if fail_count == 8:
                    self._set_status("error", "Camera stopped returning frames")
                time.sleep(0.01)
                continue
            fail_count = 0
            with self._lock:
                self._latest = frame
                self._sequence += 1
                if self._last_frame_at:
                    dt = now - self._last_frame_at
                    if dt > 0:
                        instant = 1.0 / dt
                        self._fps = instant if self._fps == 0 else self._fps * 0.9 + instant * 0.1
                self._last_frame_at = now
                self.info.fps = self._fps

    def latest(self) -> tuple[np.ndarray | None, int]:
        with self._lock:
            return (None if self._latest is None else self._latest.copy(), self._sequence)

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)
        with self._lock:
            capture = self._capture
            self._capture = None
            self._latest = None
            self._thread = None
        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass
        if self.info.status != "error":
            self._set_status("stopped", "Camera stopped")

    @property
    def is_live(self) -> bool:
        return self.info.status == "live"


class CameraPipeline:
    """Continuously process the newest camera frame off the UI thread.

    Frames are dropped rather than queued when inference is slower than capture,
    keeping gesture feedback close to real time.
    """

    def __init__(
        self,
        session: Any,
        *,
        camera_index: int = 0,
        width: int = 1280,
        height: int = 720,
        backend: str | None = None,
    ) -> None:
        self.session = session
        self.camera = OpenCVCamera(
            index=camera_index,
            width=width,
            height=height,
            backend=backend,
            on_status=self._camera_status,
        )
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._rgb: np.ndarray | None = None
        self._snapshot: dict[str, Any] | None = None
        self._events: list[Any] = []
        self._sequence = 0
        self._last_camera_sequence = -1
        self._error = ""
        self._started_at = 0.0

    def _camera_status(self, info: CameraInfo) -> None:
        self.session.set_camera_status(
            info.status,
            info.message,
            source="opencv",
            width=info.width,
            height=info.height,
        )

    def start(self) -> bool:
        self._stop.clear()
        self._started_at = time.monotonic()
        if not self.camera.open():
            self.session.set_camera_status(
                "error",
                self.camera.info.message,
                source="opencv",
            )
            self._snapshot = self.session.snapshot()
            return False
        self._thread = threading.Thread(target=self._run, name="aircanvas-pipeline", daemon=True)
        self._thread.start()
        return True

    def _run(self) -> None:
        import cv2

        last_sequence = -1
        while not self._stop.is_set():
            frame, seq = self.camera.latest()
            if frame is None or seq == last_sequence:
                time.sleep(0.005)
                continue
            last_sequence = seq
            if self.session.config.mirror_camera:
                frame = cv2.flip(frame, 1)
            try:
                events = self.session.process_frame(frame)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            except Exception as exc:
                self._error = str(exc)
                log.exception("Pipeline processing failed")
                time.sleep(0.02)
                continue
            snapshot = self.session.snapshot()
            with self._lock:
                self._rgb = rgb
                self._snapshot = snapshot
                self._events.extend(events)
                self._sequence += 1
        with self._lock:
            self._rgb = None

    def poll(self) -> tuple[np.ndarray | None, dict[str, Any] | None, list[Any], int]:
        with self._lock:
            events = list(self._events)
            self._events.clear()
            rgb = None if self._rgb is None else self._rgb.copy()
            return rgb, self._snapshot, events, self._sequence

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.camera.stop()
        self._thread = None
        self.session.set_camera_status("stopped", "Camera stopped", source="opencv")

    @property
    def error(self) -> str:
        return self._error

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())


def list_cameras(max_devices: int = 4) -> list[int]:
    """Probe camera indices without holding them open."""
    available: list[int] = []
    for index in range(max_devices):
        for _name, api in camera_backend_candidates():
            capture = None
            try:
                capture = cv2.VideoCapture(index, api)
                if capture is not None and capture.isOpened():
                    available.append(index)
                    break
            except Exception:
                pass
            finally:
                if capture is not None:
                    capture.release()
    return available


def diagnose_cameras(max_index: int = 4) -> dict[str, Any]:
    """Return detailed backend/index diagnostics without keeping a camera open.

    This is intentionally synchronous and verbose; it is used by
    ``scripts/diagnose_camera.py`` when the normal open path fails.
    """
    results: list[dict[str, Any]] = []
    for index in range(max_index + 1):
        for name, api in camera_backend_candidates():
            started = time.perf_counter()
            capture = None
            frame = None
            record: dict[str, Any] = {"index": index, "backend": name}
            try:
                capture = cv2.VideoCapture(index, api)
                record["opened"] = bool(capture is not None and capture.isOpened())
                if record["opened"]:
                    try:
                        record["backend_name"] = capture.getBackendName()
                    except Exception:
                        record["backend_name"] = name
                    record["width"] = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                    record["height"] = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                    ok, frame = capture.read()
                    record["frame"] = bool(ok and frame is not None)
                    if record["frame"]:
                        record["frame_size"] = [int(frame.shape[1]), int(frame.shape[0])]
                else:
                    record["error"] = "backend did not open the device"
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            finally:
                if capture is not None:
                    try:
                        capture.release()
                    except Exception:
                        pass
                record["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
            results.append(record)
    return {
        "opencv": cv2.__version__,
        "platform": sys.platform,
        "backends": camera_backend_candidates(),
        "results": results,
    }
