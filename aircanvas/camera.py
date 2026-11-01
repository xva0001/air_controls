"""Camera abstraction and background capture stream.

The desktop shell uses :class:`OpenCVCamera`; the browser supplies frames over
a WebSocket instead.  Both paths feed the same :class:`InteractionSession`.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

log = logging.getLogger(__name__)


@dataclass
class CameraInfo:
    status: str = "idle"  # idle | starting | live | error | stopped
    message: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    index: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "message": self.message,
            "width": self.width,
            "height": self.height,
            "fps": round(self.fps, 1),
            "index": self.index,
        }


class OpenCVCamera:
    def __init__(
        self,
        index: int = 0,
        width: int = 1280,
        height: int = 720,
        *,
        on_status: Callable[[CameraInfo], None] | None = None,
    ) -> None:
        self.index = index
        self.width = width
        self.height = height
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
        self._set_status("starting", "Opening camera...")
        backend = cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else cv2.CAP_ANY
        capture = None
        for api in (backend, cv2.CAP_ANY):
            try:
                capture = cv2.VideoCapture(self.index, api)
                if capture is not None and capture.isOpened():
                    break
                if capture is not None:
                    capture.release()
            except Exception:
                capture = None
        if capture is None or not capture.isOpened():
            self._set_status(
                "error",
                f"No camera found at index {self.index}. Check privacy settings or start the simulated feed.",
            )
            return False
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        actual_w = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or self.width)
        actual_h = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or self.height)
        with self._lock:
            self._capture = capture
            self.info.width = actual_w
            self.info.height = actual_h
        self._set_status("live", "Camera live")
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

    def __init__(self, session: Any, *, camera_index: int = 0, width: int = 1280, height: int = 720) -> None:
        self.session = session
        self.camera = OpenCVCamera(
            index=camera_index,
            width=width,
            height=height,
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
        capture = None
        try:
            capture = cv2.VideoCapture(index, cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else cv2.CAP_ANY)
            if capture is not None and capture.isOpened():
                available.append(index)
        except Exception:
            pass
        finally:
            if capture is not None:
                capture.release()
    return available
