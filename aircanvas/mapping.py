"""Gesture mapping and intentional-motion debouncing for screen navigation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .config import GestureSettings, Pose
from .geometry import Point, clamp, map_axis
from .models import GestureReading, HandObservation, NavTelemetry


class NavAction(str, Enum):
    SCROLL_UP = "scroll_up"
    SCROLL_DOWN = "scroll_down"
    BACK = "back"
    FORWARD = "forward"
    PAGE_PREV = "page_prev"
    PAGE_NEXT = "page_next"


NAV_LABELS = {
    NavAction.SCROLL_UP.value: "Scroll up",
    NavAction.SCROLL_DOWN.value: "Scroll down",
    NavAction.BACK.value: "Back",
    NavAction.FORWARD.value: "Forward",
    NavAction.PAGE_PREV.value: "Previous page",
    NavAction.PAGE_NEXT.value: "Next page",
}


@dataclass
class NavEvent:
    action: str
    direction: str
    pose: str
    at: float

    @property
    def label(self) -> str:
        return NAV_LABELS.get(self.action, self.action.replace("_", " ").title())


class NavigationController:
    """Swipe recogniser that resists accidental hand movement.

    Safety layers: the navigate tool must be active, a deliberate pose must be
    stable, an anchor must be held briefly, a minimum displacement is required,
    only one action fires per swipe, and a cooldown limits repeats.
    """

    def __init__(self, settings: GestureSettings | None = None) -> None:
        self.settings = settings or GestureSettings()
        self.reset()

    def update_settings(self, settings: GestureSettings) -> None:
        self.settings = settings

    def reset(self) -> None:
        self._pose = Pose.NONE.value
        self._anchor: Point | None = None
        self._armed_at: float | None = None
        self._last_emit = -999.0
        self._await_release = False
        self._last_action = ""
        self._last_action_at = -999.0
        self._last_pointer = Point(0.5, 0.5)
        self._last_direction = ""

    @property
    def cooldown_remaining(self) -> float:
        # The caller supplies monotonic "now"; this helper is filled by update.
        return max(0.0, self._cooldown_until - self._now) if hasattr(self, "_cooldown_until") else 0.0

    def update(
        self,
        pose: str,
        pointer: Point,
        now: float,
        *,
        enabled: bool = True,
    ) -> tuple[NavEvent | None, NavTelemetry]:
        self._now = now
        self._last_pointer = pointer
        if not enabled:
            self.reset()
            return None, NavTelemetry(hint="Switch to Navigate to use swipes")
        nav_pose = self.settings.nav_pose
        page_pose = self.settings.page_pose
        eligible = pose in (nav_pose, page_pose)
        if not eligible:
            if pose in (Pose.NONE.value, Pose.FIST.value):
                self._await_release = False
            self._pose = pose
            self._anchor = None
            self._armed_at = None
            self._last_direction = ""
            return None, self._telemetry(0.0, "Hold an open palm, then swipe", now)

        if pose != self._pose:
            self._pose = pose
            self._anchor = pointer
            self._armed_at = now
            self._await_release = False
            self._last_direction = ""
        if self._anchor is None or self._armed_at is None:
            self._anchor = pointer
            self._armed_at = now

        hold_s = self.settings.nav_hold_ms / 1000.0
        elapsed = now - self._armed_at
        armed = elapsed >= hold_s and not self._await_release
        progress = min(1.0, elapsed / max(hold_s, 0.01))
        if not armed:
            # Movement during the arming hold must not count as a swipe;
            # otherwise ordinary repositioning would trigger navigation.
            self._anchor = pointer
        dx = pointer.x - self._anchor.x
        dy = pointer.y - self._anchor.y
        threshold = 0.115 / max(0.5, self.settings.nav_sensitivity)

        event: NavEvent | None = None
        cooldown = self.settings.nav_cooldown_ms / 1000.0
        still_cooling = now - self._last_emit < cooldown
        if armed and not still_cooling and max(abs(dx), abs(dy)) >= threshold:
            direction = ""
            action = ""
            if pose == page_pose:
                if abs(dx) >= abs(dy) * 0.75:
                    direction = "left" if dx < 0 else "right"
                    action = NavAction.PAGE_PREV.value if dx < 0 else NavAction.PAGE_NEXT.value
            else:
                if abs(dx) > abs(dy) * 1.05:
                    direction = "left" if dx < 0 else "right"
                    action = NavAction.BACK.value if dx < 0 else NavAction.FORWARD.value
                elif abs(dy) > abs(dx) * 1.05:
                    direction = "up" if dy < 0 else "down"
                    action = NavAction.SCROLL_UP.value if dy < 0 else NavAction.SCROLL_DOWN.value
            if action:
                event = NavEvent(action=action, direction=direction, pose=pose, at=now)
                self._last_emit = now
                self._last_action = action
                self._last_action_at = now
                self._last_direction = direction
                self._await_release = True
                self._cooldown_until = now + cooldown
                self._anchor = pointer
                self._armed_at = now

        hint = "Swipe deliberately in a direction"
        if self._await_release:
            hint = "Release the pose to re-arm"
        elif elapsed < hold_s:
            hint = "Hold to arm navigation"
        elif pose == page_pose:
            hint = "Swipe left / right for previous / next page"
        else:
            hint = "Swipe up, down, left or right"
        telemetry = self._telemetry(progress, hint, now)
        if self._await_release and armed:
            telemetry.armed = True
        return event, telemetry

    def _telemetry(self, progress: float, hint: str, now: float) -> NavTelemetry:
        return NavTelemetry(
            armed=bool(self._armed_at is not None) and progress >= 1.0 and not self._await_release,
            progress=progress,
            pose=self._pose,
            last_action=self._last_action,
            last_action_age_s=max(0.0, now - self._last_action_at)
            if self._last_action_at > -900
            else 99.0,
            hint=hint,
        )


class GestureMapper:
    """Maps poses/hand positions to application-space interaction data."""

    def __init__(self, settings: GestureSettings | None = None) -> None:
        self.settings = settings or GestureSettings()

    def update(self, settings: GestureSettings) -> None:
        self.settings = settings

    def pointer(self, hand: HandObservation | None, gesture: GestureReading | None = None) -> Point:
        if hand is None:
            return Point(0.5, 0.5)
        # The index fingertip is the most direct manipulation point; during a
        # pinch the point just behind the tip is steadier.
        if gesture is not None and gesture.stable == Pose.PINCH.value:
            return hand.index_tip.lerp(hand.landmarks[6], 0.35)
        return hand.pointer

    def nav_pointer(self, hand: HandObservation | None) -> Point:
        if hand is None:
            return Point(0.5, 0.5)
        return hand.palm_center

    def viewport(self, point: Point, margin: float = 0.045) -> Point:
        return Point(map_axis(point.x, margin), map_axis(point.y, margin))

    def role_for_pose(self, pose: str) -> str | None:
        if pose == self.settings.draw_pose:
            return "draw"
        if pose == self.settings.click_pose:
            return "click"
        if pose == self.settings.right_click_pose:
            return "right_click"
        if pose == self.settings.nav_pose:
            return "navigate"
        if pose == self.settings.page_pose:
            return "page"
        return None

    def pose_for_role(self, role: str) -> str:
        return {
            "draw": self.settings.draw_pose,
            "click": self.settings.click_pose,
            "right_click": self.settings.right_click_pose,
            "navigate": self.settings.nav_pose,
            "page": self.settings.page_pose,
        }.get(role, Pose.UNKNOWN.value)

    @staticmethod
    def clamp_point(point: Point) -> Point:
        return Point(clamp(point.x), clamp(point.y))


@dataclass
class MouseUpdate:
    point: Point
    mapped: Point
    pressed: bool
    events: list[dict[str, Any]]
    hint: str = ""


class MouseController:
    """Tool-specific pinch click/drag + two-finger right-click state machine."""

    def __init__(self, settings: GestureSettings | None = None) -> None:
        self.settings = settings or GestureSettings()
        self._pressed = False
        self._right_armed_at: float | None = None
        self._right_sent = False
        self._last_left_event_at = -999.0
        self._last_right_event_at = -999.0

    def update_settings(self, settings: GestureSettings) -> None:
        self.settings = settings

    def reset(self) -> None:
        self._pressed = False
        self._right_armed_at = None
        self._right_sent = False

    def release(self, now: float) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if self._pressed:
            events.append({"kind": "mouse_left_up", "at": now})
            self._pressed = False
        self._right_armed_at = None
        self._right_sent = False
        return events

    def update(
        self,
        gesture: GestureReading | None,
        point: Point,
        now: float,
        *,
        enabled: bool = True,
    ) -> MouseUpdate:
        mapped = point
        if not enabled:
            events = self.release(now)
            return MouseUpdate(point, mapped, False, events, "Mouse control is available in Mouse tool")
        pose = gesture.stable if gesture else Pose.NONE.value
        raw = gesture.raw if gesture else Pose.NONE.value
        events: list[dict[str, Any]] = []
        click_pose = self.settings.click_pose
        right_pose = self.settings.right_click_pose

        # Click/drag starts on the stable click pose.  A tiny minimum interval
        # avoids duplicate events while the stabiliser settles.
        if pose == click_pose and not self._pressed and now - self._last_left_event_at > 0.18:
            self._pressed = True
            self._last_left_event_at = now
            events.append({"kind": "mouse_left_down", "x": point.x, "y": point.y, "at": now})
        elif pose != click_pose and self._pressed:
            self._pressed = False
            events.append({"kind": "mouse_left_up", "x": point.x, "y": point.y, "at": now})

        if pose == right_pose:
            if self._right_armed_at is None:
                self._right_armed_at = now
                self._right_sent = False
            held = now - self._right_armed_at
            if (
                not self._right_sent
                and held >= self.settings.right_click_hold_ms / 1000.0
                and now - self._last_right_event_at > 0.4
            ):
                self._right_sent = True
                self._last_right_event_at = now
                events.append({"kind": "mouse_right_click", "x": point.x, "y": point.y, "at": now})
        else:
            self._right_armed_at = None
            self._right_sent = False

        hint = "Pinch to click, hold to drag"
        if pose == click_pose:
            hint = "Pinching - release to drop"
        elif pose == right_pose:
            hint = "Hold two fingers for right-click"
        elif raw != pose and raw != Pose.NONE.value:
            hint = "Hold the gesture steady"
        return MouseUpdate(point=point, mapped=mapped, pressed=self._pressed, events=events, hint=hint)
