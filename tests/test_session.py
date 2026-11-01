from __future__ import annotations

import math

from aircanvas.config import AppConfig
from aircanvas.demo import DemoEngine
from aircanvas.geometry import Point
from aircanvas.session import InteractionSession
from aircanvas.synthetic import hand_with_index_tip, synthetic_hand


def _feed_point_circle(session: InteractionSession, frames: int = 90) -> None:
    now = 0.0
    for i in range(frames):
        angle = 2 * math.pi * 0.96 * i / max(1, frames - 1)
        tip = Point(0.48 + 0.17 * math.cos(angle), 0.48 + 0.14 * math.sin(angle))
        session.process_frame(None, now, observation=hand_with_index_tip(tip).observation())
        now += 1 / 30


def test_screen_draw_and_shape_correction_through_session():
    session = InteractionSession(AppConfig(auto_shapes=True))
    _feed_point_circle(session)
    for i in range(10):
        session.process_frame(None, 3.2 + i / 30, observation=synthetic_hand("fist").observation())
    snapshot = session.snapshot()
    assert len(snapshot["drawing"]["strokes"]) == 1
    assert snapshot["drawing"]["strokes"][0]["kind"] == "circle"
    assert snapshot["drawing"]["strokes"][0]["corrected"] is True
    assert any(event["kind"] == "shape_corrected" for event in snapshot["events"])
    assert session.undo()
    assert not session.snapshot()["drawing"]["strokes"]
    assert session.redo()
    assert len(session.snapshot()["drawing"]["strokes"]) == 1


def test_shape_correction_can_be_disabled_per_config():
    session = InteractionSession(AppConfig(auto_shapes=False))
    _feed_point_circle(session)
    for i in range(8):
        session.process_frame(None, 3.2 + i / 30, observation=synthetic_hand("fist").observation())
    assert session.snapshot()["drawing"]["strokes"][0]["kind"] == "freehand"


def test_custom_draw_pose_is_observed():
    config = AppConfig()
    config.gesture.draw_pose = "peace"
    session = InteractionSession(config)
    now = 0.0
    for i in range(40):
        session.process_frame(None, now, observation=synthetic_hand("peace", center=Point(0.4 + i * 0.002, 0.5)).observation())
        now += 1 / 30
    assert session.snapshot()["drawing"]["current"] is not None
    for i in range(8):
        session.process_frame(None, now, observation=synthetic_hand("fist").observation())
        now += 1 / 30
    assert session.snapshot()["drawing"]["strokes"]


def test_mouse_gesture_events_are_emitted_through_session():
    session = InteractionSession(AppConfig())
    session.set_tool("mouse")
    events = []
    now = 0.0
    for i in range(12):
        events += session.process_frame(None, now, observation=synthetic_hand("pinch", center=Point(0.5, 0.5)).observation())
        now += 1 / 30
    assert any(event.kind == "mouse_left_down" for event in events)
    for i in range(12):
        events += session.process_frame(None, now, observation=synthetic_hand("point", center=Point(0.55, 0.5)).observation())
        now += 1 / 30
    assert any(event.kind == "mouse_left_up" for event in events)
    snapshot = session.snapshot()
    assert snapshot["pointer"]["kind"] == "mouse"


def test_navigation_tool_emits_semantic_action():
    session = InteractionSession(AppConfig())
    session.set_tool("navigate")
    events = []
    now = 0.0
    for i in range(12):
        events += session.process_frame(None, now, observation=synthetic_hand("open_palm", center=Point(0.5, 0.5)).observation())
        now += 1 / 30
    for i in range(12):
        events += session.process_frame(None, now, observation=synthetic_hand("open_palm", center=Point(0.72, 0.5)).observation())
        now += 1 / 30
    nav_events = [event for event in events if event.kind == "navigation"]
    assert nav_events
    assert nav_events[0].data["action"] in ("forward", "back", "scroll_up", "scroll_down")


def test_mirror_mode_acquires_and_removes_tracking_marker():
    session = InteractionSession(AppConfig())
    session.set_mode("mirror")
    session.set_tool("track")
    engine = DemoEngine(session)
    for i in range(int(5.8 * 30)):
        t = i / 30
        frame = engine.frame(t)
        session.process_frame(frame, t, observation=engine.observation(t))
    snapshot = session.snapshot()
    assert snapshot["mode"] == "mirror"
    assert snapshot["tracks"]
    assert snapshot["tracks"][0]["status"] in ("tracking", "occluded", "reacquiring")
    object_id = snapshot["tracks"][0]["id"]
    assert session.remove_track(object_id)
    assert session.snapshot()["tracks"] == []


def test_mirror_annotation_persists_while_video_moves():
    session = InteractionSession(AppConfig())
    session.set_mode("mirror")
    session.set_tool("annotate")
    engine = DemoEngine(session)
    for i in range(90):
        t = i / 30
        frame = engine.frame(t)
        session.process_frame(frame, t, observation=engine.observation(t))
    assert session.snapshot()["drawing"]["strokes"]
    # Switching modes preserves separate drawing surfaces.
    session.set_mode("screen")
    assert session.snapshot()["drawing"]["strokes"] == []
    session.set_mode("mirror")
    assert session.snapshot()["drawing"]["strokes"]


def test_no_hand_state_is_safe():
    session = InteractionSession()
    session.process_frame(None, 0.0, observation=None)
    snapshot = session.snapshot()
    assert snapshot["hand"]["visible"] is False
    assert snapshot["pointer"]["visible"] is False
    assert snapshot["gesture"]["stable"] == "none"
