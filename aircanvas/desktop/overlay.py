"""Click-through transparent desktop overlay and its floating toolbar."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from .theme import (
    ACCENT,
    MINT,
    MUTED,
    TEXT,
    qcolor,
)
from .widgets import IconButton


class OverlayCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._snapshot: dict = {}
        self.setWindowTitle("AirCanvas overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

    def show_overlay(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.geometry())
        self.showFullScreen()
        self.raise_()

    def set_snapshot(self, snapshot: dict) -> None:
        self._snapshot = snapshot or {}
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        drawing = self._snapshot.get("drawing", {})
        strokes = list(drawing.get("strokes", []))
        if drawing.get("current"):
            strokes.append(drawing["current"])
        rect = QRectF(self.rect())
        for stroke in strokes:
            points = stroke.get("points", [])
            if len(points) < 2:
                continue
            path = self._smooth_path(points, rect)
            color = QColor(stroke.get("color", ACCENT))
            width = max(2.0, float(stroke.get("width", 5.0)) * min(rect.width(), rect.height()) / 820.0 * 1.35)
            halo = QColor(color)
            halo.setAlpha(35)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(halo, width * 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(path)
            painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(path)
        # A deliberately tiny non-interactive signature.
        font = QFont(self.font())
        font.setPixelSize(9)
        font.setWeight(QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        painter.setFont(font)
        painter.setPen(qcolor(TEXT, 75))
        painter.drawText(
            QRectF(rect.right() - 270, rect.bottom() - 26, 250, 16),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "AIRCANVAS · OVERLAY PASS-THROUGH",
        )

    @staticmethod
    def _smooth_path(points: list, rect: QRectF) -> QPainterPath:
        mapped = [QPointF(float(p[0]) * rect.width(), float(p[1]) * rect.height()) for p in points]
        path = QPainterPath(mapped[0])
        if len(mapped) == 2:
            path.lineTo(mapped[1])
            return path
        for i in range(1, len(mapped) - 1):
            mid = QPointF((mapped[i].x() + mapped[i + 1].x()) / 2, (mapped[i].y() + mapped[i + 1].y()) / 2)
            path.quadTo(mapped[i], mid)
        path.lineTo(mapped[-1])
        return path


class OverlayToolbar(QWidget):
    exit_requested = Signal()
    undo_requested = Signal()
    clear_requested = Signal()
    bring_back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AirCanvas overlay controls")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(510, 58)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background:{MINT}; border-radius:4px;")
        layout.addWidget(dot)
        title = QLabel("Overlay")
        title.setStyleSheet("color:#F4EFE5; font-size:12px; font-weight:700;")
        layout.addWidget(title)
        self.hint = QLabel("click-through · exit below")
        self.hint.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        layout.addWidget(self.hint)
        layout.addStretch(1)
        self.undo = IconButton("undo", tooltip="Undo (Ctrl+Z)", size=32)
        self.undo.clicked.connect(self.undo_requested)
        layout.addWidget(self.undo)
        self.clear = IconButton("trash", tooltip="Clear overlay", size=32)
        self.clear.clicked.connect(self.clear_requested)
        layout.addWidget(self.clear)
        self.exit = IconButton("close", tooltip="Exit overlay (Esc)", size=32, tone=TEXT)
        self.exit.clicked.connect(self.exit_requested)
        layout.addWidget(self.exit)

    def show_toolbar(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(geo.center().x() - self.width() // 2, geo.bottom() - self.height() - 24)
        self.show()
        self.raise_()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setPen(QPen(qcolor("#4B4138"), 1))
        painter.setBrush(qcolor("#171411", 245))
        painter.drawRoundedRect(r, 14, 14)
        painter.setPen(QPen(qcolor(MINT, 70), 1))
        painter.drawLine(QPointF(r.left() + 18, r.bottom() - 1), QPointF(r.right() - 18, r.bottom() - 1))


class OverlayController:
    """Owns and synchronises the transparent canvas and toolbar windows."""

    def __init__(self, parent: QWidget) -> None:
        self.canvas = OverlayCanvas()
        self.toolbar = OverlayToolbar()
        self._visible = False
        self.toolbar.exit_requested.connect(self.hide)
        self.toolbar.undo_requested.connect(self._undo)
        self.toolbar.clear_requested.connect(self._clear)
        self._on_undo = None
        self._on_clear = None

    @property
    def visible(self) -> bool:
        return self._visible

    def set_actions(self, undo, clear) -> None:
        self._on_undo = undo
        self._on_clear = clear

    def _undo(self) -> None:
        if callable(self._on_undo):
            self._on_undo()

    def _clear(self) -> None:
        if callable(self._on_clear):
            self._on_clear()

    def show(self, snapshot: dict) -> None:
        self.canvas.set_snapshot(snapshot)
        self.canvas.show_overlay()
        self.toolbar.show_toolbar()
        self.toolbar.raise_()
        self._visible = True

    def update_snapshot(self, snapshot: dict) -> None:
        if not self._visible:
            return
        self.canvas.set_snapshot(snapshot)
        self.toolbar.raise_()

    def hide(self) -> None:
        self._visible = False
        self.canvas.hide()
        self.toolbar.hide()

    def close(self) -> None:
        self._visible = False
        self.canvas.close()
        self.toolbar.close()
