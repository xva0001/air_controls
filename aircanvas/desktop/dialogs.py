"""Onboarding, help and safety dialogs."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .icons import draw_icon
from .theme import (
    ACCENT,
    AMBER,
    BORDER,
    BORDER_SOFT,
    FAINT,
    MINT,
    MUTED,
    SURFACE,
    SURFACE_RAISED,
    TEXT,
    TEXT_DIM,
)
from .widgets import IconButton, LogoMark


class GestureCard(QFrame):
    def __init__(self, icon: str, title: str, body: str, tone: str = MINT, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(7)
        top = QHBoxLayout()
        top.setSpacing(8)
        icon_widget = _IconBadge(icon, tone)
        top.addWidget(icon_widget)
        label = QLabel(title)
        label.setStyleSheet(f"color:{TEXT}; font-size:12px; font-weight:700;")
        top.addWidget(label)
        top.addStretch(1)
        layout.addLayout(top)
        caption = QLabel(body)
        caption.setWordWrap(True)
        caption.setStyleSheet(f"color:{MUTED}; font-size:11px; line-height:1.4;")
        layout.addWidget(caption)


class _IconBadge(QWidget):
    def __init__(self, icon: str, tone: str, size: int = 30) -> None:
        super().__init__()
        self.icon = icon
        self.tone = tone
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QPainter, QPen

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(self.tone), 1))
        painter.setBrush(QColor("#231F1A"))
        painter.drawRoundedRect(r, 8, 8)
        draw_icon(painter, self.icon, r.adjusted(6, 6, -6, -6), self.tone, 1.5)


class OnboardingDialog(QDialog):
    camera_requested = Signal()
    demo_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to AirCanvas")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(790, 572)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setStyleSheet(
            f"QFrame#Onboard {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:22px; }}"
        )
        card.setObjectName("Onboard")
        outer.addWidget(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(34, 30, 34, 28)
        layout.setSpacing(18)
        top = QHBoxLayout()
        top.setSpacing(11)
        top.addWidget(LogoMark(38))
        text = QVBoxLayout()
        text.setSpacing(0)
        title = QLabel("AirCanvas")
        title.setStyleSheet(f"color:{TEXT}; font-size:21px; font-weight:800; letter-spacing:0.4px;")
        tag = QLabel("Gesture interaction studio")
        tag.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        text.addWidget(title)
        text.addWidget(tag)
        top.addLayout(text)
        top.addStretch(1)
        close = IconButton("close", tooltip="Close onboarding", size=32)
        close.clicked.connect(self.reject)
        top.addWidget(close)
        layout.addLayout(top)
        hero = QLabel("Touch the air. Draw the world.")
        hero.setStyleSheet(f"color:{TEXT}; font-size:31px; font-weight:700; letter-spacing:-0.6px;")
        layout.addWidget(hero)
        sub = QLabel(
            "One shared gesture engine, two ways to work. Choose a workspace below, then use the on-screen guide. "
            "Nothing is recorded or uploaded; camera frames stay on this computer."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px; line-height:1.45;")
        layout.addWidget(sub)
        grid = QHBoxLayout()
        grid.setSpacing(10)
        grid.addWidget(GestureCard("pen", "Point to draw", "Raise your index finger. Hold a pose for a moment to begin a stroke. Deliberate circles are corrected automatically.", ACCENT))
        grid.addWidget(GestureCard("track", "Loop to track", "In Mirror Mode, trace a loop around an object, then hold still. Markers follow it and recover after brief occlusion.", MINT))
        grid.addWidget(GestureCard("navigate", "Swipe with intent", "Switch to Navigate and hold an open palm. A directional swipe is only accepted after the hold and cooldown.", AMBER))
        layout.addLayout(grid)
        keys = QHBoxLayout()
        keys.setSpacing(10)
        for label, key in [("Draw", "D"), ("Navigate", "N"), ("Mouse", "M"), ("Undo", "Ctrl Z"), ("Save", "Ctrl S")]:
            box = QFrame()
            box.setStyleSheet(f"background:{SURFACE_RAISED}; border:1px solid {BORDER_SOFT}; border-radius:7px;")
            row = QHBoxLayout(box)
            row.setContentsMargins(9, 4, 9, 4)
            row.setSpacing(6)
            k = QLabel(key)
            k.setStyleSheet(f"color:{TEXT}; font-size:9px; font-weight:700; font-family:'Cascadia Mono','Consolas';")
            row.addWidget(k)
            t = QLabel(label)
            t.setStyleSheet(f"color:{MUTED}; font-size:9px;")
            row.addWidget(t)
            keys.addWidget(box)
        keys.addStretch(1)
        layout.addLayout(keys)
        layout.addStretch(1)
        footer = QHBoxLayout()
        privacy = QLabel("●  Local by design   ·   keyboard + mouse fallback at every step")
        privacy.setStyleSheet(f"color:{FAINT}; font-size:10px;")
        footer.addWidget(privacy)
        footer.addStretch(1)
        demo = QPushButton("Use simulated feed")
        demo.clicked.connect(self._demo)
        footer.addWidget(demo)
        start = QPushButton("Start with camera")
        start.setObjectName("Primary")
        start.clicked.connect(self._camera)
        footer.addWidget(start)
        layout.addLayout(footer)

    def _camera(self) -> None:
        self.camera_requested.emit()
        self.accept()

    def _demo(self) -> None:
        self.demo_requested.emit()
        self.accept()


class HelpDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AirCanvas help")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(760, 610)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("HelpCard")
        card.setStyleSheet(f"QFrame#HelpCard {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:20px; }}")
        outer.addWidget(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(13)
        top = QHBoxLayout()
        eyebrow = QLabel("FIELD GUIDE")
        eyebrow.setObjectName("Eyebrow")
        top.addWidget(eyebrow)
        top.addStretch(1)
        close = IconButton("close", tooltip="Close help", size=32)
        close.clicked.connect(self.accept)
        top.addWidget(close)
        layout.addLayout(top)
        title = QLabel("How AirCanvas works")
        title.setStyleSheet(f"color:{TEXT}; font-size:26px; font-weight:700;")
        layout.addWidget(title)
        intro = QLabel(
            "AirCanvas is built around five short gestures. Poses are stabilised over several frames; "
            "nothing fires on a single noisy frame. Every action has a keyboard or mouse equivalent."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px;")
        layout.addWidget(intro)
        gesture_grid = QHBoxLayout()
        gesture_grid.setSpacing(9)
        gesture_grid.addWidget(GestureCard("pen", "Point", "Draw / annotate. Hold steady.", ACCENT))
        gesture_grid.addWidget(GestureCard("cursor", "Pinch", "Left click; hold to drag.", MINT))
        gesture_grid.addWidget(GestureCard("hand", "Open palm", "Arm navigation or rest.", AMBER))
        gesture_grid.addWidget(GestureCard("track", "Two fingers", "Right click / page swipe.", "#64A9E5"))
        layout.addLayout(gesture_grid)
        columns = QHBoxLayout()
        columns.setSpacing(18)
        shortcuts = self._section(
            "KEYBOARD",
            [
                ("1 / 2", "Screen / Mirror mode"),
                ("D / N / M", "Draw / Navigate / Mouse"),
                ("A", "Annotate / Track (mirror)"),
                ("Ctrl+Z", "Undo"),
                ("Ctrl+Shift+Z", "Redo"),
                ("Ctrl+S", "Export artwork"),
                ("F1", "Open this guide"),
                ("Esc", "Close dialogs / overlay"),
            ],
        )
        safety = self._section(
            "SAFER BY DEFAULT",
            [
                ("Local only", "Camera frames are processed in memory."),
                ("System control", "Off until you explicitly consent."),
                ("Undo", "Clear is reversible with Ctrl+Z."),
                ("Fallbacks", "Mouse drawing and arrow shortcuts."),
                ("Simulation", "No camera? Use a labelled demo feed."),
            ],
        )
        columns.addWidget(shortcuts, 1)
        columns.addWidget(safety, 1)
        layout.addLayout(columns)
        layout.addStretch(1)
        footer = QLabel("Tip: sensitivity and gesture mappings live in the right-hand inspector.")
        footer.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        layout.addWidget(footer)

    def _section(self, title: str, rows: list[tuple[str, str]]) -> QWidget:
        box = QFrame()
        box.setObjectName("Card")
        inner = QVBoxLayout(box)
        inner.setContentsMargins(14, 12, 14, 12)
        inner.setSpacing(5)
        heading = QLabel(title)
        heading.setStyleSheet(f"color:{MUTED}; font-size:9px; font-weight:800; letter-spacing:1.2px;")
        inner.addWidget(heading)
        for key, desc in rows:
            row = QHBoxLayout()
            row.setSpacing(8)
            k = QLabel(key)
            k.setFixedWidth(74)
            k.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px; font-family:'Cascadia Mono','Consolas';")
            d = QLabel(desc)
            d.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            d.setWordWrap(True)
            row.addWidget(k)
            row.addWidget(d, 1)
            inner.addLayout(row)
        return box


def confirm_os_control(parent: QWidget, kind: str) -> bool:
    from PySide6.QtWidgets import QMessageBox

    box = QMessageBox(parent)
    box.setWindowTitle("Enable system control?")
    if kind == "mouse":
        box.setText("Let gestures control the operating-system mouse?")
        box.setInformativeText(
            "When the Mouse tool is active, pinch and two-finger gestures will click and drag outside AirCanvas. "
            "Turn this off at any time in the inspector. Keyboard and mouse still work normally."
        )
    else:
        box.setText("Let gestures send system navigation shortcuts?")
        box.setInformativeText(
            "Open-palm swipes will send scroll and back/forward shortcuts to the focused application. "
            "Two-finger swipes send Page Up / Page Down. Turn this off at any time."
        )
    box.setIcon(QMessageBox.Icon.Warning)
    box.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok)
    box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    box.button(QMessageBox.StandardButton.Ok).setText("Enable")
    return box.exec() == QMessageBox.StandardButton.Ok
