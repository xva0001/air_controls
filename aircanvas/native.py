"""Thin Windows native input bridge.

This module is deliberately isolated from the desktop UI: the shared core
emits semantic events, and only the desktop shell may turn them into operating
system input.  The browser version routes the same events to in-page actions.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from typing import Any

log = logging.getLogger(__name__)


class NativeInputBridge:
    """Windows cursor, click, scroll and navigation-key injection.

    All methods are no-ops on other platforms.  Safety is enforced one level up:
    these methods are called only when the user explicitly enables OS control.
    """

    def __init__(self) -> None:
        self.available = sys.platform.startswith("win")
        self._user32 = ctypes.windll.user32 if self.available else None  # type: ignore[attr-defined]
        self._screen = (0, 0, 1920, 1080)
        if self.available:
            try:
                self._user32.SetProcessDPIAware()
            except Exception:
                pass
            self._screen = self.screen_rect()

    def screen_rect(self) -> tuple[int, int, int, int]:
        if not self.available or self._user32 is None:
            return (0, 0, 1920, 1080)
        try:
            left = self._user32.GetSystemMetrics(76)
            top = self._user32.GetSystemMetrics(77)
            width = self._user32.GetSystemMetrics(78)
            height = self._user32.GetSystemMetrics(79)
            return (left, top, width, height)
        except Exception:
            return (0, 0, 1920, 1080)

    @property
    def screen_size(self) -> tuple[int, int, int, int]:
        return self._screen

    def move_cursor(self, x_norm: float, y_norm: float) -> None:
        if not self.available or self._user32 is None:
            return
        left, top, width, height = self._screen
        x = int(left + max(0.0, min(1.0, x_norm)) * max(1, width - 1))
        y = int(top + max(0.0, min(1.0, y_norm)) * max(1, height - 1))
        self._user32.SetCursorPos(x, y)

    def _mouse(self, flags: int) -> None:
        if not self.available or self._user32 is None:
            return
        self._user32.mouse_event(flags, 0, 0, 0, 0)

    def left_down(self) -> None:
        self._mouse(0x0002)

    def left_up(self) -> None:
        self._mouse(0x0004)

    def right_click(self) -> None:
        if not self.available:
            return
        self._mouse(0x0008)
        self._mouse(0x0010)

    def wheel(self, direction: int, clicks: int = 1) -> None:
        if not self.available or self._user32 is None:
            return
        amount = int(120 * clicks * (1 if direction >= 0 else -1))
        self._user32.mouse_event(0x0800, 0, 0, amount, 0)

    def key(self, vk: int, *, ctrl: bool = False, alt: bool = False) -> None:
        if not self.available or self._user32 is None:
            return
        key_up = 0x0002
        if ctrl:
            self._user32.keybd_event(0x11, 0, 0, 0)
        if alt:
            self._user32.keybd_event(0x12, 0, 0, 0)
        self._user32.keybd_event(vk, 0, 0, 0)
        self._user32.keybd_event(vk, 0, key_up, 0)
        if alt:
            self._user32.keybd_event(0x12, 0, key_up, 0)
        if ctrl:
            self._user32.keybd_event(0x11, 0, key_up, 0)

    def navigate(self, action: str) -> None:
        """Map a semantic navigation action to a Windows shortcut."""
        if action == "scroll_up":
            self.wheel(1, 2)
        elif action == "scroll_down":
            self.wheel(-1, 2)
        elif action == "back":
            self.key(0x25, alt=True)  # Alt+Left
        elif action == "forward":
            self.key(0x27, alt=True)  # Alt+Right
        elif action == "page_prev":
            self.key(0x21)  # Page Up
        elif action == "page_next":
            self.key(0x22)  # Page Down

    def execute_mouse_event(self, event: dict[str, Any]) -> None:
        kind = event.get("kind")
        if kind == "mouse_left_down":
            self.left_down()
        elif kind == "mouse_left_up":
            self.left_up()
        elif kind == "mouse_right_click":
            self.right_click()

    def release_all(self) -> None:
        """Best-effort safety cleanup when the tool or window changes."""
        try:
            self.left_up()
        except Exception:
            pass
