"""Reusable, accessible PySide6 widgets for the AirCanvas desktop shell."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..gestures import HAND_CONNECTIONS
from .icons import draw_icon
from .theme import (
    ACCENT,
    ACCENT_2,
    AMBER,
    BG,
    BORDER,
    BORDER_SOFT,
    DANGER,
    FAINT,
    MINT,
    MUTED,
    SURFACE_RAISED,
    TEXT,
    TEXT_DIM,
    qcolor,
)

MODE_COLORS = {"screen": ACCENT, "mirror": MINT}


class LogoMark(QWidget):
    def __init__(self, size: int = 34, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAccessibleName("AirCanvas logo")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(SURFACE_RAISED))
        painter.drawRoundedRect(rect, 10, 10)
        # An abstract air stroke forming an A.
        path = QPainterPath()
        cx = rect.center().x()
        path.moveTo(cx - 8, rect.bottom() - 8)
        path.cubicTo(cx - 3, rect.bottom() - 3, cx + 7, rect.center().y() + 4, cx, rect.top() + 8)
        path.cubicTo(cx - 6, rect.center().y() - 5, cx - 8, rect.bottom() - 10, cx - 8, rect.bottom() - 8)
        pen = QPen(qcolor(ACCENT), 4.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        pen2 = QPen(qcolor(MINT), 2.2)
        pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen2)
        painter.drawLine(QPoint(int(cx - 6), int(rect.center().y())), QPoint(int(cx + 9), int(rect.center().y() - 1)))


class IconButton(QAbstractButton):
    def __init__(
        self,
        icon: str,
        *,
        tooltip: str = "",
        size: int = 34,
        icon_size: int = 18,
        checkable: bool = False,
        tone: str = MUTED,
        variant: str = "ghost",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon = icon
        self._icon_size = icon_size
        self._tone = tone
        self._variant = variant
        self._hover = False
        self.setCheckable(checkable)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip or icon)
        self.setAccessibleDescription(tooltip)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        active = self.isChecked()
        bg = None
        if self._variant == "solid":
            bg = ACCENT if active else SURFACE_RAISED
        elif active:
            bg = "#302A24"
        elif self._hover and self.isEnabled():
            bg = SURFACE_RAISED
        if bg:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(bg))
            painter.drawRoundedRect(r, 8, 8)
        if self.hasFocus():
            painter.setPen(QPen(qcolor(ACCENT), 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        color = self._tone
        if active:
            color = ACCENT if self._variant == "solid" else TEXT
        elif not self.isEnabled():
            color = FAINT
        elif self._hover:
            color = TEXT
        margin = (self.width() - self._icon_size) / 2
        draw_icon(painter, self._icon, QRectF(margin, margin, self._icon_size, self._icon_size), color, 1.7)


class NavButton(QAbstractButton):
    def __init__(
        self,
        icon: str,
        label: str,
        shortcut: str = "",
        *,
        description: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon = icon
        self._label = label
        self._shortcut = shortcut
        self._description = description
        self._hover = False
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(description or label)
        self.setAccessibleName(label)
        self.setAccessibleDescription(description or label)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self.isChecked()
        r = QRectF(self.rect()).adjusted(0, 1, 0, -1)
        if active:
            painter.setBrush(qcolor("#2B2520"))
            painter.setPen(QPen(qcolor("#3B322A"), 1))
            painter.drawRoundedRect(r, 11, 11)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(ACCENT))
            painter.drawRoundedRect(QRectF(r.left(), r.top() + 11, 3, r.height() - 22), 1.5, 1.5)
        elif self._hover:
            painter.setBrush(qcolor(SURFACE_RAISED))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(r, 11, 11)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.hasFocus():
            painter.setPen(QPen(qcolor(ACCENT), 1.0))
            painter.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 11, 11)
        tone = ACCENT if active else (TEXT_DIM if self._hover else MUTED)
        draw_icon(painter, self._icon, QRectF(14, 14, 22, 22), tone, 1.7)
        font = QFont(self.font())
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.DemiBold if active else QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(qcolor(TEXT if active else TEXT_DIM))
        painter.drawText(QRectF(48, 0, self.width() - 90, self.height()), Qt.AlignmentFlag.AlignVCenter, self._label)
        if self._shortcut:
            painter.setPen(QPen(qcolor(BORDER), 1))
            pill = QRectF(self.width() - 40, 16, 24, 18)
            painter.setBrush(qcolor("#1C1916"))
            painter.drawRoundedRect(pill, 5, 5)
            f = QFont(self.font())
            f.setPixelSize(9)
            f.setBold(True)
            painter.setFont(f)
            painter.setPen(qcolor(FAINT if not active else TEXT_DIM))
            painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, self._shortcut)


class SegmentControl(QWidget):
    changed = Signal(str)

    def __init__(
        self,
        options: Sequence[tuple[str, str]],
        *,
        value: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.options = list(options)
        self._value = value or self.options[0][0]
        self._hover_index = -1
        self._pressed_index = -1
        self.setMouseTracking(True)
        self.setFixedHeight(38)
        self.setMinimumWidth(70 * len(options) + 8)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("View mode")
        for key, label in self.options:
            self.setAccessibleDescription(f"{key}: {label}")

    @property
    def value(self) -> str:
        return self._value

    def set_value(self, value: str, *, emit: bool = False) -> None:
        if any(key == value for key, _ in self.options) and value != self._value:
            self._value = value
            self.update()
            if emit:
                self.changed.emit(value)

    def _index_at(self, pos: QPoint) -> int:
        if not self.rect().contains(pos):
            return -1
        inner = QRectF(4, 4, (self.width() - 8) / len(self.options), self.height() - 8)
        for i in range(len(self.options)):
            if inner.translated(i * inner.width(), 0).contains(pos):
                return i
        return -1

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        idx = self._index_at(event.position().toPoint())
        if idx != self._hover_index:
            self._hover_index = idx
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_index = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._index_at(event.position().toPoint())
            self._pressed_index = idx
            if idx >= 0:
                key = self.options[idx][0]
                if key != self._value:
                    self._value = key
                    self.update()
                    self.changed.emit(key)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._pressed_index = -1
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        keys = [key for key, _ in self.options]
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            idx = keys.index(self._value)
            idx = (idx + (1 if event.key() == Qt.Key.Key_Right else -1)) % len(keys)
            self._value = keys[idx]
            self.update()
            self.changed.emit(self._value)
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(qcolor(BORDER), 1))
        painter.setBrush(qcolor(SURFACE_RAISED))
        painter.drawRoundedRect(outer, 11, 11)
        inner_w = (outer.width() - 8) / len(self.options)
        for i, (key, label) in enumerate(self.options):
            cell = QRectF(outer.left() + 4 + i * inner_w, outer.top() + 4, inner_w, outer.height() - 8)
            if key == self._value:
                painter.setPen(QPen(qcolor("#43382F"), 1))
                painter.setBrush(qcolor("#302820"))
                painter.drawRoundedRect(cell, 8, 8)
            elif i == self._hover_index:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(qcolor("#231F1B"))
                painter.drawRoundedRect(cell, 8, 8)
            painter.setPen(qcolor(TEXT if key == self._value else MUTED))
            font = QFont(self.font())
            font.setPixelSize(11)
            font.setWeight(QFont.Weight.DemiBold if key == self._value else QFont.Weight.Medium)
            painter.setFont(font)
            painter.drawText(cell, Qt.AlignmentFlag.AlignCenter, label)
        if self.hasFocus():
            painter.setPen(QPen(qcolor(ACCENT), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(outer, 11, 11)


class ToggleSwitch(QAbstractButton):
    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(38, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._offset = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 2, -1, -2)
        off = qcolor("#302B25")
        on = qcolor(ACCENT if self.isChecked() else "#302B25")
        painter.setPen(QPen(qcolor("#4A4239" if not self.isChecked() else ACCENT), 1))
        painter.setBrush(on if self.isChecked() else off)
        painter.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        knob_x = r.left() + 2 + self._offset * (r.width() - r.height())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(TEXT if self.isChecked() else "#B9B0A4"))
        painter.drawEllipse(QRectF(knob_x, r.top() + 2, r.height() - 4, r.height() - 4))
        if self.hasFocus():
            painter.setPen(QPen(qcolor(ACCENT_2), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(r.adjusted(-1, -1, 1, 1), r.height() / 2, r.height() / 2)


class ColorSwatch(QAbstractButton):
    def __init__(self, color: str, size: int = 26, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setCheckable(True)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(f"Brush colour {color}")
        self.setAccessibleName(f"Brush colour {color}")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QRectF(self.rect()).center()
        radius = min(self.width(), self.height()) / 2 - 3
        if self.isChecked():
            painter.setPen(QPen(qcolor(TEXT), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius + 2.0, radius + 2.0)
        if self.hasFocus():
            painter.setPen(QPen(qcolor(ACCENT), 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius + 4.0, radius + 4.0)
        painter.setPen(QPen(qcolor("#00000030"), 1))
        painter.setBrush(qcolor(self._color))
        painter.drawEllipse(center, radius, radius)
        if self.isChecked():
            painter.setPen(QPen(qcolor("#1A1714"), 1.7))
            painter.drawLine(
                QPoint(int(center.x() - 4), int(center.y())),
                QPoint(int(center.x() - 1), int(center.y() + 3)),
            )
            painter.drawLine(
                QPoint(int(center.x() - 1), int(center.y() + 3)),
                QPoint(int(center.x() + 5), int(center.y() - 4)),
            )


class Pill(QWidget):
    def __init__(
        self,
        text: str = "",
        *,
        tone: str = MUTED,
        dot: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._tone = tone
        self._dot = dot
        self._padding = 11
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(26)
        self._update_width()
        self.setAccessibleName(text)

    def _update_width(self) -> None:
        metrics = QFontMetrics(self.font())
        width = metrics.horizontalAdvance(self._text) + self._padding * 2 + (13 if self._dot else 0)
        self.setMinimumWidth(max(44, width + 2))

    def set_text(self, text: str, tone: str | None = None) -> None:
        self._text = text
        if tone:
            self._tone = tone
        self._update_width()
        self.setAccessibleName(text)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(qcolor(BORDER), 1))
        painter.setBrush(qcolor("#1C1916"))
        painter.drawRoundedRect(r, 13, 13)
        x = 10.0
        if self._dot:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(self._tone))
            painter.drawEllipse(QRectF(x, r.center().y() - 3, 6, 6))
            x += 13
        font = QFont(self.font())
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(qcolor(TEXT_DIM if self._tone == MUTED else self._tone))
        painter.drawText(QRectF(x, 0, r.width() - x - 8, self.height()), Qt.AlignmentFlag.AlignVCenter, self._text)


class SliderRow(QWidget):
    value_changed = Signal(float)

    def __init__(
        self,
        label: str,
        *,
        minimum: int,
        maximum: int,
        value: int,
        suffix: str = "",
        description: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._suffix = suffix
        self._label = label
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(4)
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        self.value_label = QLabel("")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value_label.setStyleSheet(f"color:{MUTED}; font-size:10px; font-family:'Cascadia Mono','Consolas';")
        head.addWidget(label_widget)
        head.addStretch(1)
        head.addWidget(self.value_label)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.slider.setAccessibleName(label)
        self.slider.setToolTip(description or label)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider.valueChanged.connect(self._on_value)
        layout.addLayout(head)
        layout.addWidget(self.slider)
        self._on_value(value)
        if description:
            desc = QLabel(description)
            desc.setObjectName("Caption")
            desc.setWordWrap(True)
            layout.addWidget(desc)

    def _on_value(self, value: int) -> None:
        if self._suffix == "%":
            text = f"{value}%"
        elif self._suffix:
            text = f"{value}{self._suffix}"
        else:
            text = str(value)
        self.value_label.setText(text)
        self.value_changed.emit(float(value))

    def set_value(self, value: int) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self._on_value(value)


class SettingRow(QWidget):
    toggled = Signal(bool)

    def __init__(
        self,
        title: str,
        description: str = "",
        *,
        checked: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(10)
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; font-weight:600;")
        text.addWidget(title_label)
        if description:
            desc = QLabel(description)
            desc.setObjectName("Caption")
            desc.setWordWrap(True)
            text.addWidget(desc)
        layout.addLayout(text, 1)
        self.toggle = ToggleSwitch(checked)
        self.toggle.setAccessibleName(title)
        self.toggle.setToolTip(description or title)
        self.toggle.toggled.connect(self.toggled)
        layout.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignTop)

    def set_checked(self, checked: bool) -> None:
        self.toggle.blockSignals(True)
        self.toggle.setChecked(checked)
        self.toggle._offset = 1.0 if checked else 0.0
        self.toggle.update()
        self.toggle.blockSignals(False)


class ComboRow(QWidget):
    changed = Signal(str)

    def __init__(
        self,
        label: str,
        options: Sequence[tuple[str, str]],
        *,
        value: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)
        title = QLabel(label)
        title.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px; font-weight:600;")
        layout.addWidget(title)
        self.combo = QComboBox()
        for key, text in options:
            self.combo.addItem(text, key)
        if value is not None:
            idx = self.combo.findData(value)
            if idx >= 0:
                self.combo.setCurrentIndex(idx)
        self.combo.currentIndexChanged.connect(self._on_change)
        self.combo.setAccessibleName(label)
        layout.addWidget(self.combo)

    def _on_change(self, index: int) -> None:
        self.changed.emit(str(self.combo.itemData(index)))

    def set_value(self, value: str) -> None:
        idx = self.combo.findData(value)
        if idx >= 0 and idx != self.combo.currentIndex():
            self.combo.blockSignals(True)
            self.combo.setCurrentIndex(idx)
            self.combo.blockSignals(False)


class Divider(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background:{BORDER_SOFT}; border:none;")


class HandPreview(QWidget):
    """Live skeleton preview with a legible, always-visible empty state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._landmarks: list[list[float]] = []
        self._gesture = ""
        self._confidence = 0.0
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName("Live hand landmark preview")

    def set_data(self, hand: dict, gesture: dict) -> None:
        self._landmarks = hand.get("landmarks") or []
        self._gesture = str(gesture.get("stable", ""))
        self._confidence = float(gesture.get("confidence", 0.0))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        # Card surface with a subtle warm gradient.
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0, qcolor("#211E1A"))
        gradient.setColorAt(1, qcolor("#171513"))
        painter.setPen(QPen(qcolor(BORDER_SOFT), 1))
        painter.setBrush(gradient)
        painter.drawRoundedRect(rect, 12, 12)
        # Grid.
        painter.setPen(QPen(qcolor("#2B2722"), 1, Qt.PenStyle.DotLine))
        step = 22
        x = int(rect.left()) + 12
        while x < rect.right():
            painter.drawLine(x, int(rect.top()) + 1, x, int(rect.bottom()) - 1)
            x += step
        y = int(rect.top()) + 12
        while y < rect.bottom():
            painter.drawLine(int(rect.left()) + 1, y, int(rect.right()) - 1, y)
            y += step
        if not self._landmarks:
            painter.setPen(QPen(qcolor(FAINT), 1.4))
            draw_icon(painter, "hand", QRectF(rect.center().x() - 23, rect.center().y() - 40, 46, 46), FAINT, 1.2)
            font = QFont(self.font())
            font.setPixelSize(11)
            font.setWeight(QFont.Weight.Medium)
            painter.setFont(font)
            painter.setPen(qcolor(FAINT))
            painter.drawText(
                QRectF(rect.left(), rect.center().y() + 12, rect.width(), 24),
                Qt.AlignmentFlag.AlignCenter,
                "No hand in view",
            )
            self._draw_corners(painter, rect, FAINT)
            return
        points = [QPointF(x * rect.width(), y * rect.height()) for x, y in self._landmarks]
        xs = [p.x() for p in points]
        ys = [p.y() for p in points]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        span = max(0.08, max(maxx - minx, maxy - miny))
        scale = min(rect.width() * 0.58, rect.height() * 0.72) / span
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        target = QPointF(rect.center().x(), rect.center().y() + 2)
        mapped = [QPointF(target.x() + (p.x() - cx) * scale, target.y() + (p.y() - cy) * scale) for p in points]
        # Halo + connections.
        painter.setPen(QPen(qcolor(ACCENT, 36), 11, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for a, b in HAND_CONNECTIONS:
            painter.drawLine(mapped[a], mapped[b])
        painter.setPen(QPen(qcolor(MINT, 215), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for a, b in HAND_CONNECTIONS:
            painter.drawLine(mapped[a], mapped[b])
        for i, point in enumerate(mapped):
            if i in (4, 8, 12, 16, 20):
                painter.setPen(QPen(qcolor(BG), 1))
                painter.setBrush(qcolor(ACCENT if i == 8 else TEXT))
                painter.drawEllipse(point, 4.0 if i == 8 else 2.8, 4.0 if i == 8 else 2.8)
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(qcolor("#D9D2C7"))
                painter.drawEllipse(point, 2.1, 2.1)
        # Fingertip ring.
        tip = mapped[8]
        painter.setPen(QPen(qcolor(ACCENT), 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(tip, 11, 11)
        painter.setPen(QPen(qcolor(ACCENT, 80), 1))
        painter.drawEllipse(tip, 16, 16)
        self._draw_corners(painter, rect, qcolor(BORDER))
        # Confidence line.
        confidence = max(0.0, min(1.0, self._confidence))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor("#2C2721"))
        painter.drawRoundedRect(QRectF(rect.left() + 12, rect.bottom() - 13, rect.width() - 24, 3), 1.5, 1.5)
        if confidence:
            painter.setBrush(qcolor(MINT if confidence >= 0.75 else AMBER))
            painter.drawRoundedRect(QRectF(rect.left() + 12, rect.bottom() - 13, (rect.width() - 24) * confidence, 3), 1.5, 1.5)

    @staticmethod
    def _draw_corners(painter: QPainter, rect: QRectF, color) -> None:
        painter.setPen(QPen(color if isinstance(color, QColor) else qcolor(str(color)), 1.2))
        length = 10
        for x, y, dx, dy in [
            (rect.left() + 8, rect.top() + 8, 1, 1),
            (rect.right() - 8, rect.top() + 8, -1, 1),
            (rect.left() + 8, rect.bottom() - 8, 1, -1),
            (rect.right() - 8, rect.bottom() - 8, -1, -1),
        ]:
            painter.drawLine(QPointF(x, y), QPointF(x + length * dx, y))
            painter.drawLine(QPointF(x, y), QPointF(x, y + length * dy))


class Toast(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._text = ""
        self._tone = MINT
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(180)
        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.timeout.connect(self._fade_out)
        self.hide()

    def show_message(self, text: str, tone: str = "info", ttl: int = 2600) -> None:
        self._text = text
        self._tone = {"success": MINT, "warning": AMBER, "error": DANGER}.get(tone, TEXT_DIM)
        self._resize_to_text()
        self._position()
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._hold.start(ttl)

    def _fade_out(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self._hide_after_fade)

    def _hide_after_fade(self) -> None:
        try:
            self._anim.finished.disconnect(self._hide_after_fade)
        except RuntimeError:
            pass
        if self._effect.opacity() <= 0.01:
            self.hide()

    def _resize_to_text(self) -> None:
        metrics = QFontMetrics(self.font())
        width = min(520, max(220, metrics.horizontalAdvance(self._text) + 62))
        self.setFixedSize(width, 42)

    def _position(self) -> None:
        if self.parentWidget() is None:
            return
        parent = self.parentWidget()
        self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - 54)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setPen(QPen(qcolor(BORDER), 1))
        painter.setBrush(qcolor("#211D19"))
        painter.drawRoundedRect(r, 12, 12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(self._tone))
        painter.drawEllipse(QRectF(16, r.center().y() - 3, 6, 6))
        font = QFont(self.font())
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(qcolor(TEXT))
        painter.drawText(
            QRectF(30, 0, self.width() - 44, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._text,
        )


class SectionHeader(QWidget):
    def __init__(self, eyebrow: str, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        eb = QLabel(eyebrow.upper())
        eb.setObjectName("Eyebrow")
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        layout.addWidget(eb)
        layout.addWidget(title_label)


def hline(parent: QWidget | None = None) -> QFrame:
    line = QFrame(parent)
    line.setFixedHeight(1)
    line.setStyleSheet(f"background:{BORDER_SOFT}; border:none;")
    return line
