from __future__ import annotations

import cv2
import numpy as np

from aircanvas.geometry import BBox
from aircanvas.tracking import ObjectTrackerManager


def make_frame(offset_x: int = 0, offset_y: int = 0, occluded: bool = False) -> np.ndarray:
    frame = np.full((480, 640, 3), 218, dtype=np.uint8)
    if occluded:
        frame[:] = 95
        return frame
    cv2.rectangle(frame, (250 + offset_x, 160 + offset_y), (390 + offset_x, 330 + offset_y), (45, 95, 185), -1)
    cv2.circle(frame, (320 + offset_x, 220 + offset_y), 24, (200, 230, 245), -1)
    return frame


def test_tracks_a_moving_object():
    manager = ObjectTrackerManager()
    now = 0.0
    manager.add_from_region(make_frame(), BBox(0.38, 0.32, 0.23, 0.37), now=now)
    for i in range(18):
        now += 1 / 30
        markers = manager.update(make_frame(i * 3, i), now)
    assert markers[0]["status"] == "tracking"
    assert markers[0]["bbox"][0] > 0.38


def test_temporary_occlusion_is_reported_and_recovered():
    manager = ObjectTrackerManager()
    now = 0.0
    manager.add_from_region(make_frame(), BBox(0.38, 0.32, 0.23, 0.37), now=now)
    for i in range(8):
        now += 1 / 30
        manager.update(make_frame(i * 2, 0), now)
    for _ in range(4):
        now += 1 / 30
        markers = manager.update(make_frame(16, 0, occluded=True), now)
    assert markers[0]["status"] == "occluded"
    for _ in range(8):
        now += 1 / 30
        markers = manager.update(make_frame(18, 0), now)
    assert markers[0]["status"] in ("tracking", "occluded")


def test_object_leaving_frame_stops_tracking():
    manager = ObjectTrackerManager()
    now = 0.0
    manager.add_from_region(make_frame(), BBox(0.38, 0.32, 0.23, 0.37), now=now)
    status = "tracking"
    for i in range(70):
        now += 1 / 30
        markers = manager.update(make_frame(i * 11, 0), now)
        status = markers[0]["status"]
        if status == "out_of_view":
            break
    assert status == "out_of_view"
    assert markers[0]["lost_reason"] == "left camera view"


def test_manual_removal():
    manager = ObjectTrackerManager()
    tracker = manager.add_from_region(make_frame(), BBox(0.38, 0.32, 0.23, 0.37), now=0)
    assert manager.remove(tracker.id)
    assert manager.count == 0
    assert not manager.remove(tracker.id)


def test_maximum_markers():
    manager = ObjectTrackerManager()
    for _ in range(5):
        manager.add_from_region(make_frame(), BBox(0.30, 0.30, 0.25, 0.25), now=0)
    try:
        manager.add_from_region(make_frame(), BBox(0.30, 0.30, 0.25, 0.25), now=0)
    except ValueError as exc:
        assert "At most" in str(exc)
    else:
        raise AssertionError("A sixth marker should be rejected")
