"""PySide6 desktop interface for AirCanvas."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from ..camera import CameraPipeline, diagnose_cameras
from ..config import BRUSH_COLORS, Pose, save_config
from ..hand_models import backend_status
from ..demo import DemoEngine, DemoPipeline
from ..models import GESTURE_LABELS
from ..native import NativeInputBridge
from ..session import InteractionSession
from .dialogs import HelpDialog, OnboardingDialog, confirm_os_control
from .overlay import OverlayController
from .stage import StageWidget
from .theme import (
    ACCENT,
    AMBER,
    BG,
    BORDER,
    BORDER_SOFT,
    DANGER,
    FAINT,
    MINT,
    MUTED,
    SURFACE,
    SURFACE_RAISED,
    TEXT,
    TEXT_DIM,
)
from .widgets import (
    ColorSwatch,
    ComboRow,
    HandPreview,
    IconButton,
    LogoMark,
    NavButton,
    Pill,
    SectionHeader,
    SegmentControl,
    SettingRow,
    SliderRow,
    Toast,
    hline,
)

SCREEN_TOOLS = [
    ("draw", "pen", "Draw", "D", "Point and draw on the canvas."),
    ("navigate", "navigate", "Navigate", "N", "Hold an open palm, then swipe with intent."),
    ("mouse", "cursor", "Mouse", "M", "Pinch to click, hold to drag, two fingers to right-click."),
]
MIRROR_TOOLS = [
    ("annotate", "pen", "Annotate", "A", "Draw directly over the live feed."),
    ("track", "track", "Track", "T", "Trace a loop around an object, then hold."),
]
GESTURE_OPTIONS = [
    (Pose.POINT.value, "Point"),
    (Pose.PINCH.value, "Pinch"),
    (Pose.PEACE.value, "Two fingers"),
    (Pose.OPEN_PALM.value, "Open palm"),
    (Pose.THREE.value, "Three fingers"),
    (Pose.FIST.value, "Fist"),
]


class TitleBar(QWidget):
    def __init__(self, window: QMainWindow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self.setFixedHeight(64)
        self.setAccessibleName("AirCanvas title bar")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None:
                handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if self._window.isMaximized():
                self._window.showNormal()
            else:
                self._window.showMaximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(BG))
        painter.drawRect(self.rect())
        painter.setPen(QColor(BORDER_SOFT))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


class CameraNotice(QFrame):
    retry_requested = Signal()
    demo_requested = Signal()
    diagnostics_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CameraNotice")
        self.setStyleSheet(
            f"QFrame#CameraNotice {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:14px; }}"
        )
        self.setFixedWidth(410)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        top = QHBoxLayout()
        dot = QLabel("●")
        dot.setStyleSheet(f"color:{AMBER}; font-size:10px;")
        top.addWidget(dot)
        title = QLabel("Camera is not active")
        title.setStyleSheet(f"color:{TEXT}; font-size:12px; font-weight:700;")
        top.addWidget(title)
        top.addStretch(1)
        layout.addLayout(top)
        self.body = QLabel("Check privacy permissions, or explore with a labelled simulated feed.")
        self.body.setWordWrap(True)
        self.body.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        layout.addWidget(self.body)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        retry = QPushButton("Retry camera")
        retry.clicked.connect(self.retry_requested)
        diagnose = QPushButton("Diagnose")
        diagnose.setToolTip("Probe camera indices and OpenCV backends")
        diagnose.clicked.connect(self.diagnostics_requested)
        demo = QPushButton("Use simulated feed")
        demo.setObjectName("Primary")
        demo.clicked.connect(self.demo_requested)
        buttons.addStretch(1)
        buttons.addWidget(diagnose)
        buttons.addWidget(retry)
        buttons.addWidget(demo)
        layout.addLayout(buttons)

    def set_message(self, message: str) -> None:
        if message:
            self.body.setText(message)


class Footer(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(34)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 10, 0)
        layout.setSpacing(10)
        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color:{MINT}; font-size:9px;")
        layout.addWidget(self.dot)
        self.message = QLabel("Ready")
        self.message.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")
        layout.addWidget(self.message)
        layout.addStretch(1)
        self.center = QLabel("1 / 2 mode  ·  D draw  ·  N navigate  ·  M mouse  ·  Ctrl+Z undo")
        self.center.setStyleSheet(f"color:{FAINT}; font-size:9px;")
        layout.addWidget(self.center)
        layout.addStretch(1)
        self.stats = QLabel("-- fps  ·  -- ms")
        self.stats.setStyleSheet(f"color:{FAINT}; font-size:9px; font-family:'Cascadia Mono','Consolas';")
        layout.addWidget(self.stats)
        grip = QSizeGrip(self)
        grip.setFixedSize(14, 14)
        layout.addWidget(grip, 0, Qt.AlignmentFlag.AlignBottom)
        self.setStyleSheet(f"background:{BG}; border-top:1px solid {BORDER_SOFT};")

    def set_message(self, message: str, tone: str = MINT) -> None:
        self.message.setText(message)
        self.dot.setStyleSheet(f"color:{tone}; font-size:9px;")

    def set_stats(self, fps: float, latency: float, label: str = "") -> None:
        self.stats.setText(f"{fps:4.1f} fps  ·  {label or f'{latency:4.1f} ms'}")


class MainWindow(QMainWindow):
    def __init__(
        self,
        session: InteractionSession,
        *,
        config_path: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.config_path = config_path
        self._pipeline: Any = None
        self._source = "none"
        self._snapshot: dict[str, Any] = session.snapshot()
        self._last_frame_rgb: np.ndarray | None = None
        self._last_seq = -1
        self._native = NativeInputBridge()
        self._last_toast_message = ""
        self._last_track_fingerprint: tuple = ()
        self._latest_camera_status = "idle"
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(450)
        self._save_timer.timeout.connect(self._persist_now)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(33)
        self._poll_timer.timeout.connect(self._poll_pipeline)

        self.setWindowTitle("AirCanvas — Gesture Interaction Studio")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.resize(1480, 920)
        self.setMinimumSize(1200, 780)
        self._build_ui()
        self._bind_shortcuts()
        self._toast = Toast(self)
        self._overlay = OverlayController(self)
        self._overlay.set_actions(self._undo, self._clear_canvas)
        self._sync_mode_ui(self.session.config.mode, initial=True)
        self._sync_tool_ui(initial=True)
        self._sync_settings_from_config()
        self._apply_handedness_layout()
        self._poll_timer.start()

    # ------------------------------------------------------------------ layout
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.title_bar = TitleBar(self)
        self._build_titlebar()
        root_layout.addWidget(self.title_bar)
        content = QWidget()
        self._content_layout = QHBoxLayout(content)
        self._content_layout.setContentsMargins(14, 10, 14, 8)
        self._content_layout.setSpacing(12)
        self.sidebar = self._build_sidebar()
        self.center = self._build_center()
        self.inspector = self._build_inspector()
        self._content_layout.addWidget(self.sidebar)
        self._content_layout.addWidget(self.center, 1)
        self._content_layout.addWidget(self.inspector)
        root_layout.addWidget(content, 1)
        self.footer = Footer()
        root_layout.addWidget(self.footer)
        self.camera_notice = CameraNotice(self.stage)
        self.camera_notice.retry_requested.connect(self.start_camera)
        self.camera_notice.demo_requested.connect(self.start_demo)
        self.camera_notice.diagnostics_requested.connect(self._show_camera_diagnostics)
        self.camera_notice.hide()

    def _build_titlebar(self) -> None:
        layout = QHBoxLayout(self.title_bar)
        layout.setContentsMargins(18, 0, 10, 0)
        layout.setSpacing(11)
        layout.addWidget(LogoMark(36))
        brand_box = QVBoxLayout()
        brand_box.setSpacing(-2)
        brand = QLabel("AirCanvas")
        brand.setStyleSheet(f"color:{TEXT}; font-size:15px; font-weight:800; letter-spacing:0.2px;")
        tagline = QLabel("GESTURE STUDIO")
        tagline.setStyleSheet(f"color:{FAINT}; font-size:8px; font-weight:700; letter-spacing:2.0px;")
        brand_box.addWidget(brand)
        brand_box.addWidget(tagline)
        layout.addLayout(brand_box)
        layout.addSpacing(24)
        self.mode_segment = SegmentControl([("screen", "Screen"), ("mirror", "Mirror")], value=self.session.config.mode)
        self.mode_segment.changed.connect(self._on_mode_changed)
        layout.addWidget(self.mode_segment)
        layout.addStretch(1)
        self.camera_pill = Pill("CAMERA OFF", tone=FAINT)
        layout.addWidget(self.camera_pill)
        self.top_gesture = Pill("NO HAND", tone=FAINT)
        layout.addWidget(self.top_gesture)
        layout.addSpacing(4)
        self.help_button = IconButton("help", tooltip="Help and gestures (F1)", size=34)
        self.help_button.clicked.connect(self.show_help)
        layout.addWidget(self.help_button)
        layout.addSpacing(5)
        separator = QFrame()
        separator.setFixedSize(1, 22)
        separator.setStyleSheet(f"background:{BORDER};")
        layout.addWidget(separator)
        self.min_button = IconButton("minimize", tooltip="Minimise", size=32, tone=MUTED)
        self.min_button.clicked.connect(self.showMinimized)
        layout.addWidget(self.min_button)
        self.max_button = IconButton("maximize", tooltip="Maximise", size=32, tone=MUTED)
        self.max_button.clicked.connect(self._toggle_max)
        layout.addWidget(self.max_button)
        self.close_button = IconButton("close", tooltip="Close AirCanvas", size=32, tone=MUTED)
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button)

    def _build_sidebar(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(228)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(9)
        eyebrow = QLabel("WORKSPACE")
        eyebrow.setObjectName("Eyebrow")
        layout.addWidget(eyebrow)
        title = QLabel("Tools")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        self.tool_layout = QVBoxLayout()
        self.tool_layout.setContentsMargins(0, 2, 0, 0)
        self.tool_layout.setSpacing(3)
        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)
        self._tool_buttons: dict[str, NavButton] = {}
        for key, icon, label, shortcut, description in SCREEN_TOOLS + MIRROR_TOOLS:
            button = NavButton(icon, label, shortcut, description=description)
            button.clicked.connect(lambda checked=False, k=key: self._on_tool_clicked(k))
            self._tool_group.addButton(button)
            self._tool_buttons[key] = button
            self.tool_layout.addWidget(button)
        layout.addLayout(self.tool_layout)
        self.tool_hint = QLabel("")
        self.tool_hint.setWordWrap(True)
        self.tool_hint.setStyleSheet(f"color:{FAINT}; font-size:9px; padding:4px 4px 0 4px;")
        layout.addWidget(self.tool_hint)
        layout.addWidget(hline())
        # Brush controls.
        self.brush_container = QWidget()
        brush = QVBoxLayout(self.brush_container)
        brush.setContentsMargins(0, 0, 0, 0)
        brush.setSpacing(7)
        brush_head = QHBoxLayout()
        brush_head.setSpacing(4)
        brush_label = QLabel("BRUSH")
        brush_label.setObjectName("Eyebrow")
        brush_head.addWidget(brush_label)
        brush_head.addStretch(1)
        self.color_value = QLabel(self.session.config.brush_color.upper())
        self.color_value.setStyleSheet(f"color:{FAINT}; font-size:9px; font-family:'Cascadia Mono','Consolas';")
        brush_head.addWidget(self.color_value)
        brush.addLayout(brush_head)
        colors = QHBoxLayout()
        colors.setSpacing(5)
        self._swatch_group = QButtonGroup(self)
        self._swatches: dict[str, ColorSwatch] = {}
        for color in BRUSH_COLORS:
            swatch = ColorSwatch(color, 26)
            swatch.setChecked(color.lower() == self.session.config.brush_color.lower())
            swatch.clicked.connect(lambda checked=False, c=color: self._on_color(c))
            self._swatch_group.addButton(swatch)
            self._swatches[color] = swatch
            colors.addWidget(swatch)
        colors.addStretch(1)
        brush.addLayout(colors)
        self.width_slider = SliderRow(
            "Brush size",
            minimum=2,
            maximum=18,
            value=int(round(self.session.config.brush_width)),
            suffix=" px",
        )
        self.width_slider.value_changed.connect(self._on_brush_width)
        brush.addWidget(self.width_slider)
        layout.addWidget(self.brush_container)
        self.auto_shapes_row = SettingRow(
            "Smart shapes",
            "Correct deliberate circles into clean vector circles.",
            checked=self.session.config.auto_shapes,
        )
        self.auto_shapes_row.toggled.connect(self._on_auto_shapes)
        layout.addWidget(self.auto_shapes_row)
        layout.addWidget(hline())
        # Environment switch.
        self.env_container = QWidget()
        env = QVBoxLayout(self.env_container)
        env.setContentsMargins(0, 0, 0, 0)
        env.setSpacing(6)
        env_head = QLabel("DRAWING SURFACE")
        env_head.setObjectName("Eyebrow")
        env.addWidget(env_head)
        self.env_segment = SegmentControl([("canvas", "Canvas"), ("overlay", "Desktop")], value="canvas")
        self.env_segment.changed.connect(self._on_environment_changed)
        env.addWidget(self.env_segment)
        env_caption = QLabel("Desktop overlay is click-through and stays above other apps.")
        env_caption.setWordWrap(True)
        env_caption.setStyleSheet(f"color:{FAINT}; font-size:9px;")
        env.addWidget(env_caption)
        layout.addWidget(self.env_container)
        layout.addWidget(hline())
        actions_label = QLabel("QUICK ACTIONS")
        actions_label.setObjectName("Eyebrow")
        layout.addWidget(actions_label)
        actions = QHBoxLayout()
        actions.setSpacing(2)
        self.undo_button = IconButton("undo", tooltip="Undo (Ctrl+Z)", size=38, icon_size=18, tone=TEXT_DIM)
        self.undo_button.clicked.connect(self._undo)
        self.redo_button = IconButton("redo", tooltip="Redo (Ctrl+Shift+Z)", size=38, icon_size=18, tone=TEXT_DIM)
        self.redo_button.clicked.connect(self._redo)
        self.clear_button = IconButton("trash", tooltip="Clear canvas (reversible with Undo)", size=38, icon_size=18, tone=TEXT_DIM)
        self.clear_button.clicked.connect(self._clear_canvas)
        self.save_button = IconButton("download", tooltip="Export artwork (Ctrl+S)", size=38, icon_size=18, tone=TEXT_DIM)
        self.save_button.clicked.connect(self._save_png)
        for button, caption in (
            (self.undo_button, "Undo"),
            (self.redo_button, "Redo"),
            (self.clear_button, "Clear"),
            (self.save_button, "Save"),
        ):
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(1)
            cell_layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
            text = QLabel(caption)
            text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text.setStyleSheet(f"color:{FAINT}; font-size:8px;")
            cell_layout.addWidget(text)
            actions.addWidget(cell, 1)
        layout.addLayout(actions)
        layout.addStretch(1)
        tip_box = QFrame()
        tip_box.setStyleSheet(
            f"background:{SURFACE_RAISED}; border:1px solid {BORDER_SOFT}; border-radius:10px;"
        )
        tip_layout = QVBoxLayout(tip_box)
        tip_layout.setContentsMargins(11, 9, 11, 9)
        tip_layout.setSpacing(3)
        tip_title = QLabel("HOLD STEADY")
        tip_title.setStyleSheet(f"color:{MINT}; font-size:8px; font-weight:800; letter-spacing:1.3px;")
        tip_layout.addWidget(tip_title)
        tip_body = QLabel("Pose stabilisation prevents accidental strokes and clicks. Release a pose to re-arm.")
        tip_body.setWordWrap(True)
        tip_body.setStyleSheet(f"color:{MUTED}; font-size:9px;")
        tip_layout.addWidget(tip_body)
        layout.addWidget(tip_box)
        return card

    def _build_center(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        header = QWidget()
        head_layout = QHBoxLayout(header)
        head_layout.setContentsMargins(4, 1, 4, 0)
        head_layout.setSpacing(8)
        text = QVBoxLayout()
        text.setSpacing(1)
        self.center_eyebrow = QLabel("SCREEN MODE")
        self.center_eyebrow.setObjectName("Eyebrow")
        text.addWidget(self.center_eyebrow)
        self.center_title = QLabel("Built-in canvas")
        self.center_title.setStyleSheet(f"color:{TEXT}; font-size:16px; font-weight:700;")
        text.addWidget(self.center_title)
        self.center_desc = QLabel("Point to draw. Smart shapes can clean up circles.")
        self.center_desc.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        text.addWidget(self.center_desc)
        head_layout.addLayout(text)
        head_layout.addStretch(1)
        self.auto_pill = Pill("SMART SHAPES", tone=MINT)
        head_layout.addWidget(self.auto_pill)
        self.recognition_pill = Pill("IDLE", tone=FAINT)
        head_layout.addWidget(self.recognition_pill)
        layout.addWidget(header)
        self.stage = StageWidget()
        self.stage.manual_begin.connect(self._manual_begin)
        self.stage.manual_move.connect(self._manual_move)
        self.stage.manual_end.connect(self._manual_end)
        layout.addWidget(self.stage, 1)
        return container

    def _build_inspector(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(326)
        wrapper = QVBoxLayout(card)
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(14, 14, 10, 16)
        layout.setSpacing(9)
        # Live hand card.
        layout.addWidget(SectionHeader("LIVE INPUT", "Hand & gesture"))
        self.hand_preview = HandPreview()
        layout.addWidget(self.hand_preview, 0)
        gesture_row = QHBoxLayout()
        gesture_row.setContentsMargins(2, 0, 2, 0)
        gesture_row.setSpacing(6)
        self.gesture_name = QLabel("No hand")
        self.gesture_name.setStyleSheet(f"color:{TEXT}; font-size:17px; font-weight:700;")
        gesture_row.addWidget(self.gesture_name)
        gesture_row.addStretch(1)
        self.confidence_pill = Pill("CONF --", tone=FAINT)
        gesture_row.addWidget(self.confidence_pill)
        layout.addLayout(gesture_row)
        metrics = QHBoxLayout()
        metrics.setSpacing(10)
        metrics.setContentsMargins(2, 0, 2, 2)
        self.metric_fps = self._metric(metrics, "FPS", "--")
        self.metric_latency = self._metric(metrics, "INFERENCE", "-- ms")
        self.metric_pinch = self._metric(metrics, "PINCH", "--")
        layout.addLayout(metrics)
        layout.addWidget(hline())
        # Mappings.
        layout.addWidget(SectionHeader("MAPPING", "Gesture bindings"))
        mapping_grid = QGridLayout()
        mapping_grid.setContentsMargins(0, 0, 0, 0)
        mapping_grid.setHorizontalSpacing(7)
        mapping_grid.setVerticalSpacing(6)
        self.mapping_combos: dict[str, QComboBox] = {}
        mapping_defs = [
            ("draw_pose", "Draw / annotate", 0, 0),
            ("click_pose", "Left click", 1, 0),
            ("right_click_pose", "Right click", 0, 1),
            ("nav_pose", "Navigation arm", 1, 1),
            ("page_pose", "Page swipe", 2, 0),
        ]
        for key, label, row, col in mapping_defs:
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(3)
            caption = QLabel(label)
            caption.setStyleSheet(f"color:{MUTED}; font-size:9px;")
            combo = QComboBox()
            for value, text in GESTURE_OPTIONS:
                combo.addItem(text, value)
            current = getattr(self.session.config.gesture, key)
            idx = combo.findData(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.setAccessibleName(label)
            combo.currentIndexChanged.connect(
                lambda index, k=key, c=combo: self._on_mapping_changed(k, str(c.itemData(index)))
            )
            self.mapping_combos[key] = combo
            cell_layout.addWidget(caption)
            cell_layout.addWidget(combo)
            mapping_grid.addWidget(cell, row, col)
        mapping_grid.setColumnStretch(0, 1)
        mapping_grid.setColumnStretch(1, 1)
        layout.addLayout(mapping_grid)
        layout.addWidget(hline())
        # Tuning.
        layout.addWidget(SectionHeader("TUNING", "Sensitivity & stability"))
        self.pinch_slider = SliderRow("Pinch sensitivity", minimum=55, maximum=180, value=int(self.session.config.gesture.pinch_sensitivity * 100), suffix="%")
        self.pinch_slider.value_changed.connect(self._on_pinch_sensitivity)
        layout.addWidget(self.pinch_slider)
        self.smooth_slider = SliderRow("Pointer smoothing", minimum=0, maximum=95, value=int(self.session.config.gesture.cursor_smoothing * 100), suffix="%")
        self.smooth_slider.value_changed.connect(self._on_cursor_smoothing)
        layout.addWidget(self.smooth_slider)
        self.hold_slider = SliderRow("Navigation hold", minimum=120, maximum=900, value=int(self.session.config.gesture.nav_hold_ms), suffix=" ms")
        self.hold_slider.value_changed.connect(self._on_nav_hold)
        layout.addWidget(self.hold_slider)
        self.stability_slider = SliderRow("Pose stability", minimum=3, maximum=11, value=int(self.session.config.gesture.stability_frames), suffix=" frames")
        self.stability_slider.value_changed.connect(self._on_stability)
        layout.addWidget(self.stability_slider)
        layout.addWidget(hline())
        # Tracking.
        self.tracking_section = QWidget()
        tracking = QVBoxLayout(self.tracking_section)
        tracking.setContentsMargins(0, 0, 0, 0)
        tracking.setSpacing(6)
        track_head = QHBoxLayout()
        track_head.setContentsMargins(0, 0, 0, 0)
        track_titles = QVBoxLayout()
        track_titles.setSpacing(1)
        track_eye = QLabel("MIRROR MODE")
        track_eye.setObjectName("Eyebrow")
        track_title = QLabel("Tracked objects")
        track_title.setObjectName("SectionTitle")
        track_titles.addWidget(track_eye)
        track_titles.addWidget(track_title)
        track_head.addLayout(track_titles)
        track_head.addStretch(1)
        clear_tracks = IconButton("trash", tooltip="Remove all tracking markers", size=28, icon_size=15)
        clear_tracks.clicked.connect(self._clear_tracks)
        track_head.addWidget(clear_tracks)
        tracking.addLayout(track_head)
        self.track_list = QVBoxLayout()
        self.track_list.setSpacing(4)
        tracking.addLayout(self.track_list)
        self.track_empty = QLabel("No objects tracked. Choose Track and draw a loop around an object.")
        self.track_empty.setWordWrap(True)
        self.track_empty.setStyleSheet(f"color:{FAINT}; font-size:9px; padding:5px 2px;")
        self.track_list.addWidget(self.track_empty)
        tracking.addWidget(hline())
        layout.addWidget(self.tracking_section)
        self.tracking_section.hide()
        layout.addWidget(hline())
        self.inspector_layout = layout
        # System.
        layout.addWidget(SectionHeader("SYSTEM", "Camera, model & control"))
        self.mirror_camera_row = SettingRow("Mirror camera", "Selfie view; landmarks share the mirrored origin.", checked=self.session.config.mirror_camera)
        self.mirror_camera_row.toggled.connect(self._on_mirror_camera)
        layout.addWidget(self.mirror_camera_row)
        self.landmark_row = SettingRow("Show landmarks", "Skeleton overlay on the camera feed.", checked=self.session.config.show_landmarks)
        self.landmark_row.toggled.connect(self._on_landmarks)
        layout.addWidget(self.landmark_row)
        self.handed_row = SettingRow("Left-handed layout", "Move the control inspector to the left side.", checked=self.session.config.gesture.left_handed)
        self.handed_row.toggled.connect(self._on_left_handed)
        layout.addWidget(self.handed_row)
        self.os_mouse_row = SettingRow("Control OS mouse", "Requires explicit consent. Pinch acts as a real click.", checked=self.session.config.os_mouse)
        self.os_mouse_row.toggled.connect(self._on_os_mouse)
        layout.addWidget(self.os_mouse_row)
        self.os_nav_row = SettingRow("System navigation", "Send scroll/back/page shortcuts to the focused app.", checked=self.session.config.os_navigation)
        self.os_nav_row.toggled.connect(self._on_os_navigation)
        layout.addWidget(self.os_nav_row)
        self.dominant_combo = ComboRow("Dominant hand", [("auto", "Auto detect"), ("right", "Right hand"), ("left", "Left hand")], value=self.session.config.gesture.dominant_hand)
        self.dominant_combo.changed.connect(self._on_dominant_hand)
        layout.addWidget(self.dominant_combo)
        self.camera_combo = ComboRow("Camera index", [(str(i), f"Camera {i}") for i in range(4)], value=str(self.session.config.camera_index))
        self.camera_combo.changed.connect(self._on_camera_index)
        layout.addWidget(self.camera_combo)
        self.backend_combo = ComboRow(
            "Camera backend",
            [
                ("auto", "Auto (MSMF → DSHOW)"),
                ("msmf", "Media Foundation"),
                ("dshow", "DirectShow"),
                ("any", "OpenCV auto"),
            ],
            value=self.session.config.camera_backend,
        )
        self.backend_combo.changed.connect(self._on_camera_backend)
        layout.addWidget(self.backend_combo)
        self.hand_model_combo = ComboRow(
            "Hand landmark model",
            [
                ("mediapipe", "MediaPipe Hands"),
                ("rtmpose", "RTMPose-Hand"),
                ("yolo_pose", "YOLO Pose (21-kp)"),
            ],
            value=self.session.config.hand_backend,
        )
        self.hand_model_combo.changed.connect(self._on_hand_model)
        layout.addWidget(self.hand_model_combo)
        model_row = QHBoxLayout()
        model_row.setSpacing(6)
        self.hand_model_path_label = QLabel()
        self.hand_model_path_label.setObjectName("handModelPath")
        self.hand_model_path_label.setMaximumWidth(190)
        self.hand_model_path_label.setToolTip("Optional model path; MediaPipe uses the bundled model when empty.")
        choose_model = QPushButton("Choose model…")
        choose_model.clicked.connect(self._choose_hand_model)
        model_row.addWidget(self.hand_model_path_label, 1)
        model_row.addWidget(choose_model)
        layout.addLayout(model_row)
        self.hand_model_status = QLabel()
        self.hand_model_status.setObjectName("handModelStatus")
        self.hand_model_status.setWordWrap(True)
        layout.addWidget(self.hand_model_status)
        self._update_hand_model_ui()
        source_row = QHBoxLayout()
        source_row.setSpacing(6)
        webcam = QPushButton("Use webcam")
        webcam.clicked.connect(self.start_camera)
        demo = QPushButton("Simulated feed")
        demo.clicked.connect(self.start_demo)
        source_row.addWidget(webcam)
        source_row.addWidget(demo)
        layout.addLayout(source_row)
        layout.addStretch(1)
        scroll.setWidget(inner)
        wrapper.addWidget(scroll)
        return card

    def _metric(self, layout: QHBoxLayout, label: str, value: str) -> QLabel:
        cell = QWidget()
        cell.setStyleSheet(f"background:{SURFACE_RAISED}; border:1px solid {BORDER_SOFT}; border-radius:9px;")
        cell_layout = QVBoxLayout(cell)
        cell_layout.setContentsMargins(9, 6, 9, 6)
        cell_layout.setSpacing(0)
        value_label = QLabel(value)
        value_label.setStyleSheet(f"color:{TEXT}; font-size:13px; font-weight:600; font-family:'Cascadia Mono','Consolas';")
        caption = QLabel(label)
        caption.setStyleSheet(f"color:{FAINT}; font-size:7px; font-weight:700; letter-spacing:1.0px;")
        cell_layout.addWidget(value_label)
        cell_layout.addWidget(caption)
        layout.addWidget(cell, 1)
        return value_label

    # ------------------------------------------------------------------ shortcuts
    def _bind_shortcuts(self) -> None:
        bindings = [
            ("1", lambda: self._set_mode("screen")),
            ("2", lambda: self._set_mode("mirror")),
            ("D", lambda: self._on_tool_clicked("draw")),
            ("N", lambda: self._on_tool_clicked("navigate")),
            ("M", lambda: self._on_tool_clicked("mouse")),
            ("A", lambda: self._on_tool_clicked("annotate")),
            ("T", lambda: self._on_tool_clicked("track")),
            ("Ctrl+Z", self._undo),
            ("Ctrl+Shift+Z", self._redo),
            ("Ctrl+Y", self._redo),
            ("Ctrl+S", self._save_png),
            ("F1", self.show_help),
            ("Esc", self._escape),
        ]
        self._shortcuts: list[QShortcut] = []
        for sequence, callback in bindings:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _escape(self) -> None:
        if self._overlay.visible:
            self._overlay.hide()
            self.env_segment.set_value("canvas")
        elif hasattr(self, "_toast"):
            self._toast.hide()

    # ------------------------------------------------------------------ runtime
    def start_initial(self, *, demo: bool = False, show_onboarding: bool = True) -> None:
        self.show()
        self.raise_()
        if show_onboarding and not self.session.config.onboarding_done:
            QTimer.singleShot(220, self.show_onboarding)
        else:
            QTimer.singleShot(180, self.start_demo if demo else self.start_camera)

    def show_onboarding(self) -> None:
        dialog = OnboardingDialog(self)
        dialog.camera_requested.connect(self.start_camera)
        dialog.demo_requested.connect(self.start_demo)
        result = dialog.exec()
        if not self.session.config.onboarding_done:
            self.session.config.onboarding_done = True
            self._schedule_save()
        if result == dialog.DialogCode.Rejected:
            self.camera_notice.show()
            self._position_camera_notice()

    def show_help(self) -> None:
        dialog = HelpDialog(self)
        dialog.exec()

    def start_camera(self) -> None:
        self._stop_pipeline()
        self._source = "camera"
        self.session.set_camera_status("starting", "Opening camera...", source="opencv")
        self.footer.set_message("Opening camera...", AMBER)
        self.camera_notice.set_message("Opening camera and loading the hand model...")
        self.camera_notice.show()
        self._position_camera_notice()
        pipeline = CameraPipeline(
            self.session,
            camera_index=self.session.config.camera_index,
            backend=self.session.config.camera_backend,
        )
        self._pipeline = pipeline
        if not pipeline.start():
            self.footer.set_message("Camera unavailable - use the simulated feed", AMBER)
            self.camera_notice.set_message(
                self.session.snapshot().get("camera", {}).get("message")
                or "No camera was found. Check privacy settings or try the simulated feed."
            )
            self.camera_notice.show()
        else:
            self._snapshot = self.session.snapshot()
        self._last_seq = -1

    def start_demo(self) -> None:
        self._stop_pipeline()
        self._source = "demo"
        self.env_segment.set_value("canvas")
        self.camera_notice.hide()
        self.footer.set_message("Simulated feed - labelled, local and deterministic", AMBER)
        pipeline = DemoPipeline(self.session)
        self._pipeline = pipeline
        pipeline.start()
        self._last_seq = -1
        self._toast.show_message("Simulated camera active. Landmarks drive the real interaction core.", "warning", 3200)

    def _stop_pipeline(self) -> None:
        self._native.release_all()
        if self._pipeline is not None:
            try:
                self._pipeline.stop()
            except Exception:
                pass
            self._pipeline = None
        self._source = "none"

    def _poll_pipeline(self) -> None:
        if self._overlay is not None and self._overlay.visible:
            self._overlay.update_snapshot(self._snapshot)
            if self.env_segment.value == "overlay" and not self._overlay.visible:
                self.env_segment.set_value("canvas")
        if self._pipeline is None:
            return
        rgb, snapshot, events, seq = self._pipeline.poll()
        if snapshot is None:
            return
        if seq == self._last_seq:
            self._sync_light(snapshot)
            return
        self._last_seq = seq
        self._snapshot = snapshot
        if rgb is not None:
            self._last_frame_rgb = rgb
            image = QImage(
                rgb.data,
                rgb.shape[1],
                rgb.shape[0],
                rgb.strides[0],
                QImage.Format.Format_RGB888,
            ).copy()
            self.stage.set_frame(image)
        self._process_native_events(events)
        self._apply_snapshot(snapshot)

    def _apply_snapshot(self, snapshot: dict[str, Any]) -> None:
        self._snapshot = snapshot
        self.stage.set_snapshot(snapshot)
        hand = snapshot.get("hand", {})
        gesture = snapshot.get("gesture", {})
        self.hand_preview.set_data(hand, gesture)
        stable = str(gesture.get("stable", "none"))
        label = GESTURE_LABELS.get(stable, stable.replace("_", " ").title())
        self.gesture_name.setText(label if hand.get("visible") else "No hand")
        confidence = float(gesture.get("confidence", 0.0))
        if hand.get("visible"):
            tone = MINT if confidence >= 0.75 else AMBER
            self.confidence_pill.set_text(f"CONF {int(confidence * 100)}%", tone)
            self.top_gesture.set_text(label.upper(), tone)
        else:
            self.confidence_pill.set_text("CONF --", FAINT)
            self.top_gesture.set_text("NO HAND", FAINT)
        stats = snapshot.get("stats", {})
        fps = float(stats.get("fps", 0.0))
        latency = float(stats.get("recognition_ms", 0.0))
        camera_data = snapshot.get("camera", {})
        demo_feed = camera_data.get("status") == "demo" or camera_data.get("source") == "demo"
        self.metric_fps.setText(f"{fps:.1f}")
        self.metric_latency.setText("—" if demo_feed else f"{latency:.1f} ms")
        pinch = float(gesture.get("pinch_ratio", 0.0))
        self.metric_pinch.setText(f"{pinch:.2f}" if hand.get("visible") else "--")
        self.footer.set_stats(fps, latency, "simulated" if demo_feed else "")
        self.footer.set_message(
            str(snapshot.get("status", {}).get("message", "Ready")),
            MINT if hand.get("visible") else MUTED,
        )
        self.undo_button.setEnabled(bool(snapshot.get("drawing", {}).get("can_undo")))
        self.redo_button.setEnabled(bool(snapshot.get("drawing", {}).get("can_redo")))
        self.clear_button.setEnabled(bool(snapshot.get("drawing", {}).get("strokes")))
        self.auto_pill.set_text("SMART SHAPES ON" if self.session.config.auto_shapes else "SMART SHAPES OFF", MINT if self.session.config.auto_shapes else FAINT)
        self.recognition_pill.set_text(
            "TRACKING" if snapshot.get("mode") == "mirror" and snapshot.get("tracks") else "LIVE",
            MINT if snapshot.get("mode") == "mirror" and snapshot.get("tracks") else ACCENT,
        )
        camera = snapshot.get("camera", {})
        status = str(camera.get("status", "idle"))
        self._latest_camera_status = status
        if status == "live":
            self.camera_pill.set_text("CAMERA LIVE", MINT)
            self.camera_notice.hide()
        elif status == "demo":
            self.camera_pill.set_text("SIMULATED", AMBER)
            self.camera_notice.hide()
        elif status == "error":
            self.camera_pill.set_text("CAMERA ERROR", DANGER)
            self.camera_notice.set_message(str(camera.get("message", "")))
            self.camera_notice.show()
            self._position_camera_notice()
        elif status == "starting":
            self.camera_pill.set_text("CONNECTING", AMBER)
            self.camera_notice.show()
            self._position_camera_notice()
        elif status in ("stopped", "idle"):
            self.camera_pill.set_text("CAMERA OFF", FAINT)
            if self._source != "demo" and status == "stopped":
                self.camera_notice.show()
                self._position_camera_notice()
        self._sync_tracking(snapshot)
        toast = snapshot.get("status", {}).get("toast")
        if toast and toast.get("message") and toast.get("message") != self._last_toast_message:
            self._last_toast_message = str(toast.get("message"))
            self._toast.show_message(self._last_toast_message, str(toast.get("tone", "info")), 2600)
        if self._overlay.visible:
            self._overlay.update_snapshot(snapshot)

    def _sync_light(self, snapshot: dict[str, Any]) -> None:
        # Less frequent label-only update when no new camera frame is available.
        self.stage.set_snapshot(snapshot)
        hand = snapshot.get("hand", {})
        if not hand.get("visible"):
            self.top_gesture.set_text("NO HAND", FAINT)

    def _process_native_events(self, events: list[Any]) -> None:
        config = self.session.config
        for event in events:
            kind = getattr(event, "kind", "")
            data = getattr(event, "data", {})
            if kind in ("mouse_left_down", "mouse_left_up", "mouse_right_click"):
                if self._source == "demo":
                    continue
                if config.os_mouse and self.session.mode == "screen" and self.session.config.tool == "mouse":
                    if "x" in data:
                        self._native.move_cursor(float(data["x"]), float(data["y"]))
                    self._native.execute_mouse_event({"kind": kind})
            elif kind == "navigation":
                if self._source != "demo" and config.os_navigation:
                    self._native.navigate(str(data.get("action", "")))
        pointer = self._snapshot.get("pointer", {})
        if (
            self._source == "camera"
            and config.os_mouse
            and self.session.mode == "screen"
            and self.session.config.tool == "mouse"
            and pointer.get("visible")
        ):
            self._native.move_cursor(float(pointer.get("x", 0.5)), float(pointer.get("y", 0.5)))

    def _sync_tracking(self, snapshot: dict[str, Any]) -> None:
        tracks = snapshot.get("tracks", [])
        fingerprint = tuple((m.get("id"), m.get("status"), m.get("label")) for m in tracks)
        if fingerprint == self._last_track_fingerprint:
            return
        self._last_track_fingerprint = fingerprint
        while self.track_list.count():
            item = self.track_list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not tracks:
            self.track_empty = QLabel("No objects tracked. Choose Track and draw a loop around an object.")
            self.track_empty.setWordWrap(True)
            self.track_empty.setStyleSheet(f"color:{FAINT}; font-size:9px; padding:5px 2px;")
            self.track_list.addWidget(self.track_empty)
            return
        for marker in tracks:
            row = QFrame()
            row.setStyleSheet(f"QFrame {{ background:{SURFACE_RAISED}; border:1px solid {BORDER_SOFT}; border-radius:8px; }}")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(9, 6, 5, 6)
            row_layout.setSpacing(6)
            status = str(marker.get("status", "tracking"))
            tone = MINT if status == "tracking" else AMBER if status in ("occluded", "reacquiring") else DANGER
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{tone}; font-size:8px;")
            row_layout.addWidget(dot)
            text = QVBoxLayout()
            text.setSpacing(0)
            name = QLabel(str(marker.get("label", "Object")))
            name.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px; font-weight:600;")
            status_label = QLabel(status.replace("_", " ").upper())
            status_label.setStyleSheet(f"color:{tone}; font-size:7px; font-weight:700; letter-spacing:0.8px;")
            text.addWidget(name)
            text.addWidget(status_label)
            row_layout.addLayout(text, 1)
            remove = IconButton("close", tooltip="Remove marker", size=24, icon_size=12)
            remove.clicked.connect(lambda checked=False, oid=int(marker.get("id", 0)): self._remove_track(oid))
            row_layout.addWidget(remove)
            self.track_list.addWidget(row)

    # ------------------------------------------------------------------ UI actions
    def _on_mode_changed(self, mode: str) -> None:
        self._set_mode(mode)

    def _set_mode(self, mode: str) -> None:
        if mode not in ("screen", "mirror"):
            return
        if mode == self.session.mode:
            return
        if self._overlay.visible:
            self._overlay.hide()
            self.env_segment.set_value("canvas")
        self.session.set_mode(mode)
        self.mode_segment.set_value(mode)
        self._native.release_all()
        self._sync_mode_ui(mode)
        self._sync_tool_ui()
        self._schedule_save()

    def _sync_mode_ui(self, mode: str, *, initial: bool = False) -> None:
        self.mode_segment.set_value(mode)
        if mode == "screen":
            self.center_eyebrow.setText("SCREEN MODE")
            self.center_title.setText("Built-in canvas")
            self.center_desc.setText("Point to draw. Smart shapes can clean up circles.")
            self.brush_container.show()
            self.env_container.show()
            self.auto_shapes_row.show()
            self.inspector_layout.removeWidget(self.tracking_section)
            self.tracking_section.hide()
            self.footer.center.setText("1 / 2 mode  ·  D draw  ·  N navigate  ·  M mouse  ·  Ctrl+Z undo")
            tool = self.session.config.tool
        else:
            self.center_eyebrow.setText("MIRROR MODE")
            self.center_title.setText("Live feed annotator")
            self.center_desc.setText("Annotate the camera or circle an object to track it.")
            self.brush_container.show()
            self.env_container.hide()
            self.auto_shapes_row.show()
            self.inspector_layout.removeWidget(self.tracking_section)
            self.inspector_layout.insertWidget(5, self.tracking_section)
            self.tracking_section.show()
            self.footer.center.setText("1 / 2 mode  ·  A annotate  ·  T track  ·  pinch a marker to remove")
            tool = self.session.config.mirror_tool
        self.env_segment.set_value("canvas" if not getattr(self, "_overlay", None) or not self._overlay.visible else "overlay")
        self._sync_tool_buttons_visibility(mode)
        button = self._tool_buttons.get(tool)
        if button:
            button.setChecked(True)
            self.tool_hint.setText(button._description)
        self.auto_pill.set_text("SMART SHAPES ON" if self.session.config.auto_shapes else "SMART SHAPES OFF", MINT if self.session.config.auto_shapes else FAINT)
        if initial:
            self.recognition_pill.set_text("IDLE", FAINT)
        self.stage.update()

    def _sync_tool_buttons_visibility(self, mode: str) -> None:
        screen_keys = {k for k, *_ in SCREEN_TOOLS}
        mirror_keys = {k for k, *_ in MIRROR_TOOLS}
        for key, button in self._tool_buttons.items():
            button.setVisible(key in (screen_keys if mode == "screen" else mirror_keys))

    def _sync_tool_ui(self, *, initial: bool = False) -> None:
        mode = self.session.mode
        tool = self.session.config.mirror_tool if mode == "mirror" else self.session.config.tool
        self._sync_tool_buttons_visibility(mode)
        button = self._tool_buttons.get(tool)
        if button:
            button.setChecked(True)
            self.tool_hint.setText(button._description)
        self.brush_container.setVisible(not (mode == "mirror" and tool == "track"))
        if mode == "screen":
            titles = {
                "draw": ("Built-in canvas", "Point to draw. Smart shapes can clean up circles."),
                "navigate": ("Screen navigation", "Hold an open palm, then swipe deliberately."),
                "mouse": ("Virtual mouse", "Pinch to click and drag. Two fingers right-click."),
            }
            title, desc = titles.get(tool, titles["draw"])
            self.center_title.setText(title)
            self.center_desc.setText(desc)
        else:
            titles = {
                "annotate": ("Live feed annotator", "Marks stay aligned with the camera frame."),
                "track": ("Object tracking", "Trace a loop around an object, then hold still."),
            }
            title, desc = titles.get(tool, titles["annotate"])
            self.center_title.setText(title)
            self.center_desc.setText(desc)
        self.stage.update()

    def _on_tool_clicked(self, key: str) -> None:
        if key in {k for k, *_ in SCREEN_TOOLS}:
            if self.session.mode != "screen":
                self._set_mode("screen")
            self.session.set_tool(key)
        elif key in {k for k, *_ in MIRROR_TOOLS}:
            if self.session.mode != "mirror":
                self._set_mode("mirror")
            self.session.set_tool(key)
        self._native.release_all()
        self._sync_tool_ui()
        self._schedule_save()

    def _on_color(self, color: str) -> None:
        self.session.set_brush(color)
        self.color_value.setText(color.upper())
        for key, swatch in self._swatches.items():
            swatch.setChecked(key.lower() == color.lower())
        self._schedule_save()

    def _on_brush_width(self, value: float) -> None:
        self.session.set_brush(width=value)
        self._schedule_save()

    def _on_auto_shapes(self, checked: bool) -> None:
        self.session.apply_config({"auto_shapes": checked})
        self.auto_pill.set_text("SMART SHAPES ON" if checked else "SMART SHAPES OFF", MINT if checked else FAINT)
        self._toast.show_message(
            "Smart shape correction enabled" if checked else "Freehand drawing - correction off",
            "success" if checked else "info",
            1700,
        )
        self._schedule_save()

    def _on_environment_changed(self, value: str) -> None:
        if value == "overlay":
            if self.session.mode != "screen":
                self._set_mode("screen")
            self._open_overlay()
        elif self._overlay.visible:
            self._overlay.hide()

    def _open_overlay(self) -> None:
        self.overlay = self._overlay
        snapshot = self.session.snapshot()
        self._overlay.set_actions(self._undo, self._clear_canvas)
        self._overlay.show(snapshot)
        self.env_segment.set_value("overlay")
        self._toast.show_message("Desktop overlay active. Draw over other apps; use the floating bar to exit.", "info", 3600)

    def _sync_settings_from_config(self) -> None:
        cfg = self.session.config
        self.auto_shapes_row.set_checked(cfg.auto_shapes)
        self.mirror_camera_row.set_checked(cfg.mirror_camera)
        self.landmark_row.set_checked(cfg.show_landmarks)
        self.handed_row.set_checked(cfg.gesture.left_handed)
        self.os_mouse_row.set_checked(cfg.os_mouse)
        self.os_nav_row.set_checked(cfg.os_navigation)
        self.width_slider.set_value(int(round(cfg.brush_width)))
        self.pinch_slider.set_value(int(cfg.gesture.pinch_sensitivity * 100))
        self.smooth_slider.set_value(int(cfg.gesture.cursor_smoothing * 100))
        self.hold_slider.set_value(int(cfg.gesture.nav_hold_ms))
        self.stability_slider.set_value(int(cfg.gesture.stability_frames))
        for color, swatch in self._swatches.items():
            swatch.setChecked(color.lower() == cfg.brush_color.lower())

    # ------------------------------------------------------------------ settings
    def _on_mapping_changed(self, key: str, value: str) -> None:
        if not value:
            return
        self.session.apply_config({"gesture": {key: value}})
        self._schedule_save()

    def _on_pinch_sensitivity(self, value: float) -> None:
        self.session.apply_config({"gesture": {"pinch_sensitivity": value / 100.0}})
        self._schedule_save()

    def _on_cursor_smoothing(self, value: float) -> None:
        self.session.apply_config({"gesture": {"cursor_smoothing": value / 100.0}})
        self._schedule_save()

    def _on_nav_hold(self, value: float) -> None:
        self.session.apply_config({"gesture": {"nav_hold_ms": int(value)}})
        self._schedule_save()

    def _on_stability(self, value: float) -> None:
        self.session.apply_config({"gesture": {"stability_frames": int(value)}})
        self._schedule_save()

    def _on_mirror_camera(self, checked: bool) -> None:
        self.session.apply_config({"mirror_camera": checked})
        self._schedule_save()

    def _on_landmarks(self, checked: bool) -> None:
        self.session.apply_config({"show_landmarks": checked})
        self._schedule_save()

    def _on_left_handed(self, checked: bool) -> None:
        self.session.apply_config({"gesture": {"left_handed": checked}})
        self._apply_handedness_layout()
        self._schedule_save()

    def _on_os_mouse(self, checked: bool) -> None:
        if checked and not confirm_os_control(self, "mouse"):
            self.os_mouse_row.set_checked(False)
            return
        self.session.apply_config({"os_mouse": checked})
        if not checked:
            self._native.release_all()
        self._schedule_save()

    def _on_os_navigation(self, checked: bool) -> None:
        if checked and not confirm_os_control(self, "navigation"):
            self.os_nav_row.set_checked(False)
            return
        self.session.apply_config({"os_navigation": checked})
        self._schedule_save()

    def _on_dominant_hand(self, value: str) -> None:
        self.session.apply_config({"gesture": {"dominant_hand": value}})
        self._schedule_save()

    def _show_camera_diagnostics(self) -> None:
        """Probe indices/backends from the UI and explain the result."""
        self._toast.show_message("Probing camera backends…", "info", 1200)
        report = diagnose_cameras(3)
        working = [item for item in report["results"] if item.get("frame")]
        lines = [f"OpenCV {report['opencv']} on {report['platform']}", ""]
        if working:
            lines.append("Working camera paths:")
            for item in working:
                size = item.get("frame_size") or [0, 0]
                lines.append(
                    f"  ✓ index {item['index']} · {item['backend']} · {size[0]}×{size[1]} · {item.get('elapsed_ms', 0):.0f} ms"
                )
            lines.append("")
            lines.append("Choose this backend and index under System, then retry the camera.")
        else:
            lines.append("No backend/index delivered a frame.")
            lines.append("")
            index0 = [item for item in report["results"] if item["index"] == 0]
            for item in index0:
                lines.append(f"  index 0 · {item['backend']}: {item.get('error', 'no frame')}")
            lines.append("")
            lines.append(
                "Check Windows Settings → Privacy & security → Camera, close other camera apps "
                "(Teams/Zoom/OBS virtual cameras), or use the simulated feed. "
                "If the camera works in a browser but not here, use the web interface: "
                "python run_web.py --open"
            )
        lines.append("")
        lines.append("CLI: python scripts/diagnose_camera.py --max-index 3")
        QMessageBox.information(self, "Camera diagnostics", "\n".join(lines))

    def _on_camera_index(self, value: str) -> None:
        try:
            index = int(value)
        except ValueError:
            return
        self.session.apply_config({"camera_index": index})
        self._schedule_save()
        if self._source == "camera":
            self.start_camera()

    def _on_camera_backend(self, value: str) -> None:
        self.session.apply_config({"camera_backend": value})
        self._schedule_save()
        if self._source == "camera":
            self.start_camera()

    # ---------------------------------------------------------- hand model
    def _update_hand_model_ui(self) -> None:
        config = self.session.config
        path = config.hand_model_path
        if path:
            label_text = path.rstrip("/").rsplit("/", 1)[-1] if "://" in path else Path(path).name
            tooltip = path
        elif config.hand_backend == "rtmpose":
            label_text = "rtmlib default (downloaded once)"
            tooltip = "Leave empty to let rtmlib download the RTMDet hand detector and RTMPose-Hand ONNX models."
        elif config.hand_backend == "yolo_pose":
            label_text = "Choose a 21-keypoint .pt"
            tooltip = "Stock YOLOv8/v11-pose models have 17 body keypoints and are rejected."
        else:
            label_text = "Bundled hand_landmarker.task"
            tooltip = "Leave empty to use the bundled MediaPipe model."
        self.hand_model_path_label.setText(label_text)
        self.hand_model_path_label.setToolTip(tooltip)
        status = backend_status(config)
        if status.available:
            detail = status.requires if status.requires not in ("", "mediapipe") else ""
            suffix = f" · {detail}" if detail else ""
            self.hand_model_status.setText(f"● {status.label} ready{suffix}")
            self.hand_model_status.setStyleSheet(f"color:{MINT}; font-size:10px;")
        else:
            detail = status.reason
            if status.requires:
                detail = f"{detail} · {status.requires}"
            self.hand_model_status.setText(f"○ {detail}")
            self.hand_model_status.setStyleSheet(f"color:{AMBER}; font-size:10px;")
        self.hand_model_status.setToolTip(status.note)

    def _on_hand_model(self, value: str) -> None:
        config = self.session.config
        path = config.hand_model_path
        allowed = {
            "mediapipe": (".task",),
            "rtmpose": (".onnx", ".zip", ".tflite"),
            "yolo_pose": (".pt",),
        }.get(value, ())
        if path and not path.lower().endswith(allowed):
            path = ""
        self.session.apply_config({"hand_backend": value, "hand_model_path": path})
        self._schedule_save()
        self._update_hand_model_ui()
        status = backend_status(self.session.config)
        if not status.available:
            self._toast.show_message(
                f"{status.label}: {status.reason}. {status.requires}".strip(),
                "warning",
                6000,
            )

    def _choose_hand_model(self) -> None:
        backend = self.session.config.hand_backend
        filters = {
            "mediapipe": "MediaPipe model (*.task);;All files (*)",
            "rtmpose": "RTMPose ONNX bundle (*.onnx *.zip *.tflite);;All files (*)",
            "yolo_pose": "YOLO Pose weights (*.pt);;All files (*)",
        }[backend]
        filename, _ = QFileDialog.getOpenFileName(self, "Choose hand landmark model", str(Path.home()), filters)
        if not filename:
            return
        self.session.apply_config({"hand_model_path": filename})
        self._schedule_save()
        self._update_hand_model_ui()
        status = backend_status(self.session.config)
        if not status.available:
            self._toast.show_message(f"{status.label}: {status.reason}", "warning", 5000)

    def _apply_handedness_layout(self) -> None:
        left_handed = self.session.config.gesture.left_handed
        widgets = [self.sidebar, self.center, self.inspector]
        for widget in widgets:
            self._content_layout.removeWidget(widget)
        if left_handed:
            self._content_layout.addWidget(self.inspector)
            self._content_layout.addWidget(self.center, 1)
            self._content_layout.addWidget(self.sidebar)
        else:
            self._content_layout.addWidget(self.sidebar)
            self._content_layout.addWidget(self.center, 1)
            self._content_layout.addWidget(self.inspector)

    # ------------------------------------------------------------------ actions
    def _undo(self) -> None:
        if not self.session.undo():
            self._toast.show_message("Nothing to undo", "info", 1500)
        self._refresh_local_snapshot()

    def _redo(self) -> None:
        if not self.session.redo():
            self._toast.show_message("Nothing to redo", "info", 1500)
        self._refresh_local_snapshot()

    def _clear_canvas(self) -> None:
        if not self.session.clear():
            self._toast.show_message("Canvas is already empty", "info", 1500)
        else:
            self._toast.show_message("Canvas cleared - Ctrl+Z restores it", "info", 2400)
        self._refresh_local_snapshot()

    def _clear_tracks(self) -> None:
        if not self.session.clear_tracks():
            self._toast.show_message("No tracking markers to remove", "info", 1500)
        self._refresh_local_snapshot()

    def _remove_track(self, object_id: int) -> None:
        self.session.remove_track(object_id)
        self._refresh_local_snapshot()

    def _save_png(self) -> None:
        default_name = f"aircanvas-{time.strftime('%Y%m%d-%H%M%S')}.png"
        target, _ = QFileDialog.getSaveFileName(self, "Export artwork", str(Path.home() / default_name), "PNG image (*.png)")
        if not target:
            return
        try:
            image = self.stage.render_artwork(1920, 1080)
            if image.save(target, "PNG"):
                self._toast.show_message(f"Saved {Path(target).name}", "success", 2600)
            else:
                self._toast.show_message("Could not save image", "error", 2600)
        except Exception as exc:
            self._toast.show_message(f"Export failed: {exc}", "error", 3000)

    def _refresh_local_snapshot(self) -> None:
        self._snapshot = self.session.snapshot()
        self._apply_snapshot(self._snapshot)
        if self._overlay.visible:
            self._overlay.update_snapshot(self._snapshot)

    def _manual_begin(self, x: float, y: float) -> None:
        from ..geometry import Point

        self.session.manual_begin(Point(x, y))

    def _manual_move(self, x: float, y: float) -> None:
        from ..geometry import Point

        self.session.manual_add(Point(x, y))
        self._snapshot = self.session.snapshot()
        self.stage.set_snapshot(self._snapshot)

    def _manual_end(self) -> None:
        self.session.manual_end()
        self._refresh_local_snapshot()

    # ------------------------------------------------------------------ demo capture
    def prime_demo(self, mode: str, seconds: float = 6.0, fps: int = 30) -> dict[str, Any]:
        """Feed deterministic demo frames through the real session for screenshots/tests."""
        self._stop_pipeline()
        if mode != self.session.mode:
            self.session.set_mode(mode)
            self.mode_segment.set_value(mode)
            self._sync_mode_ui(mode)
            self._sync_tool_ui()
        engine = DemoEngine(self.session)
        engine.reset()
        rgb = None
        frame = None
        session = self.session
        total = max(1, int(seconds * fps))
        events: list[Any] = []
        for i in range(total):
            t = i / float(fps)
            frame = engine.frame(t)
            observation = engine.observation(t)
            events = session.process_frame(frame, t, observation=observation)
        if frame is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self._last_frame_rgb = rgb
            image = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format.Format_RGB888).copy()
            self.stage.set_frame(image)
        session.set_camera_status("demo", "Simulated camera feed", source="demo", demo=True, width=960, height=540)
        self._snapshot = session.snapshot()
        self.stage.set_snapshot(self._snapshot)
        self._process_native_events(events)
        self._apply_snapshot(self._snapshot)
        self.camera_notice.hide()
        return self._snapshot

    # ------------------------------------------------------------------ window
    def _toggle_max(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._position_camera_notice()
        if hasattr(self, "_toast") and self._toast is not None:
            self._toast._position()

    def _position_camera_notice(self) -> None:
        if not hasattr(self, "stage") or not hasattr(self, "camera_notice"):
            return
        if self.camera_notice.parent() is not self.stage:
            self.camera_notice.setParent(self.stage)
        self.camera_notice.adjustSize()
        x = max(12, (self.stage.width() - self.camera_notice.width()) // 2)
        self.camera_notice.move(x, 66)
        self.camera_notice.raise_()

    def _schedule_save(self) -> None:
        self._save_timer.start()

    def _persist_now(self) -> None:
        save_config(self.session.config, self.config_path)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._persist_now()
        self._poll_timer.stop()
        if self._overlay.visible:
            self._overlay.hide()
        self._overlay.close()
        self._native.release_all()
        self._stop_pipeline()
        self.session.close()
        super().closeEvent(event)
