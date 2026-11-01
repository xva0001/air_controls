"""Application configuration shared by the desktop and web front-ends.

All values are plain JSON-friendly primitives so the same configuration can be
persisted by PySide6, sent over a WebSocket and validated by FastAPI.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Any


class Mode(str, Enum):
    SCREEN = "screen"
    MIRROR = "mirror"


class Tool(str, Enum):
    DRAW = "draw"
    NAVIGATE = "navigate"
    MOUSE = "mouse"


class MirrorTool(str, Enum):
    ANNOTATE = "annotate"
    TRACK = "track"


class Pose(str, Enum):
    NONE = "none"
    POINT = "point"
    PINCH = "pinch"
    PEACE = "peace"
    OPEN_PALM = "open_palm"
    FIST = "fist"
    THREE = "three"
    UNKNOWN = "unknown"


DRAW_POSES = [Pose.POINT.value, Pose.PINCH.value, Pose.PEACE.value, Pose.THREE.value]
GESTURE_POSES = [p.value for p in Pose if p not in (Pose.NONE, Pose.UNKNOWN)]

BRUSH_COLORS = [
    "#ff6b57",  # coral
    "#f6c453",  # amber
    "#71d6b5",  # mint
    "#5aa9e6",  # sky
    "#c79bff",  # violet
    "#f4f1e8",  # chalk
]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class GestureSettings:
    """Tunable recognition and mapping parameters.

    The defaults were selected for a 720p webcam at roughly 1.2 m viewing
    distance.  ``*_sensitivity`` scales the corresponding activation threshold:
    higher values make a gesture easier to trigger.
    """

    smoothing: float = 0.55
    pinch_sensitivity: float = 1.0
    stability_frames: int = 5
    nav_sensitivity: float = 1.0
    nav_hold_ms: int = 280
    nav_cooldown_ms: int = 1000
    right_click_hold_ms: int = 420
    cursor_smoothing: float = 0.62
    dominant_hand: str = "auto"  # auto | left | right
    left_handed: bool = False
    draw_pose: str = Pose.POINT.value
    click_pose: str = Pose.PINCH.value
    right_click_pose: str = Pose.PEACE.value
    nav_pose: str = Pose.OPEN_PALM.value
    page_pose: str = Pose.PEACE.value
    show_gesture_trail: bool = True
    selection_hold_ms: int = 260

    def validate(self) -> GestureSettings:
        self.smoothing = _clamp(float(self.smoothing), 0.0, 0.95)
        self.pinch_sensitivity = _clamp(float(self.pinch_sensitivity), 0.55, 1.8)
        self.stability_frames = int(_clamp(int(self.stability_frames), 3, 11))
        self.nav_sensitivity = _clamp(float(self.nav_sensitivity), 0.5, 1.8)
        self.nav_hold_ms = int(_clamp(int(self.nav_hold_ms), 120, 900))
        self.nav_cooldown_ms = int(_clamp(int(self.nav_cooldown_ms), 300, 3000))
        self.right_click_hold_ms = int(_clamp(int(self.right_click_hold_ms), 200, 1500))
        self.cursor_smoothing = _clamp(float(self.cursor_smoothing), 0.0, 0.95)
        self.selection_hold_ms = int(_clamp(int(self.selection_hold_ms), 100, 800))
        if self.dominant_hand not in ("auto", "left", "right"):
            self.dominant_hand = "auto"
        for attr in ("draw_pose", "click_pose", "right_click_pose", "nav_pose", "page_pose"):
            if getattr(self, attr) not in GESTURE_POSES:
                setattr(self, attr, GestureSettings.__dataclass_fields__[attr].default)
        return self


@dataclass
class AppConfig:
    mode: str = Mode.SCREEN.value
    tool: str = Tool.DRAW.value
    mirror_tool: str = MirrorTool.TRACK.value
    auto_shapes: bool = True
    show_landmarks: bool = True
    mirror_camera: bool = True
    show_camera_pip: bool = True
    os_mouse: bool = False
    os_navigation: bool = False
    camera_index: int = 0
    brush_color: str = "#ff6b57"
    brush_width: float = 5.0
    onboarding_done: bool = False
    selection_debug: bool = False
    gesture: GestureSettings = field(default_factory=GestureSettings)

    def validate(self) -> AppConfig:
        if self.mode not in (m.value for m in Mode):
            self.mode = Mode.SCREEN.value
        if self.tool not in (t.value for t in Tool):
            self.tool = Tool.DRAW.value
        if self.mirror_tool not in (t.value for t in MirrorTool):
            self.mirror_tool = MirrorTool.TRACK.value
        self.camera_index = int(_clamp(int(self.camera_index), 0, 9))
        self.brush_width = _clamp(float(self.brush_width), 1.0, 24.0)
        if not isinstance(self.brush_color, str) or not self.brush_color.startswith("#"):
            self.brush_color = "#ff6b57"
        if len(self.brush_color) != 7:
            self.brush_color = "#ff6b57"
        self.gesture.validate()
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> AppConfig:
        data = dict(data or {})
        gesture_data = data.pop("gesture", {}) or {}
        cfg = cls()
        for f in fields(cls):
            if f.name == "gesture":
                continue
            if f.name in data:
                setattr(cfg, f.name, data[f.name])
        gesture = GestureSettings()
        for f in fields(GestureSettings):
            if f.name in gesture_data:
                setattr(gesture, f.name, gesture_data[f.name])
        cfg.gesture = gesture
        return cfg.validate()

    def apply_patch(self, patch: Mapping[str, Any]) -> AppConfig:
        """Apply a partial update, including nested gesture settings."""
        data = self.to_dict()
        for key, value in patch.items():
            if key == "gesture" and isinstance(value, Mapping):
                data["gesture"].update(value)
            elif key in data:
                data[key] = value
        updated = AppConfig.from_dict(data)
        self.__dict__.update(copy.deepcopy(updated.__dict__))
        return self.validate()

    def clone(self) -> AppConfig:
        return AppConfig.from_dict(self.to_dict())


def default_config_path() -> Path:
    """Return a per-user configuration path.

    ``AIRCANVAS_CONFIG_DIR`` is useful for tests and portable deployments.
    """
    override = os.environ.get("AIRCANVAS_CONFIG_DIR")
    if override:
        return Path(override) / "config.json"
    base = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "AirCanvas"
    return base / "config.json"


def load_config(path: Path | None = None) -> AppConfig:
    target = path or default_config_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        return AppConfig.from_dict(raw)
    except (OSError, ValueError, TypeError):
        return AppConfig()


def save_config(config: AppConfig, path: Path | None = None) -> bool:
    target = path or default_config_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(config.to_dict(), indent=2)
        # Atomic write prevents a truncated profile after a crash.
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=target.parent, delete=False, suffix=".tmp"
        ) as handle:
            handle.write(payload)
            temp_name = handle.name
        Path(temp_name).replace(target)
        return True
    except OSError:
        return False
