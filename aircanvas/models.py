"""Serialisable domain models shared by every interface."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .config import Pose
from .geometry import BBox, Point, bbox_from_points, points_from_list

GESTURE_LABELS: dict[str, str] = {
    Pose.NONE.value: "No hand",
    Pose.POINT.value: "Point",
    Pose.PINCH.value: "Pinch",
    Pose.PEACE.value: "Two fingers",
    Pose.OPEN_PALM.value: "Open palm",
    Pose.FIST.value: "Fist",
    Pose.THREE.value: "Three fingers",
    Pose.UNKNOWN.value: "Unknown",
}


@dataclass
class HandObservation:
    """A single hand detection in normalised image coordinates."""

    landmarks: list[Point]
    handedness: str = "Unknown"
    score: float = 0.0
    timestamp: float = 0.0
    tracking_id: int = 0

    def __post_init__(self) -> None:
        if len(self.landmarks) != 21:
            raise ValueError(f"Expected 21 hand landmarks, got {len(self.landmarks)}")

    def point(self, index: int) -> Point:
        return self.landmarks[int(index) % 21]

    @property
    def wrist(self) -> Point:
        return self.landmarks[0]

    @property
    def index_tip(self) -> Point:
        return self.landmarks[8]

    @property
    def index_mcp(self) -> Point:
        return self.landmarks[5]

    @property
    def thumb_tip(self) -> Point:
        return self.landmarks[4]

    @property
    def middle_mcp(self) -> Point:
        return self.landmarks[9]

    @property
    def pinky_tip(self) -> Point:
        return self.landmarks[20]

    @property
    def palm_center(self) -> Point:
        return Point(
            (self.landmarks[0].x + self.landmarks[5].x + self.landmarks[9].x + self.landmarks[17].x) / 4.0,
            (self.landmarks[0].y + self.landmarks[5].y + self.landmarks[9].y + self.landmarks[17].y) / 4.0,
        )

    @property
    def pointer(self) -> Point:
        """A stable interaction point just behind the fingertip."""
        return self.landmarks[8].lerp(self.landmarks[7], 0.18)

    @property
    def scale(self) -> float:
        """A rotation-tolerant palm size used to normalise distances."""
        wrist_to_mcp = self.wrist.distance(self.middle_mcp)
        index_to_pinky = self.index_mcp.distance(self.landmarks[17])
        return max(0.025, (wrist_to_mcp + index_to_pinky) / 2.0)

    def to_dict(self, include_landmarks: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "visible": True,
            "handedness": self.handedness,
            "score": round(float(self.score), 3),
            "center": self.palm_center.as_list(),
            "index_tip": self.index_tip.as_list(),
            "thumb_tip": self.thumb_tip.as_list(),
        }
        if include_landmarks:
            data["landmarks"] = [p.as_list() for p in self.landmarks]
        return data


@dataclass
class FingerState:
    thumb: bool = False
    index: bool = False
    middle: bool = False
    ring: bool = False
    pinky: bool = False

    @property
    def count(self) -> int:
        return sum((self.thumb, self.index, self.middle, self.ring, self.pinky))

    def as_dict(self) -> dict[str, bool]:
        return {
            "thumb": self.thumb,
            "index": self.index,
            "middle": self.middle,
            "ring": self.ring,
            "pinky": self.pinky,
        }


@dataclass
class GestureReading:
    raw: str = Pose.NONE.value
    stable: str = Pose.NONE.value
    confidence: float = 0.0
    held_s: float = 0.0
    pinch_ratio: float = 1.0
    fingers: FingerState = field(default_factory=FingerState)
    thumb_index_gap: float = 1.0

    @property
    def label(self) -> str:
        return GESTURE_LABELS.get(self.stable, self.stable.title())

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "stable": self.stable,
            "label": self.label,
            "confidence": round(float(self.confidence), 3),
            "held_s": round(float(self.held_s), 2),
            "pinch_ratio": round(float(self.pinch_ratio), 3),
            "fingers": self.fingers.as_dict(),
        }


@dataclass
class Stroke:
    id: str
    points: list[Point]
    color: str = "#ff6b57"
    width: float = 5.0
    kind: str = "freehand"  # freehand | circle | line
    closed: bool = False
    corrected: bool = False
    created_at: float = field(default_factory=time.time)

    @property
    def bbox(self) -> BBox:
        return bbox_from_points(self.points)

    def to_dict(self, max_points: int | None = None, precision: int = 5) -> dict[str, Any]:
        points = self.points
        if max_points and len(points) > max_points:
            step = (len(points) - 1) / (max_points - 1)
            points = [points[round(i * step)] for i in range(max_points)]
        return {
            "id": self.id,
            "points": [[round(p.x, precision), round(p.y, precision)] for p in points],
            "color": self.color,
            "width": round(float(self.width), 2),
            "kind": self.kind,
            "closed": self.closed,
            "corrected": self.corrected,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Stroke:
        return cls(
            id=str(data.get("id", "stroke")),
            points=points_from_list(data.get("points", [])),
            color=str(data.get("color", "#ff6b57")),
            width=float(data.get("width", 5.0)),
            kind=str(data.get("kind", "freehand")),
            closed=bool(data.get("closed", False)),
            corrected=bool(data.get("corrected", False)),
        )


@dataclass
class TrackedMarker:
    id: int
    bbox: BBox
    status: str = "tracking"  # tracking | occluded | reacquiring | out_of_view | lost
    label: str = "Object"
    confidence: float = 1.0
    color: str = "#71d6b5"
    age_frames: int = 0
    missed_frames: int = 0
    last_seen_s: float = 0.0
    lost_reason: str = ""
    created_at: float = field(default_factory=time.time)

    @property
    def active(self) -> bool:
        return self.status in ("tracking", "occluded", "reacquiring")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "bbox": self.bbox.as_list(),
            "status": self.status,
            "label": self.label,
            "confidence": round(float(self.confidence), 2),
            "color": self.color,
            "age_frames": self.age_frames,
            "missed_frames": self.missed_frames,
            "lost_reason": self.lost_reason,
        }


@dataclass
class NavTelemetry:
    armed: bool = False
    progress: float = 0.0
    pose: str = Pose.NONE.value
    last_action: str = ""
    last_action_age_s: float = 99.0
    hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "armed": self.armed,
            "progress": round(float(self.progress), 2),
            "pose": self.pose,
            "last_action": self.last_action,
            "last_action_age_s": round(float(self.last_action_age_s), 1),
            "hint": self.hint,
        }


@dataclass
class PointerState:
    point: Point = field(default_factory=lambda: Point(0.5, 0.5))
    visible: bool = False
    pressed: bool = False
    kind: str = "cursor"  # cursor | pen | eraser | shape
    label: str = ""
    mapped: Point = field(default_factory=lambda: Point(0.5, 0.5))

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": round(float(self.point.x), 4),
            "y": round(float(self.point.y), 4),
            "mx": round(float(self.mapped.x), 4),
            "my": round(float(self.mapped.y), 4),
            "visible": self.visible,
            "pressed": self.pressed,
            "kind": self.kind,
            "label": self.label,
        }


@dataclass
class SelectionTelemetry:
    active: bool = False
    points: list[Point] = field(default_factory=list)
    progress: float = 0.0
    hint: str = "Draw a loop around an object"
    status: str = "idle"  # idle | drawing | closing | acquired | rejected

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "points": [[round(p.x, 4), round(p.y, 4)] for p in self.points[-180:]],
            "progress": round(float(self.progress), 2),
            "hint": self.hint,
            "status": self.status,
        }


@dataclass
class UiEvent:
    kind: str
    data: dict[str, Any] = field(default_factory=dict)
    at: float = field(default_factory=time.time)
    id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "data": self.data, "at": round(self.at, 3)}


def no_hand_dict() -> dict[str, Any]:
    return {"visible": False, "landmarks": [], "handedness": "None", "score": 0.0}


def clamp_stroke_points(points: Sequence[Point]) -> list[Point]:
    return [Point(min(1.0, max(0.0, p.x)), min(1.0, max(0.0, p.y))) for p in points]
