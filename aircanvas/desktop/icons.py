"""Vector icons drawn with QPainter (no external icon dependency)."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from .theme import MUTED


def draw_icon(
    painter: QPainter,
    name: str,
    rect: QRectF,
    color: QColor | str = MUTED,
    stroke: float = 1.7,
) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color) if isinstance(color, str) else color, stroke)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    r = rect.adjusted(stroke / 2, stroke / 2, -stroke / 2, -stroke / 2)
    w, h = r.width(), r.height()
    cx, cy = r.center().x(), r.center().y()

    if name == "pen":
        path = QPainterPath()
        path.moveTo(r.left() + w * 0.25, r.bottom() - h * 0.18)
        path.lineTo(r.left() + w * 0.34, r.top() + h * 0.55)
        path.lineTo(r.right() - w * 0.26, r.top() + h * 0.18)
        path.lineTo(r.right() - w * 0.13, r.top() + h * 0.30)
        path.lineTo(r.left() + w * 0.42, r.bottom() - h * 0.08)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(
            QPointF(r.left() + w * 0.31, r.bottom() - h * 0.28),
            QPointF(r.left() + w * 0.42, r.bottom() - h * 0.08),
        )
    elif name == "cursor":
        path = QPainterPath()
        path.moveTo(r.left() + w * 0.28, r.top() + h * 0.12)
        path.lineTo(r.left() + w * 0.28, r.bottom() - h * 0.16)
        path.lineTo(r.left() + w * 0.47, r.bottom() - h * 0.34)
        path.lineTo(r.left() + w * 0.60, r.bottom() - h * 0.06)
        path.lineTo(r.left() + w * 0.72, r.bottom() - h * 0.14)
        path.lineTo(r.left() + w * 0.58, r.bottom() - h * 0.42)
        path.lineTo(r.right() - w * 0.14, r.bottom() - h * 0.38)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "navigate":
        painter.drawLine(QPointF(cx, r.top() + h * 0.16), QPointF(cx, r.bottom() - h * 0.16))
        painter.drawLine(QPointF(r.left() + w * 0.16, cy), QPointF(r.right() - w * 0.16, cy))
        for ax, ay, ang in [
            (cx, r.top() + h * 0.16, -90),
            (cx, r.bottom() - h * 0.16, 90),
            (r.left() + w * 0.16, cy, 180),
            (r.right() - w * 0.16, cy, 0),
        ]:
            a = math.radians(ang)
            size = min(w, h) * 0.13
            left = QPointF(ax + math.cos(a + 2.5) * size, ay + math.sin(a + 2.5) * size)
            right = QPointF(ax + math.cos(a - 2.5) * size, ay + math.sin(a - 2.5) * size)
            painter.drawLine(QPointF(ax, ay), left)
            painter.drawLine(QPointF(ax, ay), right)
    elif name == "track":
        painter.drawEllipse(QRectF(r.left() + w * 0.18, r.top() + h * 0.18, w * 0.64, h * 0.64))
        painter.drawEllipse(QRectF(cx - w * 0.08, cy - h * 0.08, w * 0.16, h * 0.16))
        for x1, y1, x2, y2 in [
            (cx, r.top() + h * 0.04, cx, r.top() + h * 0.16),
            (cx, r.bottom() - h * 0.16, cx, r.bottom() - h * 0.04),
            (r.left() + w * 0.04, cy, r.left() + w * 0.16, cy),
            (r.right() - w * 0.16, cy, r.right() - w * 0.04, cy),
        ]:
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    elif name == "hand":
        path = QPainterPath()
        path.moveTo(r.left() + w * 0.27, r.bottom() - h * 0.20)
        path.lineTo(r.left() + w * 0.24, r.top() + h * 0.46)
        path.quadTo(r.left() + w * 0.24, r.top() + h * 0.34, r.left() + w * 0.33, r.top() + h * 0.34)
        path.quadTo(r.left() + w * 0.41, r.top() + h * 0.34, r.left() + w * 0.42, r.top() + h * 0.46)
        path.lineTo(r.left() + w * 0.43, r.top() + h * 0.20)
        path.quadTo(r.left() + w * 0.44, r.top() + h * 0.08, r.left() + w * 0.53, r.top() + h * 0.09)
        path.quadTo(r.left() + w * 0.61, r.top() + h * 0.10, r.left() + w * 0.60, r.top() + h * 0.22)
        path.lineTo(r.left() + w * 0.60, r.top() + h * 0.40)
        path.lineTo(r.left() + w * 0.63, r.top() + h * 0.16)
        path.quadTo(r.left() + w * 0.66, r.top() + h * 0.05, r.left() + w * 0.74, r.top() + h * 0.08)
        path.quadTo(r.left() + w * 0.81, r.top() + h * 0.11, r.left() + w * 0.78, r.top() + h * 0.24)
        path.lineTo(r.left() + w * 0.74, r.top() + h * 0.50)
        path.lineTo(r.left() + w * 0.81, r.top() + h * 0.34)
        path.quadTo(r.left() + w * 0.88, r.top() + h * 0.27, r.left() + w * 0.92, r.top() + h * 0.36)
        path.quadTo(r.left() + w * 0.96, r.top() + h * 0.44, r.left() + w * 0.86, r.top() + h * 0.60)
        path.lineTo(r.left() + w * 0.72, r.bottom() - h * 0.18)
        path.quadTo(r.left() + w * 0.65, r.bottom() - h * 0.04, r.left() + w * 0.48, r.bottom() - h * 0.04)
        path.quadTo(r.left() + w * 0.34, r.bottom() - h * 0.04, r.left() + w * 0.27, r.bottom() - h * 0.20)
        painter.drawPath(path)
    elif name in ("undo", "redo"):
        path = QPainterPath()
        start = r.left() + w * 0.28 if name == "undo" else r.right() - w * 0.28
        end = r.right() - w * 0.20 if name == "undo" else r.left() + w * 0.20
        path.moveTo(start, r.top() + h * 0.36)
        path.cubicTo(
            QPointF(r.left() + w * 0.45, r.top() + h * 0.15),
            QPointF(r.right() - w * 0.24, r.top() + h * 0.28),
            QPointF(end, r.bottom() - h * 0.30),
        )
        painter.drawPath(path)
        if name == "undo":
            painter.drawLine(QPointF(start, r.top() + h * 0.36), QPointF(start, r.top() + h * 0.16))
            painter.drawLine(QPointF(start, r.top() + h * 0.36), QPointF(start + w * 0.19, r.top() + h * 0.36))
        else:
            painter.drawLine(QPointF(start, r.top() + h * 0.36), QPointF(start, r.top() + h * 0.16))
            painter.drawLine(QPointF(start, r.top() + h * 0.36), QPointF(start - w * 0.19, r.top() + h * 0.36))
    elif name == "trash":
        painter.drawLine(QPointF(r.left() + w * 0.20, r.top() + h * 0.26), QPointF(r.right() - w * 0.20, r.top() + h * 0.26))
        painter.drawLine(QPointF(cx - w * 0.12, r.top() + h * 0.16), QPointF(cx + w * 0.12, r.top() + h * 0.16))
        path = QPainterPath()
        path.moveTo(r.left() + w * 0.27, r.top() + h * 0.30)
        path.lineTo(r.left() + w * 0.32, r.bottom() - h * 0.18)
        path.quadTo(r.left() + w * 0.34, r.bottom() - h * 0.10, r.left() + w * 0.44, r.bottom() - h * 0.10)
        path.lineTo(r.right() - w * 0.44, r.bottom() - h * 0.10)
        path.quadTo(r.right() - w * 0.34, r.bottom() - h * 0.10, r.right() - w * 0.32, r.bottom() - h * 0.18)
        path.lineTo(r.right() - w * 0.27, r.top() + h * 0.30)
        painter.drawPath(path)
        painter.drawLine(QPointF(cx - w * 0.10, r.top() + h * 0.46), QPointF(cx - w * 0.06, r.bottom() - h * 0.28))
        painter.drawLine(QPointF(cx + w * 0.10, r.top() + h * 0.46), QPointF(cx + w * 0.06, r.bottom() - h * 0.28))
    elif name == "download":
        painter.drawLine(QPointF(cx, r.top() + h * 0.14), QPointF(cx, r.bottom() - h * 0.42))
        painter.drawLine(QPointF(cx, r.bottom() - h * 0.40), QPointF(cx - w * 0.17, r.bottom() - h * 0.58))
        painter.drawLine(QPointF(cx, r.bottom() - h * 0.40), QPointF(cx + w * 0.17, r.bottom() - h * 0.58))
        painter.drawLine(QPointF(r.left() + w * 0.16, r.bottom() - h * 0.18), QPointF(r.right() - w * 0.16, r.bottom() - h * 0.18))
    elif name == "overlay":
        painter.drawRoundedRect(QRectF(r.left() + w * 0.06, r.top() + h * 0.16, w * 0.58, h * 0.50), 2, 2)
        painter.drawRoundedRect(QRectF(r.left() + w * 0.34, r.top() + h * 0.38, w * 0.60, h * 0.50), 2, 2)
    elif name == "help":
        painter.drawEllipse(QRectF(r.left() + w * 0.10, r.top() + h * 0.10, w * 0.80, h * 0.80))
        painter.drawArc(
            QRectF(cx - w * 0.17, r.top() + h * 0.27, w * 0.34, h * 0.29),
            20 * 16,
            250 * 16,
        )
        painter.drawPoint(QPointF(cx, r.top() + h * 0.76))
    elif name == "settings":
        for y in (0.32, 0.5, 0.68):
            painter.drawLine(QPointF(r.left() + w * 0.14, r.top() + h * y), QPointF(r.right() - w * 0.14, r.top() + h * y))
            px = r.left() + w * (0.34 if y != 0.5 else 0.62)
            painter.setBrush(QColor(color) if isinstance(color, str) else color)
            painter.drawEllipse(QPointF(px, r.top() + h * y), stroke * 2.0, stroke * 2.0)
            painter.setBrush(Qt.BrushStyle.NoBrush)
    elif name == "camera":
        painter.drawRoundedRect(QRectF(r.left() + w * 0.08, r.top() + h * 0.28, w * 0.68, h * 0.48), 3, 3)
        path = QPainterPath()
        path.moveTo(r.left() + w * 0.76, r.top() + h * 0.42)
        path.lineTo(r.left() + w * 0.94, r.top() + h * 0.30)
        path.lineTo(r.left() + w * 0.94, r.top() + h * 0.72)
        path.lineTo(r.left() + w * 0.76, r.top() + h * 0.60)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawEllipse(QPointF(r.left() + w * 0.42, r.top() + h * 0.52), w * 0.12, h * 0.12)
    elif name == "sparkle":
        path = QPainterPath()
        path.moveTo(cx, r.top() + h * 0.10)
        path.lineTo(cx + w * 0.10, cy - h * 0.10)
        path.lineTo(r.right() - w * 0.10, cy)
        path.lineTo(cx + w * 0.10, cy + h * 0.10)
        path.lineTo(cx, r.bottom() - h * 0.10)
        path.lineTo(cx - w * 0.10, cy + h * 0.10)
        path.lineTo(r.left() + w * 0.10, cy)
        path.lineTo(cx - w * 0.10, cy - h * 0.10)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "check":
        painter.drawLine(QPointF(r.left() + w * 0.18, cy), QPointF(cx - w * 0.02, r.bottom() - h * 0.24))
        painter.drawLine(QPointF(cx - w * 0.02, r.bottom() - h * 0.24), QPointF(r.right() - w * 0.16, r.top() + h * 0.26))
    elif name == "close":
        painter.drawLine(QPointF(r.left() + w * 0.24, r.top() + h * 0.24), QPointF(r.right() - w * 0.24, r.bottom() - h * 0.24))
        painter.drawLine(QPointF(r.right() - w * 0.24, r.top() + h * 0.24), QPointF(r.left() + w * 0.24, r.bottom() - h * 0.24))
    elif name == "minimize":
        painter.drawLine(QPointF(r.left() + w * 0.22, cy), QPointF(r.right() - w * 0.22, cy))
    elif name == "maximize":
        painter.drawRoundedRect(QRectF(r.left() + w * 0.22, r.top() + h * 0.22, w * 0.56, h * 0.56), 1, 1)
    elif name == "chevron":
        painter.drawLine(QPointF(r.left() + w * 0.28, cy - h * 0.12), QPointF(cx, cy + h * 0.14))
        painter.drawLine(QPointF(cx, cy + h * 0.14), QPointF(r.right() - w * 0.28, cy - h * 0.12))
    elif name == "eye":
        path = QPainterPath()
        path.moveTo(r.left() + w * 0.10, cy)
        path.quadTo(cx, r.top() + h * 0.18, r.right() - w * 0.10, cy)
        path.quadTo(cx, r.bottom() - h * 0.18, r.left() + w * 0.10, cy)
        painter.drawPath(path)
        painter.drawEllipse(QPointF(cx, cy), w * 0.09, h * 0.09)
    elif name == "pause":
        painter.drawLine(QPointF(cx - w * 0.14, r.top() + h * 0.22), QPointF(cx - w * 0.14, r.bottom() - h * 0.22))
        painter.drawLine(QPointF(cx + w * 0.14, r.top() + h * 0.22), QPointF(cx + w * 0.14, r.bottom() - h * 0.22))
    elif name == "play":
        path = QPainterPath()
        path.moveTo(r.left() + w * 0.30, r.top() + h * 0.20)
        path.lineTo(r.right() - w * 0.22, cy)
        path.lineTo(r.left() + w * 0.30, r.bottom() - h * 0.20)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "plus":
        painter.drawLine(QPointF(cx, r.top() + h * 0.20), QPointF(cx, r.bottom() - h * 0.20))
        painter.drawLine(QPointF(r.left() + w * 0.20, cy), QPointF(r.right() - w * 0.20, cy))
    else:
        painter.drawEllipse(QRectF(cx - w * 0.3, cy - h * 0.3, w * 0.6, h * 0.6))
    painter.restore()
