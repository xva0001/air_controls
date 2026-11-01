from __future__ import annotations

from aircanvas.config import GestureSettings
from aircanvas.geometry import Point
from aircanvas.mapping import MouseController, NavigationController
from aircanvas.models import GestureReading


def settings() -> GestureSettings:
    return GestureSettings(
        nav_pose="open_palm",
        page_pose="peace",
        nav_hold_ms=280,
        nav_cooldown_ms=1000,
        nav_sensitivity=1.0,
    )


def test_navigation_requires_arm_hold_and_deliberate_swipe():
    nav = NavigationController(settings())
    p0 = Point(0.5, 0.5)
    p1 = Point(0.7, 0.5)
    # Moving immediately does not count: the anchor follows during arming.
    event, _ = nav.update("open_palm", p0, 0.0)
    assert event is None
    event, _ = nav.update("open_palm", p1, 0.10)
    assert event is None
    event, _ = nav.update("open_palm", p1, 0.20)
    assert event is None
    event, _ = nav.update("open_palm", p1, 0.30)
    assert event is None
    # Deliberate movement once armed fires exactly one back/forward action.
    event, telemetry = nav.update("open_palm", Point(0.85, 0.5), 0.36)
    assert event is not None
    assert event.action == "forward"
    event2, _ = nav.update("open_palm", Point(0.95, 0.5), 0.42)
    assert event2 is None


def test_page_swipe_uses_two_fingers():
    nav = NavigationController(settings())
    for t in (0.0, 0.15, 0.25, 0.30):
        event, _ = nav.update("peace", Point(0.5, 0.5), t)
        assert event is None
    event, _ = nav.update("peace", Point(0.30, 0.5), 0.36)
    assert event is not None
    assert event.action == "page_prev"


def test_cooldown_and_release_rearm():
    nav = NavigationController(settings())
    for t in (0.0, 0.1, 0.2, 0.3):
        nav.update("open_palm", Point(0.5, 0.5), t)
    event, _ = nav.update("open_palm", Point(0.7, 0.5), 0.36)
    assert event is not None
    # Same pose cannot fire again until released.
    for t in (0.5, 0.8, 1.2):
        event, _ = nav.update("open_palm", Point(0.9, 0.5), t)
        assert event is None
    # Release, re-arm and swipe after the cooldown.
    nav.update("fist", Point(0.5, 0.5), 1.3)
    for t in (1.4, 1.6, 1.75):
        nav.update("open_palm", Point(0.5, 0.5), t)
    event, _ = nav.update("open_palm", Point(0.7, 0.5), 1.8)
    assert event is not None


def test_mouse_pinch_click_drag_and_release():
    mouse = MouseController(GestureSettings())
    pinch = GestureReading(raw="pinch", stable="pinch", confidence=0.9)
    point = GestureReading(raw="point", stable="point", confidence=0.9)
    update = mouse.update(pinch, Point(0.4, 0.4), 0.0)
    assert [event["kind"] for event in update.events] == ["mouse_left_down"]
    assert update.pressed
    update = mouse.update(pinch, Point(0.45, 0.45), 0.2)
    assert update.pressed
    assert update.events == []
    update = mouse.update(point, Point(0.45, 0.45), 0.4)
    assert [event["kind"] for event in update.events] == ["mouse_left_up"]
    assert not update.pressed


def test_mouse_right_click_requires_hold():
    mouse = MouseController(GestureSettings(right_click_hold_ms=420))
    peace = GestureReading(raw="peace", stable="peace", confidence=0.9)
    update = mouse.update(peace, Point(0.5, 0.5), 0.0)
    assert update.events == []
    update = mouse.update(peace, Point(0.5, 0.5), 0.2)
    assert update.events == []
    update = mouse.update(peace, Point(0.5, 0.5), 0.5)
    assert [event["kind"] for event in update.events] == ["mouse_right_click"]
    update = mouse.update(peace, Point(0.5, 0.5), 0.8)
    assert update.events == []


def test_mouse_release_on_disable():
    mouse = MouseController()
    pinch = GestureReading(raw="pinch", stable="pinch")
    mouse.update(pinch, Point(0.2, 0.2), 0.0)
    update = mouse.update(None, Point(0.2, 0.2), 0.2, enabled=False)
    assert [event["kind"] for event in update.events] == ["mouse_left_up"]
