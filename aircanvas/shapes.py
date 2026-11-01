"""Shape recognition/correction and the mirror-mode loop selection detector."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from .geometry import (
    BBox,
    Point,
    angular_coverage,
    bbox_from_points,
    circularity,
    polyline_length,
)


@dataclass
class CircleFit:
    center: Point
    radius: float
    confidence: float
    regular: bool = True

    def points(self, count: int = 96) -> list[Point]:
        return [
            Point(
                self.center.x + math.cos(2 * math.pi * i / count) * self.radius,
                self.center.y + math.sin(2 * math.pi * i / count) * self.radius,
            )
            for i in range(count)
        ]


@dataclass
class ShapeResult:
    kind: str = "freehand"  # circle | line | freehand
    confidence: float = 0.0
    circle: CircleFit | None = None
    corrected_points: list[Point] = field(default_factory=list)
    reason: str = ""

    @property
    def recognized(self) -> bool:
        return self.kind != "freehand" and bool(self.corrected_points)


def fit_circle(points: Sequence[Point]) -> CircleFit | None:
    """Algebraic (Kasa) circle fit robust enough for hand-drawn loops."""
    if len(points) < 8:
        return None
    # Work around the mean to improve conditioning.
    mean_x = sum(p.x for p in points) / len(points)
    mean_y = sum(p.y for p in points) / len(points)
    su, sv, suu, svv, suv, suuu, svvv, suvv, svuu = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    for p in points:
        u, v = p.x - mean_x, p.y - mean_y
        su += u
        sv += v
        suu += u * u
        svv += v * v
        suv += u * v
        suuu += u * u * u
        svvv += v * v * v
        suvv += u * v * v
        svuu += v * u * u
    n = float(len(points))
    # Solve [suu suv; suv svv] [uc, vc] = rhs
    det = suu * svv - suv * suv
    if abs(det) < 1e-14:
        return None
    rhs_u = 0.5 * (suuu + suvv)
    rhs_v = 0.5 * (svvv + svuu)
    uc = (rhs_u * svv - rhs_v * suv) / det
    vc = (rhs_v * suu - rhs_u * suv) / det
    center = Point(uc + mean_x, vc + mean_y)
    radii = [center.distance(p) for p in points]
    radius = sum(radii) / n
    if radius <= 1e-5:
        return None
    variance = sum((r - radius) ** 2 for r in radii) / n
    variation = math.sqrt(variance) / radius
    regular = variation < 0.20
    confidence = max(0.0, min(1.0, 1.0 - variation * 2.4)) * 0.6 + circularity(points) * 0.4
    return CircleFit(center=center, radius=radius, confidence=confidence, regular=regular)


def recognize_shape(points: Sequence[Point], *, min_points: int = 12) -> ShapeResult:
    """Recognise a deliberately drawn closed circle.

    The detector is conservative: an open scribble is never corrected.  This
    protects freehand expressiveness and makes the optional nature of shape
    correction meaningful.
    """
    if len(points) < min_points:
        return ShapeResult(reason="too short")
    length = polyline_length(points)
    if length < 0.14:
        return ShapeResult(reason="too short")
    box = bbox_from_points(points)
    if min(box.w, box.h) < 0.035:
        return ShapeResult(reason="too flat")
    # Hand-drawn loops often overshoot the starting point by a few degrees.
    # Measuring the best closure over the trailing half accepts a natural
    # overshoot, while angular coverage still rejects open arcs.
    tail = points[max(1, int(len(points) * 0.5)) :]
    closure_gap = min(points[0].distance(p) for p in tail) / max(1e-6, box.diagonal)
    if closure_gap > 0.24:
        return ShapeResult(reason="not closed")
    coverage = angular_coverage(points, bins=12)
    circ = circularity(points)
    aspect = box.w / max(1e-6, box.h)
    if coverage < 0.72 or circ < 0.48 or not (0.55 <= aspect <= 1.9):
        return ShapeResult(reason="not round enough")
    fit = fit_circle(points)
    if fit is None or fit.radius <= 0:
        return ShapeResult(reason="fit failed")
    if not (0.45 <= aspect <= 1.9):
        return ShapeResult(reason="not a circle")
    confidence = min(0.99, fit.confidence * 0.75 + (1.0 - closure_gap) * 0.15 + coverage * 0.10)
    if confidence < 0.54:
        return ShapeResult(reason="low confidence", confidence=confidence)
    corrected = fit.points(96)
    # Keep the corrected shape inside the canvas.
    if any(p.x < 0.0 or p.x > 1.0 or p.y < 0.0 or p.y > 1.0 for p in corrected):
        return ShapeResult(reason="outside canvas", confidence=confidence)
    return ShapeResult(kind="circle", confidence=confidence, circle=fit, corrected_points=corrected)


@dataclass
class SelectionUpdate:
    status: str
    progress: float = 0.0
    points: list[Point] = field(default_factory=list)
    bbox: BBox | None = None
    hint: str = "Draw a loop around an object"


class LoopSelectionDetector:
    """Turn a circular fingertip trail into an object-selection region.

    The user draws a loop and briefly holds still.  Completion requires:
    minimum path length, spatial closure, angular coverage, and a short dwell.
    This avoids accidental tracking when the user simply points across the feed.
    """

    def __init__(self, hold_seconds: float = 0.26, min_points: int = 14) -> None:
        self.hold_seconds = max(0.1, hold_seconds)
        self.min_points = min_points
        self.points: list[Point] = []
        self.started_at = 0.0
        self.last_point_at = 0.0
        self.closed_since: float | None = None
        self.status = "idle"
        self.last_progress = 0.0
        self._last_final: BBox | None = None
        self._finalized = False

    def reset(self) -> None:
        self.points.clear()
        self.closed_since = None
        self.status = "idle"
        self.last_progress = 0.0
        self._finalized = False
        self.started_at = 0.0
        self.last_point_at = 0.0

    @property
    def is_drawing(self) -> bool:
        return bool(self.points) and self.status == "drawing"

    def add(self, point: Point, now: float) -> SelectionUpdate:
        if not self.points:
            self.started_at = now
            self.status = "drawing"
        if not self.points or point.distance(self.points[-1]) >= 0.004:
            self.points.append(point)
        self.last_point_at = now
        if len(self.points) > 400:
            # Keep the most recent portion; loops that long are already invalid.
            self.points = self.points[-400:]
        self._update_closure(now)
        progress = self._progress(now)
        hint = "Keep going around the object" if progress < 0.9 else "Hold to select"
        if self.closed_since is not None:
            hint = "Hold still to lock the selection"
        return SelectionUpdate(
            "drawing",
            progress=progress,
            points=list(self.points),
            hint=hint,
        )

    def _update_closure(self, now: float) -> None:
        if len(self.points) < self.min_points:
            return
        box = bbox_from_points(self.points)
        if box.area < 0.003 or box.diagonal < 0.09:
            return
        coverage = angular_coverage(self.points, bins=10)
        length = polyline_length(self.points)
        closure = self.points[0].distance(self.points[-1]) / max(box.diagonal, 1e-6)
        if coverage >= 0.70 and closure <= 0.16 and length > 0.24:
            if self.closed_since is None:
                self.closed_since = now
        elif self.closed_since is not None and closure > 0.35:
            # Loop opened again; wait for the next closure.
            self.closed_since = None

    def _progress(self, now: float) -> float:
        if not self.points:
            return 0.0
        length_score = min(1.0, polyline_length(self.points) / 0.45)
        if len(self.points) < self.min_points:
            return max(0.0, length_score * 0.35)
        coverage = angular_coverage(self.points, bins=10)
        closure = self._closure_ratio()
        close_score = max(0.0, 1.0 - closure / 0.35)
        hold_score = 1.0
        if self.closed_since is not None:
            hold_score = min(1.0, (now - self.closed_since) / self.hold_seconds)
        progress = coverage * 0.45 + close_score * 0.25 + length_score * 0.15 + hold_score * 0.15
        self.last_progress = max(self.last_progress * 0.85, min(1.0, progress))
        return self.last_progress

    def _closure_ratio(self) -> float:
        if len(self.points) < 2:
            return 1.0
        box = bbox_from_points(self.points)
        return self.points[0].distance(self.points[-1]) / max(box.diagonal, 1e-6)

    def maybe_complete(self, now: float) -> SelectionUpdate | None:
        if self.closed_since is None or self._finalized:
            return None
        if now - self.closed_since < self.hold_seconds:
            return None
        box = bbox_from_points(self.points)
        if box.area < 0.003 or box.diagonal < 0.09:
            self.status = "rejected"
            return SelectionUpdate("rejected", self.last_progress, hint="Loop was too small")
        # The object usually occupies the middle of the loop; inset the box so
        # the tracker's appearance model is not dominated by background.
        inset = box.expanded(0.82).clipped()
        if inset.area < 0.002:
            self.status = "rejected"
            return SelectionUpdate("rejected", self.last_progress, hint="Try a larger loop")
        self.status = "acquired"
        self._finalized = True
        self._last_final = inset
        return SelectionUpdate(
            "acquired",
            progress=1.0,
            points=list(self.points),
            bbox=inset,
            hint="Object locked - tracking",
        )

    def finish(self, now: float) -> SelectionUpdate | None:
        """Finish explicitly when the pointing pose ends."""
        completed = self.maybe_complete(now)
        if completed is not None:
            return completed
        if self.points:
            if len(self.points) >= self.min_points and self.closed_since is not None:
                # A deliberate close is enough even without the full dwell.
                self.hold_seconds = min(self.hold_seconds, 0.08)
                return self.maybe_complete(now)
            self.status = "rejected"
            update = SelectionUpdate("rejected", self.last_progress, hint="Loop not closed - try again")
            self.reset()
            return update
        return None

    def telemetry(self, active: bool = True) -> dict[str, object]:
        return {
            "active": active and bool(self.points),
            "points": [[round(p.x, 4), round(p.y, 4)] for p in self.points[-180:]],
            "progress": round(self.last_progress, 2),
            "hint": "Draw a loop around an object"
            if self.status == "idle"
            else ("Hold still to lock the selection" if self.closed_since else "Keep going around the object"),
            "status": self.status,
        }
