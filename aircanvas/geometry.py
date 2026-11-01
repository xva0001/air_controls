"""Small, dependency-free 2-D geometry helpers.

All interaction coordinates are normalised to ``[0, 1]`` of the source image
(camera frame or application canvas).  Keeping geometry normalised makes the
same drawing and tracking data render correctly on a 1280x720 webcam, a
1920x1080 canvas, a high-DPI desktop screen and a browser window.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    def as_list(self) -> list[float]:
        return [round(self.x, 5), round(self.y, 5)]

    def distance(self, other: Point) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def lerp(self, other: Point, t: float) -> Point:
        t = max(0.0, min(1.0, t))
        return Point(self.x + (other.x - self.x) * t, self.y + (other.y - self.y) * t)


@dataclass(frozen=True)
class BBox:
    """Normalised axis-aligned bounding box."""

    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def area(self) -> float:
        return max(0.0, self.w) * max(0.0, self.h)

    @property
    def center(self) -> Point:
        return Point(self.x + self.w / 2.0, self.y + self.h / 2.0)

    @property
    def diagonal(self) -> float:
        return math.hypot(self.w, self.h)

    def as_list(self) -> list[float]:
        return [round(self.x, 5), round(self.y, 5), round(self.w, 5), round(self.h, 5)]

    def padded(self, fraction: float) -> BBox:
        pad_x = self.w * fraction
        pad_y = self.h * fraction
        return BBox(self.x - pad_x, self.y - pad_y, self.w + 2 * pad_x, self.h + 2 * pad_y)

    def clipped(self) -> BBox:
        left = max(0.0, min(1.0, self.x))
        top = max(0.0, min(1.0, self.y))
        right = max(0.0, min(1.0, self.right))
        bottom = max(0.0, min(1.0, self.bottom))
        return BBox(left, top, max(0.0, right - left), max(0.0, bottom - top))

    def intersection_area(self, other: BBox) -> float:
        left = max(self.x, other.x)
        top = max(self.y, other.y)
        right = min(self.right, other.right)
        bottom = min(self.bottom, other.bottom)
        return max(0.0, right - left) * max(0.0, bottom - top)

    def contains(self, point: Point) -> bool:
        return self.x <= point.x <= self.right and self.y <= point.y <= self.bottom

    def to_pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        x = int(round(self.x * width))
        y = int(round(self.y * height))
        w = max(1, int(round(self.w * width)))
        h = max(1, int(round(self.h * height)))
        return x, y, w, h

    def expanded(self, factor: float) -> BBox:
        new_w = self.w * factor
        new_h = self.h * factor
        return BBox(
            self.x - (new_w - self.w) / 2.0,
            self.y - (new_h - self.h) / 2.0,
            new_w,
            new_h,
        )


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def distance(a: Point, b: Point) -> float:
    return a.distance(b)


def bbox_from_points(points: Sequence[Point], padding: float = 0.0) -> BBox:
    if not points:
        return BBox(0.5, 0.5, 0.0, 0.0)
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    box = BBox(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    return box.padded(padding) if padding else box


def centroid(points: Sequence[Point]) -> Point:
    if not points:
        return Point(0.5, 0.5)
    return Point(sum(p.x for p in points) / len(points), sum(p.y for p in points) / len(points))


def polyline_length(points: Sequence[Point]) -> float:
    return sum(points[i - 1].distance(points[i]) for i in range(1, len(points)))


def resample(points: Sequence[Point], max_points: int) -> list[Point]:
    if len(points) <= max_points:
        return list(points)
    if max_points < 2:
        return [points[0]]
    step = (len(points) - 1) / (max_points - 1)
    return [points[round(i * step)] for i in range(max_points)]


def point_segment_distance(point: Point, start: Point, end: Point) -> float:
    dx, dy = end.x - start.x, end.y - start.y
    if dx == dy == 0:
        return point.distance(start)
    t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    projection = Point(start.x + t * dx, start.y + t * dy)
    return point.distance(projection)


def stroke_hits_point(points: Sequence[Point], target: Point, radius: float) -> bool:
    if not points:
        return False
    if len(points) == 1:
        return points[0].distance(target) <= radius
    for i in range(1, len(points)):
        if point_segment_distance(target, points[i - 1], points[i]) <= radius:
            return True
    return False


def angle_at(a: Point, b: Point, c: Point) -> float:
    """Angle ABC in degrees, 0..180."""
    abx, aby = a.x - b.x, a.y - b.y
    cbx, cby = c.x - b.x, c.y - b.y
    norm = math.hypot(abx, aby) * math.hypot(cbx, cby)
    if norm <= 1e-9:
        return 0.0
    cosine = max(-1.0, min(1.0, (abx * cbx + aby * cby) / norm))
    return math.degrees(math.acos(cosine))


def angle_between(a: Point, b: Point) -> float:
    return math.degrees(math.atan2(b.y - a.y, b.x - a.x))


def wrap_angle(angle: float) -> float:
    while angle <= -180:
        angle += 360
    while angle > 180:
        angle -= 360
    return angle


def circularity(points: Sequence[Point]) -> float:
    """Return 1 for a perfect circle and lower values for irregular loops."""
    if len(points) < 8:
        return 0.0
    center = centroid(points)
    radii = [center.distance(p) for p in points]
    mean = sum(radii) / len(radii)
    if mean <= 1e-6:
        return 0.0
    variance = sum((r - mean) ** 2 for r in radii) / len(radii)
    coefficient = math.sqrt(variance) / mean
    return max(0.0, min(1.0, 1.0 - coefficient * 2.2))


def angular_coverage(points: Sequence[Point], bins: int = 12) -> float:
    if len(points) < 2:
        return 0.0
    center = centroid(points)
    occupied = set()
    for p in points:
        angle = math.atan2(p.y - center.y, p.x - center.x)
        idx = int(((angle + math.pi) / (2 * math.pi)) * bins) % bins
        occupied.add(idx)
    return len(occupied) / bins


def percent_rank(value: float, values: Iterable[float]) -> float:
    vals = sorted(values)
    if not vals:
        return 0.0
    return sum(1 for v in vals if v <= value) / len(vals)


def map_axis(value: float, margin: float) -> float:
    """Map [margin, 1-margin] -> [0, 1], clamped."""
    if margin >= 0.49:
        return 0.5
    return clamp((value - margin) / (1.0 - margin * 2.0))


def point_to_list(points: Sequence[Point]) -> list[list[float]]:
    return [p.as_list() for p in points]


def points_from_list(data: Iterable[Sequence[float]]) -> list[Point]:
    return [Point(float(item[0]), float(item[1])) for item in data if len(item) >= 2]


def scale_point(point: Point, width: float, height: float) -> tuple[float, float]:
    return (point.x * width, point.y * height)


def aspect_fit_rect(
    source_width: float,
    source_height: float,
    target_width: float,
    target_height: float,
) -> tuple[float, float, float, float]:
    """Contain-fit rectangle (x, y, width, height) for an image in a viewport."""
    if source_width <= 0 or source_height <= 0 or target_width <= 0 or target_height <= 0:
        return (0.0, 0.0, target_width, target_height)
    scale = min(target_width / source_width, target_height / source_height)
    w = source_width * scale
    h = source_height * scale
    return ((target_width - w) / 2.0, (target_height - h) / 2.0, w, h)
