"""Deterministic synthetic hand landmarks for tests, demos and screenshots.

This module does not attempt to fake MediaPipe recognition.  It supplies an
already-recognised hand observation to the *same* session and mapper used with
a real camera, which is why the simulated feed exercises the real interaction
logic and drawing/tracking pipeline.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .geometry import Point
from .models import HandObservation

# Local hand space: wrist at (0, 0), fingers up (-y).  The 21 points match
# MediaPipe's landmark ordering exactly.
_EXTENDED: list[tuple[float, float]] = [
    (0.0, 0.0),  # wrist
    (-0.28, -0.12), (-0.46, -0.29), (-0.55, -0.46), (-0.62, -0.62),  # thumb
    (-0.22, -0.55), (-0.24, -0.77), (-0.24, -0.92), (-0.24, -1.04),  # index
    (0.00, -0.60), (0.00, -0.86), (0.00, -1.01), (0.00, -1.14),  # middle
    (0.20, -0.56), (0.22, -0.79), (0.23, -0.94), (0.24, -1.05),  # ring
    (0.38, -0.48), (0.41, -0.66), (0.42, -0.78), (0.43, -0.89),  # pinky
]

_FINGERS = {
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}


def _with_fingers(local: list[tuple[float, float]], folded: set[str]) -> list[tuple[float, float]]:
    points = list(local)
    for name in folded:
        mcp, pip, dip, tip = _FINGERS[name]
        bx, by = points[mcp]
        # Curl toward the palm while keeping the PIP joint slightly raised.
        points[pip] = (bx + 0.025, by - 0.045)
        points[dip] = (bx + 0.075, by - 0.020)
        points[tip] = (bx + 0.038, by + 0.020)
    return points


@dataclass
class SyntheticHand:
    landmarks: list[Point]
    pose: str
    handedness: str = "Right"

    def observation(self, score: float = 0.96) -> HandObservation:
        return HandObservation(self.landmarks, handedness=self.handedness, score=score)


def _local_for_pose(pose: str) -> list[tuple[float, float]]:
    pose = pose.lower()
    if pose == "point":
        local = _with_fingers(_EXTENDED, {"middle", "ring", "pinky"})
        # Keep the thumb out of the way but not pinching.
        local[3] = (-0.52, -0.48)
        local[4] = (-0.55, -0.38)
        return local
    if pose == "pinch":
        local = _with_fingers(_EXTENDED, {"middle", "ring", "pinky"})
        # Bring thumb tip to index tip; adjust the two distal thumb points.
        ix, iy = local[8]
        local[3] = (ix - 0.075, iy + 0.06)
        local[4] = (ix - 0.015, iy + 0.015)
        return local
    if pose == "peace":
        return _with_fingers(_EXTENDED, {"ring", "pinky"})
    if pose == "three":
        return _with_fingers(_EXTENDED, {"pinky"})
    if pose == "open_palm":
        return list(_EXTENDED)
    if pose == "fist":
        local = _with_fingers(_EXTENDED, {"index", "middle", "ring", "pinky"})
        # Fold the thumb across the palm, away from the index tip.
        local[3] = (-0.34, -0.28)
        local[4] = (-0.20, -0.22)
        return local
    return list(_EXTENDED)


def synthetic_hand(
    pose: str = "point",
    *,
    center: Point = Point(0.5, 0.55),
    scale: float = 0.18,
    rotation_deg: float = 0.0,
    handedness: str = "Right",
    jitter: float = 0.0,
    seed: int = 7,
) -> SyntheticHand:
    """Create 21 normalised landmarks for a static pose.

    ``center`` refers to the palm centre, not the wrist.
    """
    local = _local_for_pose(pose)
    # Palm centre in local coordinates.
    pcx = (local[0][0] + local[5][0] + local[9][0] + local[17][0]) / 4.0
    pcy = (local[0][1] + local[5][1] + local[9][1] + local[17][1]) / 4.0
    angle = math.radians(rotation_deg)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    rng = random.Random(seed)
    points: list[Point] = []
    for x, y in local:
        x, y = x - pcx, y - pcy
        rx = x * cos_a - y * sin_a
        ry = x * sin_a + y * cos_a
        px = center.x + rx * scale
        py = center.y + ry * scale
        if jitter:
            px += rng.uniform(-jitter, jitter)
            py += rng.uniform(-jitter, jitter)
        points.append(Point(max(0.01, min(0.99, px)), max(0.01, min(0.99, py))))
    return SyntheticHand(points, pose=pose, handedness=handedness)


def hand_with_index_tip(
    tip: Point,
    *,
    pose: str = "point",
    scale: float = 0.18,
    rotation_deg: float = 0.0,
    handedness: str = "Right",
    jitter: float = 0.0,
    seed: int = 7,
) -> SyntheticHand:
    """Place a synthetic pointing hand so landmark 8 lands on ``tip``."""
    base = synthetic_hand(pose, center=Point(0.5, 0.5), scale=scale, rotation_deg=rotation_deg, handedness=handedness)
    base_tip = base.landmarks[8]
    center = Point(
        (0.5 + (tip.x - base_tip.x)),
        (0.5 + (tip.y - base_tip.y)),
    )
    return synthetic_hand(
        pose,
        center=center,
        scale=scale,
        rotation_deg=rotation_deg,
        handedness=handedness,
        jitter=jitter,
        seed=seed,
    )


def pinch_hand_at(
    center: Point = Point(0.5, 0.5),
    *,
    scale: float = 0.18,
    rotation_deg: float = 0.0,
) -> SyntheticHand:
    return synthetic_hand("pinch", center=center, scale=scale, rotation_deg=rotation_deg)


def landmarks_as_lists(hand: SyntheticHand) -> list[list[float]]:
    return [p.as_list() for p in hand.landmarks]
