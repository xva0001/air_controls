"""FastAPI backend for the browser interface.

The backend is deliberately thin: it serves the static UI, exchanges JPEG frames
and semantic state over one WebSocket, and delegates every interaction decision
to :class:`aircanvas.session.InteractionSession`.  No gesture, drawing, shape or
tracking logic is reimplemented here.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import json
import logging
import threading
import time
import webbrowser
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

import cv2
import numpy as np
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..config import AppConfig
from ..demo import DemoEngine
from ..resources import static_dir
from ..session import InteractionSession

log = logging.getLogger(__name__)

MAX_FRAME_BYTES = 2_500_000
MAX_MESSAGE_BYTES = 3_500_000
TARGET_DEMO_FPS = 15


FEATURES = {
    "browser_camera": True,
    "browser_drawing": True,
    "mirror_mode": True,
    "object_tracking": True,
    "transparent_desktop_overlay": False,
    "os_mouse_control": False,
    "os_navigation": False,
    "export_png": True,
    "keyboard_shortcuts": True,
    "local_only": True,
}


def _security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "connect-src 'self' ws: wss:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'self'"
    )
    return response


def _origin_allowed(origin: str | None) -> bool:
    if not origin:
        return True
    try:
        host = urlsplit(origin).hostname
    except ValueError:
        return False
    return host in ("localhost", "127.0.0.1", "::1")


def _decode_frame(data_url: str) -> np.ndarray | None:
    if not isinstance(data_url, str) or not data_url:
        return None
    payload = data_url.split(",", 1)[1] if data_url.startswith("data:") and "," in data_url else data_url
    if len(payload) > MAX_FRAME_BYTES * 1.4:
        raise ValueError("Frame is too large")
    try:
        raw = base64.b64decode(payload, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Frame is not valid base64") from exc
    if len(raw) > MAX_FRAME_BYTES:
        raise ValueError("Frame is too large")
    array = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if frame is None or frame.size == 0:
        raise ValueError("Frame could not be decoded")
    height, width = frame.shape[:2]
    if width < 160 or height < 120 or width > 1920 or height > 1080:
        raise ValueError("Unsupported frame dimensions")
    return frame


def _encode_demo_frame(frame: np.ndarray) -> str:
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
    if not ok:
        return ""
    encoded = base64.b64encode(buffer.tobytes()).decode("ascii")
    return "data:image/jpeg;base64," + encoded


class WebClient:
    def __init__(self, websocket: WebSocket, config: AppConfig) -> None:
        self.websocket = websocket
        self.session = InteractionSession(config)
        self.send_lock = asyncio.Lock()
        self.processing_lock = asyncio.Lock()
        self.sequence = 0
        self.closed = False
        self.demo_task: asyncio.Task | None = None
        self.demo_engine: DemoEngine | None = None
        self.demo_t0 = 0.0
        self.demo_started = 0.0
        self.demo_mode = self.session.mode
        self.camera_active = False
        self._last_state_sent = 0.0

    async def send(self, payload: dict[str, Any]) -> None:
        if self.closed:
            return
        async with self.send_lock:
            try:
                await self.websocket.send_text(json.dumps(payload, separators=(",", ":")))
            except Exception:
                self.closed = True

    async def send_state(self, frame_data: str | None = None, *, force: bool = False) -> None:
        if self.closed:
            return
        self.sequence += 1
        snapshot = self.session.snapshot()
        payload: dict[str, Any] = {
            "type": "state",
            "seq": self.sequence,
            "state": snapshot,
            "features": FEATURES,
        }
        if frame_data:
            payload["frame"] = frame_data
        await self.send(payload)

    async def handle_frame(self, frame: np.ndarray) -> None:
        if self.demo_task is not None:
            return
        async with self.processing_lock:
            if not self.camera_active:
                self.camera_active = True
                height, width = frame.shape[:2]
                self.session.set_camera_status(
                    "live",
                    "Browser camera live",
                    source="browser",
                    width=width,
                    height=height,
                )
            await asyncio.to_thread(self.session.process_frame, frame)
            await self.send_state()

    async def apply_config(self, patch: dict[str, Any]) -> None:
        patch = dict(patch or {})
        # Browser sessions cannot use OS-level control by design.
        patch["os_mouse"] = False
        patch["os_navigation"] = False
        self.session.apply_config(patch)

    async def start_demo(self, seek: float = 0.0) -> None:
        await self.stop_demo(notify=False)
        if self.camera_active:
            self.session.close()
            # Recreate the session so a browser->demo switch is clean.
            self.session = InteractionSession(self.session.config.clone())
            self.camera_active = False
        self.session.clear_tracks()
        self.demo_engine = DemoEngine(self.session)
        self.demo_engine.reset()
        self.demo_mode = self.session.mode
        seek = max(0.0, min(float(seek or 0.0), 20.0))
        if seek > 0:
            def pre_roll():
                frame = None
                for i in range(int(seek * 24)):
                    t = i / 24.0
                    frame = self.demo_engine.frame(t)
                    observation = self.demo_engine.observation(t)
                    self.session.process_frame(frame, t, observation=observation)
                return self.demo_engine.frame(seek)

            frame = await asyncio.to_thread(pre_roll)
            data = _encode_demo_frame(frame)
            self.session.set_camera_status(
                "demo", "Simulated camera feed", source="demo", demo=True, width=960, height=540
            )
            await self.send_state(data)
        else:
            self.session.set_camera_status(
                "demo", "Simulated camera feed", source="demo", demo=True, width=960, height=540
            )
            await self.send_state()
        self.demo_t0 = seek
        self.demo_started = time.monotonic()
        self.demo_task = asyncio.create_task(self._demo_loop(), name="aircanvas-web-demo")

    async def _demo_loop(self) -> None:
        interval = 1.0 / TARGET_DEMO_FPS
        next_tick = time.monotonic()
        while not self.closed:
            now = time.monotonic()
            if self.session.mode != self.demo_mode:
                self.demo_mode = self.session.mode
                self.demo_t0 = 0.0
                self.demo_started = now
                if self.demo_engine:
                    self.demo_engine.reset()
            t = self.demo_t0 + (now - self.demo_started)
            try:
                def tick(frame_t=t, frame_now=now):
                    engine = self.demo_engine
                    session = self.session
                    if engine is None:
                        raise RuntimeError("Demo engine was stopped")
                    frame = engine.frame(frame_t)
                    observation = engine.observation(frame_t)
                    events = session.process_frame(frame, frame_now, observation=observation)
                    return _encode_demo_frame(frame), session.snapshot(), events

                data, snapshot, _events = await asyncio.to_thread(tick)
                if self.demo_task is None or self.closed:
                    break
                # prepare payload inline for ordering
                self.sequence += 1
                payload = {
                    "type": "state",
                    "seq": self.sequence,
                    "state": snapshot,
                    "frame": data,
                    "features": FEATURES,
                }
                await self.send(payload)
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("Demo tick failed")
                await asyncio.sleep(0.12)
            next_tick += interval
            delay = next_tick - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            else:
                next_tick = time.monotonic()

    async def stop_demo(self, *, notify: bool = True) -> None:
        task = self.demo_task
        self.demo_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self.demo_engine = None
        if notify:
            if not self.camera_active and self.session.mode == "mirror":
                self.session.set_camera_status("stopped", "Simulated feed stopped", source="demo", demo=True)
            await self.send_state()

    async def cleanup(self) -> None:
        self.closed = True
        await self.stop_demo(notify=False)
        try:
            self.session.close()
        except Exception:
            pass


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info("AirCanvas web service starting")
        yield
        log.info("AirCanvas web service stopped")

    app = FastAPI(
        title="AirCanvas Web",
        version=__version__,
        description="Local browser interface backed by the shared AirCanvas Python core.",
        lifespan=lifespan,
    )
    assets = static_dir()
    if assets.exists():
        app.mount("/static", StaticFiles(directory=str(assets)), name="static")

    @app.middleware("http")
    async def add_headers(request: Request, call_next):
        response = await call_next(request)
        _security_headers(response)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "app": "AirCanvas",
            "version": __version__,
            "service": "web",
            "features": FEATURES,
            "browser_security": [
                "Camera access requires localhost or HTTPS and explicit browser permission.",
                "A browser cannot draw over other applications or move the operating-system cursor.",
                "Transparent desktop overlays and native navigation are desktop-only features.",
                "Frames are processed in memory by the local Python service and are not stored.",
            ],
        }

    @app.get("/api/config")
    async def default_config() -> dict[str, Any]:
        return AppConfig().to_dict()

    @app.get("/")
    async def index():
        path = assets / "index.html"
        if not path.exists():
            return JSONResponse({"error": "UI assets missing"}, status_code=500)
        return FileResponse(path, media_type="text/html", headers={"Cache-Control": "no-cache"})

    @app.get("/favicon.svg")
    async def favicon():
        path = assets / "favicon.svg"
        if not path.exists():
            return JSONResponse({}, status_code=404)
        return FileResponse(path, media_type="image/svg+xml")

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        if not _origin_allowed(websocket.headers.get("origin")):
            await websocket.close(code=1008, reason="Origin not allowed")
            return
        await websocket.accept()
        config = AppConfig()
        config.os_mouse = False
        config.os_navigation = False
        client = WebClient(websocket, config)
        try:
            await client.send(
                {
                    "type": "ready",
                    "version": __version__,
                    "config": client.session.config.to_dict(),
                    "features": FEATURES,
                    "limits": {
                        "max_frame_bytes": MAX_FRAME_BYTES,
                        "target_demo_fps": TARGET_DEMO_FPS,
                        "camera_processing": "browser -> local Python worker",
                    },
                }
            )
            await client.send_state()
            while True:
                try:
                    message = await websocket.receive_text()
                except WebSocketDisconnect:
                    break
                if len(message) > MAX_MESSAGE_BYTES:
                    await client.send({"type": "error", "message": "Message too large"})
                    continue
                try:
                    payload = json.loads(message)
                except ValueError:
                    await client.send({"type": "error", "message": "Malformed message"})
                    continue
                kind = payload.get("type")
                if kind == "hello":
                    patch = payload.get("config") or {}
                    if isinstance(patch, dict):
                        await client.apply_config(patch)
                    await client.send(
                        {
                            "type": "configured",
                            "config": client.session.config.to_dict(),
                            "features": FEATURES,
                        }
                    )
                    await client.send_state()
                elif kind == "config":
                    patch = payload.get("patch")
                    if isinstance(patch, dict):
                        await client.apply_config(patch)
                        await client.send_state()
                elif kind == "mode":
                    value = str(payload.get("value", "screen"))
                    if value in ("screen", "mirror"):
                        await client.apply_config({"mode": value})
                        await client.send_state()
                elif kind == "tool":
                    name = str(payload.get("value", "draw"))
                    if client.session.mode == "screen" and name in ("draw", "navigate", "mouse"):
                        await client.apply_config({"tool": name})
                    elif client.session.mode == "mirror" and name in ("annotate", "track"):
                        await client.apply_config({"mirror_tool": name})
                    await client.send_state()
                elif kind == "frame":
                    if client.demo_task is not None:
                        continue
                    try:
                        frame = _decode_frame(str(payload.get("image", "")))
                    except ValueError as exc:
                        await client.send({"type": "error", "message": str(exc)})
                        continue
                    if frame is not None:
                        await client.handle_frame(frame)
                elif kind == "camera_status":
                    status = str(payload.get("status", "error"))
                    if status not in ("live", "error", "stopped"):
                        status = "error"
                    client.session.set_camera_status(
                        status,
                        str(payload.get("message", "Browser camera state")),
                        source="browser",
                        width=int(payload.get("width", 0) or 0),
                        height=int(payload.get("height", 0) or 0),
                    )
                    client.camera_active = status == "live"
                    await client.send_state()
                elif kind == "demo":
                    enabled = bool(payload.get("enabled"))
                    if enabled:
                        await client.start_demo(float(payload.get("seek", 0.0) or 0.0))
                    else:
                        await client.stop_demo()
                elif kind == "pointer":
                    phase = str(payload.get("phase", ""))
                    try:
                        x = max(0.0, min(1.0, float(payload.get("x", 0.0))))
                        y = max(0.0, min(1.0, float(payload.get("y", 0.0))))
                    except (TypeError, ValueError):
                        continue
                    from ..geometry import Point

                    if phase == "start":
                        client.session.manual_begin(Point(x, y))
                    elif phase == "move":
                        client.session.manual_add(Point(x, y))
                    elif phase == "end":
                        client.session.manual_end()
                    await client.send_state()
                elif kind == "action":
                    action = str(payload.get("name", ""))
                    if action == "undo":
                        client.session.undo()
                    elif action == "redo":
                        client.session.redo()
                    elif action == "clear":
                        client.session.clear()
                    elif action == "clear_tracks":
                        client.session.clear_tracks()
                    elif action == "remove_track":
                        client.session.remove_track(int(payload.get("id", 0)))
                    elif action == "pause":
                        client.session.set_paused(bool(payload.get("value", True)))
                    elif action == "set_brush":
                        client.session.set_brush(
                            str(payload.get("color", client.session.config.brush_color)),
                            float(payload.get("width", client.session.config.brush_width)),
                        )
                    await client.send_state()
                elif kind == "request_state":
                    await client.send_state()
                elif kind == "ping":
                    await client.send({"type": "pong", "t": payload.get("t")})
        except WebSocketDisconnect:
            pass
        except Exception:
            log.exception("WebSocket session failed")
            try:
                await client.send({"type": "error", "message": "Session error"})
            except Exception:
                pass
        finally:
            await client.cleanup()

    return app


app = create_app()


def main() -> int:
    """Console entry point for the local web service."""
    import uvicorn

    parser = argparse.ArgumentParser(description="AirCanvas local web service")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: localhost only)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    parser.add_argument("--open", action="store_true", help="Open the interface in the default browser")
    parser.add_argument(
        "--log-level",
        default="info",
        choices=("critical", "error", "warning", "info", "debug", "trace"),
    )
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        logging.warning(
            "Binding to %s exposes the local camera service to the network. "
            "The service has no authentication and is intended for localhost use.",
            args.host,
        )
    url = f"http://{'127.0.0.1' if args.host == '0.0.0.0' else args.host}:{args.port}/"
    if args.open:
        threading.Thread(
            target=lambda: (time.sleep(1.0), webbrowser.open(url)),
            name="open-browser",
            daemon=True,
        ).start()
    print("AirCanvas Web")
    print(f"  Interface : {url}")
    print(f"  WebSocket : {url.replace('http', 'ws')}ws")
    print("  Scope     : local Python service + browser camera; no OS-level control")
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        ws_max_size=4 * 1024 * 1024,
        timeout_keep_alive=20,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
