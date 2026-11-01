"""Shared interaction session.

One instance owns all state for one user workspace: mode/tool selection, hand
recognition, gesture mapping, drawing engines, loop selection, object tracking,
navigation and virtual-mouse state.  Both the PySide6 app and every FastAPI
browser connection instantiate this exact class.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from .config import (
    BRUSH_COLORS,
    AppConfig,
    MirrorTool,
    Mode,
    Pose,
    Tool,
)
from .drawing import DrawCommit, DrawingEngine
from .geometry import Point
from .gestures import GestureStabilizer, classify_hand
from .hand_models import (
    HandLandmarkBackend,
    MediaPipeBackend,
    backend_catalog,
    backend_status,
    create_hand_backend,
)
from .mapping import (
    GestureMapper,
    MouseController,
    NavEvent,
    NavigationController,
)
from .models import (
    GESTURE_LABELS,
    GestureReading,
    HandObservation,
    NavTelemetry,
    PointerState,
    SelectionTelemetry,
    UiEvent,
)
from .shapes import LoopSelectionDetector, SelectionUpdate
from .smoothing import PointerSmoother
from .tracking import ObjectTrackerManager

log = logging.getLogger(__name__)

_AUTO = object()


@dataclass
class SessionStats:
    fps: float = 0.0
    recognition_ms: float = 0.0
    frames: int = 0
    dropped: int = 0
    last_frame_s: float = 0.0


class InteractionSession:
    def __init__(
        self,
        config: AppConfig | None = None,
        *,
        hand_tracker: Any | None = None,
        tracker_manager: ObjectTrackerManager | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self.config = (config or AppConfig()).clone().validate()
        self.screen_drawing = DrawingEngine(auto_shapes=self.config.auto_shapes)
        self.mirror_drawing = DrawingEngine(auto_shapes=self.config.auto_shapes)
        self.gesture_stabilizer = GestureStabilizer(self.config.gesture.stability_frames)
        self.mapper = GestureMapper(self.config.gesture)
        self.navigation = NavigationController(self.config.gesture)
        self.mouse = MouseController(self.config.gesture)
        self.tracker = tracker_manager or ObjectTrackerManager()
        self.selection_detector = LoopSelectionDetector(
            hold_seconds=self.config.gesture.selection_hold_ms / 1000.0
        )
        self._pointer_smoother = PointerSmoother(self.config.gesture.cursor_smoothing)
        if hand_tracker is None:
            self._hand_tracker: HandLandmarkBackend | None = None
        elif isinstance(hand_tracker, HandLandmarkBackend):
            self._hand_tracker = hand_tracker
        else:
            # Backwards-compatible support for an injected HandTracker (tests/tools).
            self._hand_tracker = MediaPipeBackend(tracker=hand_tracker)
        self._backend_fail_key: tuple[Any, ...] | None = None
        self._backend_retry_at = 0.0
        self._recognition_error = ""

        self._hand: HandObservation | None = None
        self._gesture = GestureReading()
        self._pointer = PointerState()
        self._nav = NavTelemetry()
        self._selection = SelectionTelemetry()
        self._events: deque[UiEvent] = deque(maxlen=60)
        self._pending_events: list[UiEvent] = []
        self._event_counter = 0
        self._stroke_target: DrawingEngine | None = None
        self._selection_cooldown_until = 0.0
        self._selection_requires_release = False
        self._last_pinch = False
        self._previous_statuses: dict[int, str] = {}
        self._stats = SessionStats()
        self._last_process_s: float | None = None
        self._camera = {
            "status": "idle",
            "message": "Camera not started",
            "source": "none",
            "demo": False,
            "width": 0,
            "height": 0,
        }
        self._toast: dict[str, Any] | None = None
        self._toast_until = 0.0
        self._status_message = "Ready"
        self._frame_size = (0, 0)
        self._paused = False

    # ------------------------------------------------------------------ config
    @property
    def mode(self) -> str:
        return self.config.mode

    @property
    def drawing(self) -> DrawingEngine:
        return self.mirror_drawing if self.mode == Mode.MIRROR.value else self.screen_drawing

    @property
    def active_tool(self) -> str:
        return self.config.mirror_tool if self.mode == Mode.MIRROR.value else self.config.tool

    @property
    def paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool) -> None:
        with self._lock:
            self._paused = bool(paused)
            if self._paused:
                self._finish_stroke(0.0)
                self._release_mouse()
                self.navigation.reset()
            self._status_message = "Paused" if self._paused else "Ready"

    def set_mode(self, mode: str) -> None:
        if mode not in (Mode.SCREEN.value, Mode.MIRROR.value):
            return
        with self._lock:
            if mode == self.config.mode:
                return
            self._finish_stroke(time.monotonic())
            self._release_mouse()
            self._selection_detector_reset()
            self.navigation.reset()
            self.mouse.reset()
            self.config.mode = mode
            self._pointer_smoother.reset()
            self._pointer.visible = False
            self._status_message = "Screen mode" if mode == Mode.SCREEN.value else "Mirror mode"

    def set_tool(self, tool: str) -> None:
        with self._lock:
            if self.mode == Mode.SCREEN.value:
                if tool not in (Tool.DRAW.value, Tool.NAVIGATE.value, Tool.MOUSE.value):
                    return
                if tool == self.config.tool:
                    return
                self._finish_stroke(time.monotonic())
                self._release_mouse()
                self.navigation.reset()
                self.config.tool = tool
                self._status_message = {
                    Tool.DRAW.value: "Draw on the canvas",
                    Tool.NAVIGATE.value: "Navigate with deliberate swipes",
                    Tool.MOUSE.value: "Move the on-screen cursor",
                }[tool]
            else:
                if tool not in (MirrorTool.ANNOTATE.value, MirrorTool.TRACK.value):
                    return
                if tool == self.config.mirror_tool:
                    return
                self._finish_stroke(time.monotonic())
                self._selection_detector_reset()
                self.config.mirror_tool = tool
                self._status_message = "Annotate the feed" if tool == MirrorTool.ANNOTATE.value else "Circle an object to track it"
            self._pointer_smoother.reset()

    def set_brush(self, color: str | None = None, width: float | None = None) -> None:
        with self._lock:
            if color and color in BRUSH_COLORS:
                self.config.brush_color = color
            if width is not None:
                self.config.brush_width = max(1.0, min(24.0, float(width)))
            self.screen_drawing.style(self.config.brush_color, self.config.brush_width)
            self.mirror_drawing.style(self.config.brush_color, self.config.brush_width)

    def apply_config(self, patch: Mapping[str, Any] | AppConfig) -> AppConfig:
        with self._lock:
            old = self.config
            if isinstance(patch, AppConfig):
                new = patch.clone().validate()
            else:
                new = old.clone()
                new.apply_patch(patch)
            new.validate()
            mode_changed = new.mode != old.mode
            tool_changed = new.tool != old.tool
            mirror_tool_changed = new.mirror_tool != old.mirror_tool
            backend_changed = (
                new.hand_backend != old.hand_backend
                or new.hand_model_path != old.hand_model_path
                or new.hand_detector_path != old.hand_detector_path
                or new.hand_device != old.hand_device
            )
            if mode_changed or tool_changed or mirror_tool_changed:
                self._finish_stroke(time.monotonic())
                self._release_mouse()
                self.navigation.reset()
                self.mouse.reset()
                self._selection_detector_reset()
                self._pointer_smoother.reset()
                self._pointer.visible = False
            self.config = new
            self.gesture_stabilizer.set_window(new.gesture.stability_frames)
            self.mapper.update(new.gesture)
            self.navigation.update_settings(new.gesture)
            self.mouse.update_settings(new.gesture)
            self.screen_drawing.auto_shapes = new.auto_shapes
            self.mirror_drawing.auto_shapes = new.auto_shapes
            self.screen_drawing.style(new.brush_color, new.brush_width)
            self.mirror_drawing.style(new.brush_color, new.brush_width)
            self._pointer_smoother = PointerSmoother(new.gesture.cursor_smoothing)
            if backend_changed:
                self._reset_hand_backend()
            return self.config

    def _reset_hand_backend(self) -> None:
        if self._hand_tracker is not None:
            try:
                self._hand_tracker.close()
            except Exception:
                log.debug("Hand backend close failed", exc_info=True)
        self._hand_tracker = None
        self._backend_fail_key = None
        self._backend_retry_at = 0.0
        self._recognition_error = ""
        status = backend_status(self.config)
        if not status.available:
            self._recognition_error = status.reason
            self.set_toast(f"Hand model unavailable: {status.reason}", "error", 4.5)

    # ------------------------------------------------------------------ status
    def set_camera_status(
        self,
        status: str,
        message: str = "",
        *,
        source: str = "opencv",
        demo: bool = False,
        width: int = 0,
        height: int = 0,
    ) -> None:
        with self._lock:
            self._camera = {
                "status": status,
                "message": message,
                "source": source,
                "demo": demo,
                "width": int(width),
                "height": int(height),
            }
            self._status_message = message or status.title()
            if width and height:
                self._frame_size = (int(width), int(height))

    def set_toast(self, message: str, tone: str = "info", ttl: float = 3.0) -> None:
        with self._lock:
            self._toast = {"message": message, "tone": tone}
            self._toast_until = time.monotonic() + ttl

    # ------------------------------------------------------------------ events
    def _emit(self, kind: str, **data: Any) -> UiEvent:
        self._event_counter += 1
        event = UiEvent(kind=kind, data=data, at=time.time(), id=self._event_counter)
        self._events.append(event)
        self._pending_events.append(event)
        return event

    def drain_events(self) -> list[UiEvent]:
        with self._lock:
            events = list(self._pending_events)
            self._pending_events.clear()
            return events

    def _recent_events(self, count: int = 24) -> list[dict[str, Any]]:
        return [event.to_dict() for event in list(self._events)[-count:]]

    # ------------------------------------------------------------------ actions
    def undo(self) -> bool:
        with self._lock:
            ok = self.drawing.undo()
            if ok:
                self._emit("undo", message="Undid last stroke")
                self.set_toast("Stroke undone", "info", 1.6)
            return ok

    def redo(self) -> bool:
        with self._lock:
            ok = self.drawing.redo()
            if ok:
                self._emit("redo", message="Redid stroke")
                self.set_toast("Stroke restored", "info", 1.6)
            return ok

    def clear(self) -> bool:
        with self._lock:
            ok = self.drawing.clear()
            if ok:
                self._emit("cleared", message="Canvas cleared")
                self.set_toast("Canvas cleared - Undo still available", "info", 2.2)
            return ok

    def remove_track(self, object_id: int | None = None) -> bool:
        with self._lock:
            ok = self.tracker.remove(object_id)
            if ok:
                self._emit("track_removed", object_id=object_id)
                self.set_toast("Tracking marker removed", "info", 1.8)
            return ok

    def clear_tracks(self) -> bool:
        with self._lock:
            if self.tracker.count == 0:
                return False
            self.tracker.clear()
            self._previous_statuses.clear()
            self._emit("track_removed", object_id=None)
            self.set_toast("All tracking markers removed", "info", 1.8)
            return True

    def _finish_stroke(self, now: float) -> DrawCommit | None:
        target = self._stroke_target or self.drawing
        self._stroke_target = None
        commit = target.end()
        self._pointer.pressed = False
        if commit is not None and commit.corrected:
            self._emit(
                "shape_corrected",
                shape=commit.shape,
                confidence=round(commit.confidence, 2),
                stroke_id=commit.stroke_id,
            )
            self.set_toast(f"Circle recognised and corrected ({int(commit.confidence * 100)}%)", "success", 2.1)
        return commit

    def _release_mouse(self) -> None:
        now = time.monotonic()
        for event in self.mouse.release(now):
            self._emit_mouse_event(event)
        self._pointer.pressed = False

    def _emit_mouse_event(self, event: dict[str, Any]) -> None:
        kind = str(event.get("kind", "mouse"))
        payload = {key: value for key, value in event.items() if key not in ("kind", "at")}
        self._emit(kind, **payload)

    def _selection_detector_reset(self) -> None:
        self.selection_detector.reset()
        self.selection_detector.hold_seconds = self.config.gesture.selection_hold_ms / 1000.0
        self._selection = SelectionTelemetry()

    # ------------------------------------------------------------------ process
    def process_frame(
        self,
        frame_bgr: np.ndarray | None,
        now: float | None = None,
        *,
        observation: Any = _AUTO,
    ) -> list[UiEvent]:
        now = time.monotonic() if now is None else float(now)
        with self._lock:
            if frame_bgr is not None and getattr(frame_bgr, "size", 0):
                height, width = frame_bgr.shape[:2]
                self._frame_size = (int(width), int(height))
            self._update_fps(now)
            if self._paused:
                self._pointer.visible = False
                return []
            recognition_ms = 0.0
            if observation is _AUTO:
                started = time.perf_counter()
                observation = self._detect(frame_bgr, now)
                recognition_ms = (time.perf_counter() - started) * 1000.0
            self._stats.recognition_ms = (
                recognition_ms
                if recognition_ms
                else self._stats.recognition_ms * 0.9
            )
            hand = observation if isinstance(observation, HandObservation) else None
            self._hand = hand
            if hand is None:
                self._gesture = self.gesture_stabilizer.update(None, now)
                self._finish_stroke(now)
                self._release_mouse()
                self._pointer_smoother.reset()
                self._last_pinch = False
                self.navigation.update(Pose.NONE.value, Point(0.5, 0.5), now, enabled=False)
                self._nav = NavTelemetry(hint="Show your hand to begin")
                self._pointer.visible = False
                self._pointer.pressed = False
                if self.mode == Mode.MIRROR.value and self.selection_detector.points:
                    self._selection = SelectionTelemetry(hint="Hand lost - loop cancelled")
                    self.selection_detector.reset()
            else:
                raw = classify_hand(hand, self.config.gesture)
                self._gesture = self.gesture_stabilizer.update(raw, now)
                raw_pointer = self.mapper.pointer(hand, self._gesture)
                smoothed_pointer = self._pointer_smoother.filter(raw_pointer, now)
                self._pointer_smoother_active = True
                if self.mode == Mode.SCREEN.value:
                    self._handle_screen_mode(hand, smoothed_pointer, now)
                else:
                    self._handle_mirror_mode(hand, smoothed_pointer, frame_bgr, now)

            # Tracking runs on every mirror-mode frame, even with no hand.
            if self.mode == Mode.MIRROR.value and frame_bgr is not None and getattr(frame_bgr, "size", 0):
                markers = self.tracker.update(frame_bgr, now)
                self._watch_tracking_transitions(markers)
            self._pointer_hand_visibility(hand)
            self._stats.frames += 1
            self._stats.last_frame_s = now
            if self._toast is not None and now > self._toast_until:
                self._toast = None
            return self.drain_events_internal()

    def drain_events_internal(self) -> list[UiEvent]:
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def _detect(self, frame_bgr: np.ndarray | None, now: float) -> HandObservation | None:
        if frame_bgr is None or not getattr(frame_bgr, "size", 0):
            return None
        key = (
            self.config.hand_backend,
            self.config.hand_model_path,
            self.config.hand_detector_path,
            self.config.hand_device,
        )
        if self._backend_fail_key == key and now < self._backend_retry_at:
            return None
        try:
            if self._hand_tracker is None:
                status = backend_status(self.config)
                if not status.available:
                    raise RuntimeError(status.reason or f"{status.label} is unavailable")
                self._hand_tracker = create_hand_backend(self.config)
            self._hand_tracker.initialize()
            self._recognition_error = ""
            self._backend_fail_key = None
            return self._hand_tracker.detect(frame_bgr, now, self.config.gesture.dominant_hand)
        except Exception as exc:  # keep the UI alive, surface a useful message
            self._recognition_error = str(exc)
            self._backend_fail_key = key
            self._backend_retry_at = now + 5.0
            if not self._camera["message"] or "hand" not in self._camera["message"].lower():
                self.set_toast(f"Hand model unavailable: {exc}", "error", 4.5)
            log.exception("Hand detection failed (backend=%s)", self.config.hand_backend)
            return None

    # ------------------------------------------------------------------ screen
    def _handle_screen_mode(self, hand: HandObservation, raw_pointer: Point, now: float) -> None:
        pointer = self.mapper.viewport(raw_pointer)
        tool = self.config.tool
        self._pointer.point = pointer
        self._pointer.visible = True
        self._pointer.label = ""
        if tool == Tool.DRAW.value:
            self._handle_drawing_pose(pointer, now, space="screen")
            self._pointer.kind = "pen" if self._pointer.pressed else "crosshair"
            self._pointer.label = "Draw" if self._pointer.pressed else "Point to draw"
        elif tool == Tool.MOUSE.value:
            self._finish_stroke(now)
            self.navigation.reset()
            update = self.mouse.update(self._gesture, pointer, now, enabled=True)
            for event in update.events:
                self._emit_mouse_event(event)
                if event["kind"] == "mouse_left_down":
                    self._emit("click", button="left", x=pointer.x, y=pointer.y)
                elif event["kind"] == "mouse_right_click":
                    self._emit("click", button="right", x=pointer.x, y=pointer.y)
            self._pointer.pressed = update.pressed
            self._pointer.kind = "mouse"
            self._pointer.label = "Left click / drag: pinch" if not update.pressed else "Dragging"
            self._nav = NavTelemetry(hint="Move your hand to position the cursor")
        else:
            self._finish_stroke(now)
            self._release_mouse()
            nav_event, telemetry = self.navigation.update(
                self._gesture.stable,
                self.mapper.viewport(self.mapper.nav_pointer(hand)),
                now,
                enabled=True,
            )
            self._nav = telemetry
            self._pointer.kind = "navigate"
            self._pointer.point = self.mapper.viewport(self.mapper.nav_pointer(hand))
            self._pointer.visible = True
            self._pointer.label = telemetry.hint
            if nav_event is not None:
                self._handle_nav_event(nav_event)

    def _handle_nav_event(self, event: NavEvent) -> None:
        self._emit(
            "navigation",
            action=event.action,
            label=event.label,
            direction=event.direction,
            pose=event.pose,
        )
        self.set_toast(event.label, "success", 1.5)
        self._status_message = event.label

    # ------------------------------------------------------------------ mirror
    def _handle_mirror_mode(
        self,
        hand: HandObservation,
        raw_pointer: Point,
        frame: np.ndarray | None,
        now: float,
    ) -> None:
        self._pointer.point = raw_pointer
        self._pointer.visible = True
        tool = self.config.mirror_tool
        if tool == MirrorTool.ANNOTATE.value:
            self._handle_drawing_pose(raw_pointer, now, space="mirror")
            self._pointer.kind = "pen" if self._pointer.pressed else "crosshair"
            self._pointer.label = "Annotate the feed" if self._pointer.pressed else "Point to annotate"
            return

        # Track tool: draw a loop, hold briefly, acquire.
        self._finish_stroke(now)
        self._pointer.kind = "selector"
        self._pointer.label = "Circle an object with your fingertip"
        pinch = self._gesture.stable == self.config.gesture.click_pose
        if pinch and not self._last_pinch:
            removed = self.tracker.remove_at(raw_pointer)
            if removed is not None:
                self._emit("track_removed", object_id=removed)
                self.set_toast(f"Tracking marker {removed} removed", "info", 1.8)
        self._last_pinch = pinch

        draw_pose = self.config.gesture.draw_pose
        if self._gesture.stable == draw_pose and now >= self._selection_cooldown_until:
            if self._selection_requires_release:
                self._selection = SelectionTelemetry(
                    active=False,
                    hint="Release the pointing pose to select another object",
                    status="idle",
                )
            else:
                update = self.selection_detector.add(raw_pointer, now)
                self._selection = SelectionTelemetry(
                    active=True,
                    points=update.points,
                    progress=update.progress,
                    hint=update.hint,
                    status=update.status,
                )
                complete = self.selection_detector.maybe_complete(now)
                if complete is not None:
                    self._complete_selection(complete, frame, now)
        else:
            if self.selection_detector.points:
                finished = self.selection_detector.finish(now)
                if finished is not None:
                    self._selection = SelectionTelemetry(
                        active=False,
                        points=[],
                        progress=finished.progress,
                        hint=finished.hint,
                        status=finished.status,
                    )
                    if finished.status == "acquired":
                        self._complete_selection(finished, frame, now)
                    elif finished.status == "rejected":
                        self.set_toast(finished.hint, "warning", 1.8)
            self._selection = SelectionTelemetry(
                active=False,
                hint="Circle an object with your fingertip",
                status="idle",
            )
            self._selection_requires_release = False

        if frame is None or not getattr(frame, "size", 0):
            self._pointer.label = "Camera frame unavailable"

    def _complete_selection(self, update: SelectionUpdate, frame: np.ndarray | None, now: float) -> None:
        if update.bbox is None or frame is None or not getattr(frame, "size", 0):
            self.selection_detector.reset()
            self.set_toast("Could not initialise tracking - no frame", "error", 2.2)
            return
        try:
            tracker = self.tracker.add_from_region(frame, update.bbox, now=now)
        except Exception as exc:
            self.selection_detector.reset()
            self.set_toast(f"Tracking could not start: {exc}", "warning", 2.5)
            self._selection = SelectionTelemetry(hint="Object too small - draw a larger loop", status="rejected")
            return
        self._emit("track_added", object_id=tracker.id, bbox=tracker.bbox.as_list())
        self.set_toast(f"{tracker.label} locked - tracking", "success", 2.0)
        self._selection = SelectionTelemetry(
            active=False,
            points=[],
            progress=1.0,
            hint=f"{tracker.label} locked",
            status="acquired",
        )
        self.selection_detector.reset()
        self._selection_cooldown_until = now + 1.0
        self._selection_requires_release = True
        self._pointer.label = f"Tracking {tracker.label}"

    def _watch_tracking_transitions(self, markers: Iterable[dict[str, Any]]) -> None:
        seen: set[int] = set()
        for marker in markers:
            object_id = int(marker["id"])
            seen.add(object_id)
            status = str(marker["status"])
            previous = self._previous_statuses.get(object_id)
            if previous == status:
                continue
            self._previous_statuses[object_id] = status
            if status == "occluded":
                self._emit("track_occluded", object_id=object_id, label=marker["label"])
                self.set_toast(f"{marker['label']} briefly occluded - searching", "warning", 1.8)
            elif status == "lost":
                self._emit("track_lost", object_id=object_id, reason=marker.get("lost_reason", "lost"))
                self.set_toast(f"{marker['label']} lost - marker retained for review", "warning", 2.5)
            elif status == "out_of_view":
                self._emit("track_out_of_view", object_id=object_id, label=marker["label"])
                self.set_toast(f"{marker['label']} left the camera view - tracking stopped", "info", 2.5)
            elif status == "tracking" and previous in ("occluded", "reacquiring"):
                self._emit("track_recovered", object_id=object_id)
                self.set_toast(f"{marker['label']} re-acquired", "success", 1.6)
        for object_id in list(self._previous_statuses):
            if object_id not in seen:
                self._previous_statuses.pop(object_id, None)

    # ------------------------------------------------------------------ drawing
    def _handle_drawing_pose(self, point: Point, now: float, *, space: str) -> None:
        target = self.drawing if space == "screen" else self.mirror_drawing
        expected = self.config.gesture.draw_pose
        active_pose = self._gesture.stable == expected
        if active_pose:
            if target.current is None:
                target.begin(
                    point,
                    color=self.config.brush_color,
                    width=self.config.brush_width,
                    tool="pen",
                    now=now,
                )
                self._stroke_target = target
                self._pointer.pressed = True
            else:
                target.add(point)
        else:
            if target.current is not None:
                self._finish_stroke(now)
            self._pointer.pressed = False

    def _pointer_hand_visibility(self, hand: HandObservation | None) -> None:
        if hand is None:
            self._pointer.visible = False
            return
        if self.mode == Mode.SCREEN.value:
            self._pointer.visible = self.config.tool in (
                Tool.DRAW.value,
                Tool.MOUSE.value,
                Tool.NAVIGATE.value,
            )
        else:
            self._pointer.visible = True

    # ------------------------------------------------------------------ manual
    def manual_begin(self, point: Point, tool: str = "pen") -> bool:
        with self._lock:
            if self._paused:
                return False
            if self.mode == Mode.SCREEN.value and self.config.tool != Tool.DRAW.value:
                return False
            if self.mode == Mode.MIRROR.value and self.config.mirror_tool != MirrorTool.ANNOTATE.value:
                return False
            if self.drawing.current is not None:
                self.drawing.cancel()
            self.drawing.begin(
                point,
                color=self.config.brush_color,
                width=self.config.brush_width,
                tool=tool,
            )
            self._pointer.pressed = True
            return True

    def manual_add(self, point: Point) -> bool:
        with self._lock:
            if self._paused or self.drawing.current is None:
                return False
            return self.drawing.add(point)

    def manual_end(self) -> DrawCommit | None:
        with self._lock:
            commit = self.drawing.end()
            self._pointer.pressed = False
            if commit is not None and commit.corrected:
                self._emit(
                    "shape_corrected",
                    shape=commit.shape,
                    confidence=round(commit.confidence, 2),
                    stroke_id=commit.stroke_id,
                )
                self.set_toast("Circle corrected", "success", 1.8)
            return commit

    def manual_erase(self, point: Point, radius: float = 0.018) -> bool:
        with self._lock:
            return self.drawing.erase_at(point, radius)

    # ------------------------------------------------------------------ helpers
    def _update_fps(self, now: float) -> None:
        if self._last_process_s is not None:
            dt = now - self._last_process_s
            if 0 < dt < 2.0:
                instant = 1.0 / dt
                self._stats.fps = instant if self._stats.fps == 0 else self._stats.fps * 0.85 + instant * 0.15
        self._last_process_s = now

    def _tracking_summary(self) -> dict[str, Any]:
        markers = self.tracker.markers()
        active = sum(1 for marker in markers if marker["status"] in ("tracking", "occluded", "reacquiring"))
        return {
            "count": len(markers),
            "active": active,
            "occluded": sum(1 for marker in markers if marker["status"] == "occluded"),
            "lost": sum(1 for marker in markers if marker["status"] in ("lost", "out_of_view")),
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            drawing = self.drawing.snapshot()
            hand_dict = self._hand.to_dict(include_landmarks=self.config.show_landmarks) if self._hand else {
                "visible": False,
                "landmarks": [],
                "handedness": "None",
                "score": 0.0,
            }
            tracks = self.tracker.markers()
            selection = self.selection_detector.telemetry(active=self.selection_detector.is_drawing)
            if self._selection.status == "acquired" or self._selection.hint:
                # Prefer explicit selection feedback right after acquisition.
                if self._selection.status in ("acquired", "rejected"):
                    selection["hint"] = self._selection.hint
                    selection["status"] = self._selection.status
            active_tool = self.active_tool
            return {
                "version": "1.0",
                "timestamp": time.time(),
                "mode": self.config.mode,
                "tool": self.config.tool,
                "mirror_tool": self.config.mirror_tool,
                "active_tool": active_tool,
                "paused": self._paused,
                "config": self.config.to_dict(),
                "hand": hand_dict,
                "gesture": self._gesture.to_dict(),
                "pointer": self._pointer.to_dict(),
                "drawing": drawing.to_dict(),
                "tracks": tracks,
                "nav": self._nav.to_dict(),
                "selection": selection,
                "camera": dict(self._camera),
                "status": {
                    "message": self._status_message,
                    "recognition_error": self._recognition_error,
                    "hand_backend": (
                        self._hand_tracker.status().to_dict()
                        if self._hand_tracker is not None
                        else backend_status(self.config).to_dict()
                    ),
                    "hand_backends": [item.to_dict() for item in backend_catalog(self.config)],
                    "tracking": self._tracking_summary(),
                    "toast": self._toast,
                },
                "stats": {
                    "fps": round(self._stats.fps, 1),
                    "recognition_ms": round(self._stats.recognition_ms, 1),
                    "frames": self._stats.frames,
                    "width": self._frame_size[0],
                    "height": self._frame_size[1],
                },
                "events": self._recent_events(),
                "palette": BRUSH_COLORS,
                "gestures": GESTURE_LABELS,
                "stroke_counts": {
                    "screen": len(self.screen_drawing.strokes),
                    "mirror": len(self.mirror_drawing.strokes),
                },
            }

    def close(self) -> None:
        with self._lock:
            self._finish_stroke(time.monotonic())
            self._release_mouse()
            if self._hand_tracker is not None:
                self._hand_tracker.close()
            self._hand_tracker = None
            self._backend_fail_key = None
