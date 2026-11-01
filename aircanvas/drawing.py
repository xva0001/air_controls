"""Undoable vector drawing engine used by both UI implementations."""

from __future__ import annotations

import copy
import threading
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .geometry import Point, stroke_hits_point
from .shapes import ShapeResult, recognize_shape


@dataclass
class DrawCommit:
    stroke_id: str
    corrected: bool = False
    shape: str = "freehand"
    confidence: float = 0.0
    points: int = 0
    reason: str = ""


@dataclass
class DrawingSnapshot:
    strokes: list[dict[str, Any]] = field(default_factory=list)
    current: dict[str, Any] | None = None
    can_undo: bool = False
    can_redo: bool = False
    stroke_count: int = 0
    history_depth: int = 0
    auto_shapes: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "strokes": self.strokes,
            "current": self.current,
            "can_undo": self.can_undo,
            "can_redo": self.can_redo,
            "stroke_count": self.stroke_count,
            "history_depth": self.history_depth,
            "auto_shapes": self.auto_shapes,
        }


class DrawingEngine:
    """Normalised-coordinate stroke store with snapshot-based undo/redo.

    Snapshotting the (small) vector list is intentionally simple and reliable:
    every operation, including clear and eraser deletion, is reversible.  Live
    strokes are kept out of history until they are committed.
    """

    def __init__(self, max_history: int = 80, auto_shapes: bool = True) -> None:
        self._strokes: list[Any] = []  # list[Stroke]
        self._current: Any | None = None
        self._undo: list[list[Any]] = []
        self._redo: list[list[Any]] = []
        self.max_history = max(10, int(max_history))
        self.auto_shapes = bool(auto_shapes)
        self._lock = threading.RLock()
        self._current_tool = "pen"
        self._current_color = "#ff6b57"
        self._current_width = 5.0
        self._started_at = 0.0
        self._last_shape_result: ShapeResult | None = None

    @property
    def current(self) -> Any | None:
        return self._current

    @property
    def strokes(self) -> list[Any]:
        with self._lock:
            return list(self._strokes)

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def _push_undo(self) -> None:
        self._undo.append(copy.deepcopy(self._strokes))
        if len(self._undo) > self.max_history:
            self._undo.pop(0)
        self._redo.clear()

    def begin(
        self,
        point: Point,
        *,
        color: str | None = None,
        width: float | None = None,
        tool: str = "pen",
        now: float | None = None,
    ) -> None:
        from .models import Stroke

        with self._lock:
            if self._current is not None:
                self.cancel()
            self._current = Stroke(
                id=f"s-{uuid.uuid4().hex[:10]}",
                points=[point],
                color=color or self._current_color,
                width=float(width if width is not None else self._current_width),
                kind="freehand" if tool == "pen" else tool,
            )
            self._current_color = self._current.color
            self._current_width = self._current.width
            self._current_tool = tool
            self._started_at = time.time() if now is None else now
            self._last_shape_result = None

    def add(self, point: Point, *, min_distance: float = 0.0018) -> bool:
        with self._lock:
            if self._current is None:
                return False
            if self._current.points and point.distance(self._current.points[-1]) < min_distance:
                return False
            self._current.points.append(point)
            # Record pressure-like speed as part of width? Kept vector-thin here.
            return True

    def end(self, *, now: float | None = None) -> DrawCommit | None:
        with self._lock:
            stroke = self._current
            self._current = None
            if stroke is None:
                return None
            if len(stroke.points) < 2:
                return DrawCommit(stroke_id=stroke.id, reason="single point")
            if stroke.kind == "eraser":
                return None
            corrected = False
            shape = "freehand"
            confidence = 0.0
            reason = ""
            if self.auto_shapes and stroke.kind == "freehand":
                result = recognize_shape(stroke.points)
                if result.recognized:
                    stroke.points = result.corrected_points
                    stroke.kind = "circle"
                    stroke.closed = True
                    stroke.corrected = True
                    corrected = True
                    shape = "circle"
                    confidence = result.confidence
                    self._last_shape_result = result
                else:
                    reason = result.reason
            self._push_undo()
            self._strokes.append(stroke)
            return DrawCommit(
                stroke_id=stroke.id,
                corrected=corrected,
                shape=shape,
                confidence=confidence,
                points=len(stroke.points),
                reason=reason,
            )

    def cancel(self) -> None:
        with self._lock:
            self._current = None

    def erase_at(self, point: Point, radius: float = 0.018) -> bool:
        with self._lock:
            hit = [s for s in self._strokes if stroke_hits_point(s.points, point, radius + s.width / 900.0)]
            if not hit:
                return False
            self._push_undo()
            hit_ids = {s.id for s in hit}
            self._strokes = [s for s in self._strokes if s.id not in hit_ids]
            return True

    def undo(self) -> bool:
        with self._lock:
            if not self._undo:
                return False
            self._redo.append(copy.deepcopy(self._strokes))
            self._strokes = self._undo.pop()
            return True

    def redo(self) -> bool:
        with self._lock:
            if not self._redo:
                return False
            self._undo.append(copy.deepcopy(self._strokes))
            self._strokes = self._redo.pop()
            return True

    def clear(self) -> bool:
        with self._lock:
            if not self._strokes:
                return False
            self._push_undo()
            self._strokes = []
            return True

    def remove_stroke(self, stroke_id: str) -> bool:
        with self._lock:
            matches = [s for s in self._strokes if s.id == stroke_id]
            if not matches:
                return False
            self._push_undo()
            self._strokes = [s for s in self._strokes if s.id != stroke_id]
            return True

    def style(self, color: str | None = None, width: float | None = None) -> None:
        with self._lock:
            if color:
                self._current_color = color
            if width:
                self._current_width = float(width)

    def snapshot(self, max_points: int = 900) -> DrawingSnapshot:
        with self._lock:
            current = None
            if self._current is not None:
                current = self._current.to_dict(max_points=max_points)
            return DrawingSnapshot(
                strokes=[stroke.to_dict(max_points=max_points) for stroke in self._strokes],
                current=current,
                can_undo=bool(self._undo),
                can_redo=bool(self._redo),
                stroke_count=len(self._strokes),
                history_depth=len(self._undo),
                auto_shapes=self.auto_shapes,
            )

    def export_strokes(self) -> list[dict[str, Any]]:
        return self.snapshot(max_points=10000).strokes

    def replace_strokes(self, strokes: Sequence[Any]) -> None:
        with self._lock:
            self._push_undo()
            self._strokes = list(strokes)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "strokes": len(self._strokes),
                "points": sum(len(s.points) for s in self._strokes),
                "can_undo": bool(self._undo),
                "can_redo": bool(self._redo),
                "auto_shapes": self.auto_shapes,
            }
