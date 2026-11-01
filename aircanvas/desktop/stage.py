"""The central interaction stage: canvas, mirrored camera feed and overlays."""

from __future__ import annotations

import math
import time
from collections import deque

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..geometry import Point, aspect_fit_rect
from ..gestures import HAND_CONNECTIONS
from .icons import draw_icon
from .theme import (
    ACCENT,
    AMBER,
    DANGER,
    FAINT,
    MINT,
    PAPER,
    PAPER_2,
    SKY,
    TEXT,
    TEXT_DIM,
    qcolor,
)


class StageWidget(QWidget):
    manual_begin = Signal(float, float)
    manual_move = Signal(float, float)
    manual_end = Signal()
    surface_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(QSize(520, 380))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("AirCanvas interaction stage")
        self._snapshot: dict = {}
        self._frame: QImage | None = None
        self._ambient: QImage | None = None
        self._cursor_trail: deque[tuple[Point, float]] = deque(maxlen=18)
        self._ripples: list[tuple[float, float, float, str]] = []
        self._manual_down = False
        self._hover = False
        self._last_frame_at = 0.0
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._animate)
        self._timer.start()

    # ------------------------------------------------------------------ data
    def set_snapshot(self, snapshot: dict) -> None:
        previous = self._snapshot
        self._snapshot = snapshot or {}
        pointer = self._snapshot.get("pointer", {})
        if pointer.get("visible"):
            point = Point(float(pointer.get("x", 0.5)), float(pointer.get("y", 0.5)))
            if not self._cursor_trail or self._cursor_trail[-1][0].distance(point) > 0.001:
                self._cursor_trail.append((point, time.monotonic()))
        else:
            self._cursor_trail.clear()
        # New click events create ripples even when OS control is off.
        events = self._snapshot.get("events", [])
        last_ids = {e.get("id") for e in previous.get("events", [])}
        for event in events:
            if event.get("id") in last_ids:
                continue
            if event.get("kind") == "click":
                data = event.get("data", {})
                self._ripples.append(
                    (
                        float(data.get("x", 0.5)),
                        float(data.get("y", 0.5)),
                        time.monotonic(),
                        str(data.get("button", "left")),
                    )
                )
        self.update()

    def set_frame(self, image: QImage | None) -> None:
        if image is not None and not image.isNull():
            self._frame = image
            self._ambient = image.scaled(
                64,
                36,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._last_frame_at = time.monotonic()
        elif image is None:
            self._frame = None
            self._ambient = None
        self.update()

    def clear_frame(self) -> None:
        self._frame = None
        self._ambient = None
        self.update()

    @property
    def snapshot(self) -> dict:
        return self._snapshot

    def flash_click(self, x: float, y: float, button: str = "left") -> None:
        self._ripples.append((x, y, time.monotonic(), button))
        self.update()

    def _animate(self) -> None:
        self._pulse = (time.monotonic() * 0.55) % 1.0
        if self._ripples:
            now = time.monotonic()
            self._ripples = [r for r in self._ripples if now - r[2] < 0.65]
        self.update()

    # ------------------------------------------------------------------ geometry
    def _mode(self) -> str:
        return str(self._snapshot.get("mode", "screen"))

    def _stage_rect(self) -> QRectF:
        return QRectF(self.rect()).adjusted(14, 14, -14, -14)

    def _paper_rect(self) -> QRectF:
        r = self._stage_rect().adjusted(22, 22, -22, -22)
        return r

    def _video_rect(self) -> QRectF:
        area = self._stage_rect().adjusted(12, 12, -12, -12)
        if self._frame is None:
            return area
        return QRectF(*aspect_fit_rect(self._frame.width(), self._frame.height(), area.width(), area.height())).translated(
            area.left(), area.top()
        )

    def _map_point(self, point: Point, rect: QRectF) -> QPointF:
        return QPointF(rect.left() + point.x * rect.width(), rect.top() + point.y * rect.height())

    def _active_rect(self) -> QRectF:
        return self._video_rect() if self._mode() == "mirror" else self._paper_rect()

    def _point_from_widget(self, pos: QPoint) -> Point | None:
        rect = self._active_rect()
        if not rect.contains(QPointF(pos)):
            return None
        return Point(
            max(0.0, min(1.0, (pos.x() - rect.left()) / max(1.0, rect.width()))),
            max(0.0, min(1.0, (pos.y() - rect.top()) / max(1.0, rect.height()))),
        )

    # ------------------------------------------------------------------ paint
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        outer = QRectF(self.rect())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor("#0C0B0A"))
        painter.drawRoundedRect(outer, 18, 18)
        if self._mode() == "mirror":
            self._paint_mirror(painter)
        else:
            self._paint_screen(painter)
        # Ripples are drawn above both modes.
        self._paint_ripples(painter)

    def _paint_screen(self, painter: QPainter) -> None:
        paper = self._paper_rect()
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor("#191613"))
        painter.drawRoundedRect(self._stage_rect(), 14, 14)
        # Paper shadow.
        shadow = QPainterPath()
        shadow.addRoundedRect(paper.translated(0, 5), 12, 12)
        painter.setBrush(QColor(0, 0, 0, 90))
        painter.drawPath(shadow)
        gradient = QLinearGradient(paper.topLeft(), paper.bottomRight())
        gradient.setColorAt(0, qcolor("#F4EFE6"))
        gradient.setColorAt(0.58, qcolor(PAPER))
        gradient.setColorAt(1, qcolor(PAPER_2))
        painter.setBrush(gradient)
        painter.setPen(QPen(qcolor("#CEC5B7"), 1))
        painter.drawRoundedRect(paper, 10, 10)
        painter.setClipPath(self._rounded_path(paper, 10))
        # Paper dot grid.
        painter.setPen(QPen(qcolor("#D8D0C3"), 1, Qt.PenStyle.SolidLine))
        spacing = 28
        y = paper.top() + 22
        while y < paper.bottom() - 10:
            x = paper.left() + 22
            while x < paper.right() - 10:
                painter.drawPoint(QPointF(x, y))
                x += spacing
            y += spacing
        # Faint brand watermark.
        font = QFont(self.font())
        font.setPixelSize(max(34, int(paper.width() * 0.058)))
        font.setWeight(QFont.Weight.Black)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 6)
        painter.setFont(font)
        painter.setPen(qcolor("#E2DACD"))
        painter.drawText(
            QRectF(paper.left() + 34, paper.bottom() - 96, paper.width() - 340, 76),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
            "AIRCANVAS",
        )
        self._paint_strokes(painter, paper, mirror=False)
        painter.setClipping(False)
        # Canvas label.
        self._paint_stage_chip(painter, paper.left() + 16, paper.top() + 14, "LIVE CANVAS", ACCENT)
        self._paint_paper_hint(painter, paper)
        self._paint_cursor(painter, paper)
        self._paint_nav_hud(painter, paper)
        if self._snapshot.get("config", {}).get("show_camera_pip", True):
            self._paint_pip(painter)
        painter.restore()

    def _paint_mirror(self, painter: QPainter) -> None:
        area = self._stage_rect()
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor("#0D0C0B"))
        painter.drawRoundedRect(area, 14, 14)
        video = self._video_rect()
        if self._ambient is not None:
            painter.save()
            painter.setClipPath(self._rounded_path(area, 14))
            self._paint_cover_image(painter, self._ambient, area)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(8, 7, 6, 168))
            painter.drawRect(area)
            painter.restore()
        painter.setClipPath(self._rounded_path(video, 11))
        if self._frame is not None:
            painter.drawImage(video, self._frame)
            # Cinematic vignette so UI overlays remain legible.
            top = QLinearGradient(0, video.top(), 0, video.top() + 140)
            top.setColorAt(0, QColor(0, 0, 0, 110))
            top.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setBrush(top)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(QRectF(video.left(), video.top(), video.width(), 140))
            bottom = QLinearGradient(0, video.bottom() - 170, 0, video.bottom())
            bottom.setColorAt(0, QColor(0, 0, 0, 0))
            bottom.setColorAt(1, QColor(0, 0, 0, 165))
            painter.setBrush(bottom)
            painter.drawRect(QRectF(video.left(), video.bottom() - 170, video.width(), 170))
        else:
            self._paint_empty_video(painter, video)
        self._paint_strokes(painter, video, mirror=True)
        self._paint_tracks(painter, video)
        self._paint_selection(painter, video)
        if self._snapshot.get("config", {}).get("show_landmarks", True):
            self._paint_hand(painter, video, compact=False)
        self._paint_cursor(painter, video)
        painter.setClipping(False)
        # Edge ring.
        painter.setPen(QPen(qcolor("#3B342C"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(video, 11, 11)
        mode = "MIRROR"
        tool = str(self._snapshot.get("mirror_tool", "track")).upper()
        self._paint_stage_chip(painter, video.left() + 16, video.top() + 16, f"{mode}  /  {tool}", MINT)
        if self._snapshot.get("camera", {}).get("demo"):
            self._paint_stage_chip(
                painter,
                video.left() + 132,
                video.top() + 16,
                "SIMULATED",
                AMBER,
                compact=True,
            )
        tracks = self._snapshot.get("tracks", [])
        if tracks:
            active = sum(1 for t in tracks if t.get("status") in ("tracking", "occluded", "reacquiring"))
            self._paint_stage_chip(
                painter,
                video.right() - 118,
                video.top() + 16,
                f"{active} TRACKED",
                MINT if active else AMBER,
            )
        self._paint_mirror_hint(painter, video)
        self._paint_shot_corners(painter, video)
        painter.restore()

    @staticmethod
    def _paint_cover_image(painter: QPainter, image: QImage, rect: QRectF) -> None:
        source = QRectF(image.rect())
        target_aspect = rect.width() / max(1.0, rect.height())
        if source.width() / max(1.0, source.height()) > target_aspect:
            crop_w = source.height() * target_aspect
            source = QRectF(source.center().x() - crop_w / 2, 0, crop_w, source.height())
        else:
            crop_h = source.width() / target_aspect
            source = QRectF(0, source.center().y() - crop_h / 2, source.width(), crop_h)
        painter.drawImage(rect, image, source)

    def _paint_empty_video(self, painter: QPainter, rect: QRectF) -> None:
        painter.setBrush(qcolor("#141210"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 11, 11)
        painter.setPen(QPen(qcolor("#27221D"), 1, Qt.PenStyle.DotLine))
        step = 34
        x = rect.left() + 20
        while x < rect.right() - 10:
            painter.drawLine(QPointF(x, rect.top() + 10), QPointF(x, rect.bottom() - 10))
            x += step
        y = rect.top() + 20
        while y < rect.bottom() - 10:
            painter.drawLine(QPointF(rect.left() + 10, y), QPointF(rect.right() - 10, y))
            y += step
        painter.setPen(QPen(qcolor(FAINT), 1.3))
        draw_icon(
            painter,
            "camera",
            QRectF(rect.center().x() - 30, rect.center().y() - 65, 60, 60),
            FAINT,
            1.2,
        )
        font = QFont(self.font())
        font.setPixelSize(14)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(qcolor(TEXT_DIM))
        painter.drawText(
            QRectF(rect.left(), rect.center().y() + 4, rect.width(), 24),
            Qt.AlignmentFlag.AlignCenter,
            "Camera feed offline",
        )
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(qcolor(FAINT))
        painter.drawText(
            QRectF(rect.left(), rect.center().y() + 30, rect.width(), 40),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "Start a webcam or use the simulated feed",
        )

    # ------------------------------------------------------------------ drawing
    def _paint_strokes(self, painter: QPainter, rect: QRectF, *, mirror: bool) -> None:
        drawing = self._snapshot.get("drawing", {})
        strokes = drawing.get("strokes", [])
        current = drawing.get("current")
        all_strokes = list(strokes)
        if current:
            all_strokes.append(current)
        for index, stroke in enumerate(all_strokes):
            points = stroke.get("points", [])
            if len(points) < 2:
                continue
            color = QColor(stroke.get("color", ACCENT))
            width = float(stroke.get("width", 5.0))
            px_width = max(1.5, width * min(rect.width(), rect.height()) / 870.0 * 1.25)
            if current is not None and index == len(all_strokes) - 1:
                color.setAlpha(225)
            if stroke.get("kind") == "circle":
                # Corrected circles are stored in normalised document space;
                # render a true physical circle so they remain circular on any
                # stage aspect ratio.
                box = self._points_box(points, rect)
                radius = (box.width() + box.height()) / 4.0
                path = QPainterPath()
                path.addEllipse(box.center(), radius, radius)
            else:
                path = self._smooth_path(points, rect)
                if stroke.get("closed"):
                    path.closeSubpath()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            # Soft halo under the stroke for a marker-like feel.
            halo = QColor(color)
            halo.setAlpha(38 if not mirror else 60)
            painter.setPen(QPen(halo, px_width * 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(path)
            painter.setPen(QPen(color, px_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(path)

    @staticmethod
    def _smooth_path(points: list, rect: QRectF) -> QPainterPath:
        mapped = [QPointF(rect.left() + float(p[0]) * rect.width(), rect.top() + float(p[1]) * rect.height()) for p in points]
        path = QPainterPath(mapped[0])
        if len(mapped) == 2:
            path.lineTo(mapped[1])
            return path
        for i in range(1, len(mapped) - 1):
            mid = QPointF((mapped[i].x() + mapped[i + 1].x()) / 2, (mapped[i].y() + mapped[i + 1].y()) / 2)
            path.quadTo(mapped[i], mid)
        path.lineTo(mapped[-1])
        return path

    @staticmethod
    def _points_box(points: list, rect: QRectF) -> QRectF:
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        left = rect.left() + min(xs) * rect.width()
        top = rect.top() + min(ys) * rect.height()
        right = rect.left() + max(xs) * rect.width()
        bottom = rect.top() + max(ys) * rect.height()
        return QRectF(left, top, max(1, right - left), max(1, bottom - top))

    # ------------------------------------------------------------------ overlays
    def _paint_cursor(self, painter: QPainter, rect: QRectF) -> None:
        pointer = self._snapshot.get("pointer", {})
        if not pointer.get("visible"):
            return
        p = self._map_point(Point(float(pointer.get("x", 0.5)), float(pointer.get("y", 0.5))), rect)
        kind = str(pointer.get("kind", "crosshair"))
        pressed = bool(pointer.get("pressed", False))
        # Trail.
        if len(self._cursor_trail) > 2:
            for i in range(1, len(self._cursor_trail)):
                age = time.monotonic() - self._cursor_trail[i][1]
                if age > 0.35:
                    continue
                a = self._map_point(self._cursor_trail[i - 1][0], rect)
                b = self._map_point(self._cursor_trail[i][0], rect)
                painter.setPen(QPen(qcolor(ACCENT, int(55 * (1 - age / 0.35))), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(a, b)
        painter.save()
        if kind == "mouse":
            painter.setPen(QPen(qcolor(TEXT), 1.4))
            painter.setBrush(qcolor(ACCENT if pressed else "#F7F2E8"))
            arrow = QPolygonF(
                [
                    QPointF(p.x(), p.y()),
                    QPointF(p.x(), p.y() + 22),
                    QPointF(p.x() + 6, p.y() + 17),
                    QPointF(p.x() + 12, p.y() + 27),
                    QPointF(p.x() + 16, p.y() + 24),
                    QPointF(p.x() + 10, p.y() + 15),
                    QPointF(p.x() + 18, p.y() + 14),
                ]
            )
            painter.drawPolygon(arrow)
        elif kind == "navigate":
            pulse = 1.0 + 0.18 * math.sin(self._pulse * math.pi * 2)
            painter.setPen(QPen(qcolor(ACCENT, 190), 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(p, 22 * pulse, 22 * pulse)
            painter.setPen(QPen(qcolor(ACCENT), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for dx, dy in ((0, -13), (0, 13), (-13, 0), (13, 0)):
                painter.drawLine(p, QPointF(p.x() + dx, p.y() + dy))
        else:
            glow = QRadialGradient(p, 28)
            glow.setColorAt(0, qcolor(ACCENT, 52 if not pressed else 95))
            glow.setColorAt(1, qcolor(ACCENT, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(p, 28, 28)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcolor(TEXT, 210), 1.5))
            painter.drawEllipse(p, 10, 10)
            painter.setPen(QPen(qcolor(ACCENT), 2.0))
            painter.drawEllipse(p, 13, 13)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor(ACCENT if pressed else MINT))
            painter.drawEllipse(p, 3.4, 3.4)
            if kind == "crosshair":
                painter.setPen(QPen(qcolor(TEXT, 150), 1))
                painter.drawLine(QPointF(p.x() - 17, p.y()), QPointF(p.x() - 14, p.y()))
                painter.drawLine(QPointF(p.x() + 14, p.y()), QPointF(p.x() + 17, p.y()))
                painter.drawLine(QPointF(p.x(), p.y() - 17), QPointF(p.x(), p.y() - 14))
                painter.drawLine(QPointF(p.x(), p.y() + 14), QPointF(p.x(), p.y() + 17))
        label = pointer.get("label")
        if label and self._hover:
            self._paint_pointer_label(painter, p, str(label))
        painter.restore()

    def _paint_pointer_label(self, painter: QPainter, point: QPointF, text: str) -> None:
        font = QFont(self.font())
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        width = painter.fontMetrics().horizontalAdvance(text) + 18
        rect = QRectF(point.x() + 20, point.y() + 16, min(width, 220), 24)
        if rect.right() > self.width() - 20:
            rect.moveLeft(point.x() - rect.width() - 20)
        painter.setPen(QPen(qcolor("#443A30"), 1))
        painter.setBrush(qcolor("#1D1915", 220))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(qcolor(TEXT_DIM))
        painter.drawText(rect.adjusted(9, 0, -9, 0), Qt.AlignmentFlag.AlignVCenter, text)

    def _paint_pip(self, painter: QPainter) -> None:
        area = self._stage_rect().adjusted(22, 22, -22, -22)
        width = min(282, max(190, area.width() * 0.27))
        height = width * 9 / 16
        rect = QRectF(area.right() - width - 18, area.bottom() - height - 18, width, height)
        painter.save()
        painter.setPen(QPen(qcolor("#4A4036"), 1))
        painter.setBrush(qcolor("#0E0D0C"))
        painter.drawRoundedRect(rect, 10, 10)
        painter.setClipPath(self._rounded_path(rect, 10))
        if self._frame is not None:
            source = QRectF(self._frame.rect())
            target_aspect = rect.width() / rect.height()
            if source.width() / source.height() > target_aspect:
                crop_w = source.height() * target_aspect
                source = QRectF(source.center().x() - crop_w / 2, 0, crop_w, source.height())
            else:
                crop_h = source.width() / target_aspect
                source = QRectF(0, source.center().y() - crop_h / 2, source.width(), crop_h)
            painter.drawImage(rect, self._frame, source)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(qcolor("#171411"))
            painter.drawRect(rect)
            draw_icon(painter, "camera", QRectF(rect.center().x() - 16, rect.center().y() - 20, 32, 32), FAINT, 1.2)
            painter.setPen(qcolor(FAINT))
            f = QFont(self.font())
            f.setPixelSize(9)
            painter.setFont(f)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "\n\nCAMERA OFF")
        if self._snapshot.get("hand", {}).get("visible") and self._snapshot.get("config", {}).get("show_landmarks", True):
            self._paint_hand(painter, rect, compact=True)
        painter.setClipping(False)
        painter.setPen(QPen(qcolor("#4A4036"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 10, 10)
        # Live dot and label.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(MINT if self._frame is not None else FAINT))
        painter.drawEllipse(QRectF(rect.left() + 9, rect.top() + 9, 5, 5))
        f = QFont(self.font())
        f.setPixelSize(8)
        f.setWeight(QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        painter.setFont(f)
        painter.setPen(qcolor("#F4EFE5"))
        painter.drawText(QRectF(rect.left() + 19, rect.top() + 4, 100, 16), Qt.AlignmentFlag.AlignVCenter, "REC")
        painter.restore()

    def _paint_tracks(self, painter: QPainter, rect: QRectF) -> None:
        for marker in self._snapshot.get("tracks", []):
            bbox = marker.get("bbox") or [0, 0, 0, 0]
            x, y, w, h = (float(v) for v in bbox)
            box = QRectF(rect.left() + x * rect.width(), rect.top() + y * rect.height(), w * rect.width(), h * rect.height())
            status = marker.get("status", "tracking")
            color = MINT if status == "tracking" else (AMBER if status in ("occluded", "reacquiring") else DANGER)
            if status in ("lost", "out_of_view"):
                color = DANGER if status == "out_of_view" else AMBER
            alpha = 180 if status in ("tracking", "occluded", "reacquiring") else 110
            painter.save()
            dash = status in ("occluded", "reacquiring", "lost")
            pen = QPen(qcolor(color, alpha), 2.0, Qt.PenStyle.DashLine if dash else Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(box.adjusted(-4, -4, 4, 4), 12, 12)
            # Corner brackets.
            painter.setPen(QPen(qcolor(color, 240), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            length = min(20.0, box.width() * 0.22, box.height() * 0.22)
            for cx, cy, dx, dy in [
                (box.left() - 4, box.top() - 4, 1, 1),
                (box.right() + 4, box.top() - 4, -1, 1),
                (box.left() - 4, box.bottom() + 4, 1, -1),
                (box.right() + 4, box.bottom() + 4, -1, -1),
            ]:
                painter.drawLine(QPointF(cx, cy), QPointF(cx + length * dx, cy))
                painter.drawLine(QPointF(cx, cy), QPointF(cx, cy + length * dy))
            # Pulsing target dot.
            if status == "tracking":
                radius = 3.0 + 1.2 * self._pulse
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(qcolor(color))
                painter.drawEllipse(box.center(), radius, radius)
            # Label chip.
            label = str(marker.get("label", "Object"))
            subtitle = {
                "tracking": "TRACKING",
                "occluded": "OCCLUDED · SEARCHING",
                "reacquiring": "RE-ACQUIRING",
                "lost": "LOST",
                "out_of_view": "LEFT VIEW",
            }.get(status, status.upper())
            font = QFont(self.font())
            font.setPixelSize(9)
            font.setWeight(QFont.Weight.Bold)
            painter.setFont(font)
            text_w = max(painter.fontMetrics().horizontalAdvance(label), painter.fontMetrics().horizontalAdvance(subtitle)) + 20
            chip = QRectF(box.left() - 4, box.top() - 45, max(118, min(text_w, 220)), 36)
            if chip.top() < rect.top() + 8:
                chip.moveTop(box.top() - 4)
            if chip.right() > rect.right() - 6:
                chip.moveRight(box.right() + 4)
            if chip.left() < rect.left() + 6:
                chip.moveLeft(box.left() - 4)
            painter.setPen(QPen(qcolor(color, 150), 1))
            painter.setBrush(qcolor("#14110E", 232))
            painter.drawRoundedRect(chip, 7, 7)
            painter.setPen(qcolor(TEXT))
            painter.drawText(chip.adjusted(9, 2, -8, -17), Qt.AlignmentFlag.AlignVCenter, label)
            f2 = QFont(self.font())
            f2.setPixelSize(7)
            f2.setWeight(QFont.Weight.Bold)
            f2.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
            painter.setFont(f2)
            painter.setPen(qcolor(color))
            painter.drawText(chip.adjusted(9, 18, -8, -1), Qt.AlignmentFlag.AlignVCenter, subtitle)
            painter.restore()

    def _paint_selection(self, painter: QPainter, rect: QRectF) -> None:
        selection = self._snapshot.get("selection", {})
        points = selection.get("points", [])
        if not points:
            return
        mapped = [QPointF(rect.left() + float(p[0]) * rect.width(), rect.top() + float(p[1]) * rect.height()) for p in points]
        path = QPainterPath(mapped[0])
        for point in mapped[1:]:
            path.lineTo(point)
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(qcolor(MINT, 45), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)
        painter.setPen(QPen(qcolor(MINT, 220), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)
        end = mapped[-1]
        progress = float(selection.get("progress", 0.0))
        radius = 17
        painter.setPen(QPen(QColor(0, 0, 0, 90), 4))
        painter.drawEllipse(end, radius + 2, radius + 2)
        painter.setPen(QPen(qcolor(MINT, 70), 3))
        painter.drawEllipse(end, radius, radius)
        painter.setPen(QPen(qcolor(MINT), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(end.x() - radius, end.y() - radius, radius * 2, radius * 2), 90 * 16, -int(progress * 360 * 16))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(MINT))
        painter.drawEllipse(end, 4, 4)
        painter.restore()

    def _paint_hand(self, painter: QPainter, rect: QRectF, *, compact: bool) -> None:
        landmarks = self._snapshot.get("hand", {}).get("landmarks") or []
        if len(landmarks) != 21:
            return
        points = [QPointF(rect.left() + float(p[0]) * rect.width(), rect.top() + float(p[1]) * rect.height()) for p in landmarks]
        base_width = 2.0 if not compact else 1.2
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(qcolor("#0B0A09", 90), base_width * 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for a, b in HAND_CONNECTIONS:
            painter.drawLine(points[a], points[b])
        painter.setPen(QPen(qcolor("#F8F2E8", 205 if not compact else 160), base_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for a, b in HAND_CONNECTIONS:
            painter.drawLine(points[a], points[b])
        for i, point in enumerate(points):
            if i in (4, 8, 12, 16, 20):
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(qcolor(ACCENT if i == 8 else "#F8F2E8"))
                painter.drawEllipse(point, (3.6 if i == 8 else 2.5) if not compact else 2.0, (3.6 if i == 8 else 2.5) if not compact else 2.0)
            elif not compact:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(qcolor("#D6CEC1"))
                painter.drawEllipse(point, 1.8, 1.8)
        if not compact:
            tip = points[8]
            painter.setPen(QPen(qcolor(ACCENT, 80), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(tip, 15 + 2 * math.sin(self._pulse * math.pi * 2), 15 + 2 * math.sin(self._pulse * math.pi * 2))
            painter.setPen(QPen(qcolor(ACCENT), 1.3))
            painter.drawEllipse(tip, 10, 10)
        painter.restore()

    def _paint_nav_hud(self, painter: QPainter, rect: QRectF) -> None:
        tool = str(self._snapshot.get("tool", ""))
        if tool != "navigate":
            return
        nav = self._snapshot.get("nav", {})
        hint = str(nav.get("hint", "Hold an open palm, then swipe"))
        progress = float(nav.get("progress", 0.0))
        armed = bool(nav.get("armed", False))
        font = QFont(self.font())
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        width = min(rect.width() - 32, max(220, painter.fontMetrics().horizontalAdvance(hint) + 52))
        bar = QRectF(rect.center().x() - width / 2, rect.bottom() - 50, width, 30)
        painter.setPen(QPen(qcolor("#D8D0C3"), 1))
        painter.setBrush(qcolor("#F2EEE5", 235))
        painter.drawRoundedRect(bar, 15, 15)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(MINT if armed else ACCENT))
        painter.drawEllipse(QRectF(bar.left() + 12, bar.center().y() - 3, 6, 6))
        painter.setPen(qcolor("#4B453C"))
        painter.drawText(bar.adjusted(26, 0, -12, 0), Qt.AlignmentFlag.AlignVCenter, hint)
        # Four-direction compass fades in while arming.
        if progress > 0.03:
            center = QPointF(rect.center().x(), rect.center().y() - 20)
            alpha = int(60 + 140 * min(1.0, progress))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcolor(ACCENT, alpha), 1.4, Qt.PenStyle.DashLine))
            painter.drawEllipse(center, 46, 46)
            painter.setPen(QPen(qcolor(ACCENT, alpha), 1.6))
            for dx, dy in ((0, -58), (0, 58), (-58, 0), (58, 0)):
                painter.drawLine(center, QPointF(center.x() + dx * 0.75, center.y() + dy * 0.75))
            painter.setPen(QPen(qcolor(ACCENT), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawArc(QRectF(center.x() - 46, center.y() - 46, 92, 92), 90 * 16, -int(progress * 360 * 16))

    # ------------------------------------------------------------------ misc paint
    def _paint_ripples(self, painter: QPainter) -> None:
        now = time.monotonic()
        for x, y, started, button in self._ripples:
            age = now - started
            if age > 0.65:
                continue
            t = age / 0.65
            center = self._map_point(Point(x, y), self._active_rect())
            radius = 10 + 34 * t
            alpha = int(160 * (1 - t))
            color = ACCENT if button == "left" else SKY
            painter.setPen(QPen(qcolor(color, alpha), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius, radius)
            painter.setPen(QPen(qcolor(color, alpha // 2), 1))
            painter.drawEllipse(center, radius + 7, radius + 7)

    def _paint_stage_chip(self, painter: QPainter, x: float, y: float, text: str, color: str, *, compact: bool = False) -> None:
        font = QFont(self.font())
        font.setPixelSize(8 if compact else 9)
        font.setWeight(QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2 if not compact else 0.8)
        painter.setFont(font)
        width = painter.fontMetrics().horizontalAdvance(text) + (24 if not compact else 18)
        rect = QRectF(x, y, width, 22 if not compact else 19)
        painter.setPen(QPen(qcolor(color, 85), 1))
        painter.setBrush(qcolor("#100E0C", 205))
        painter.drawRoundedRect(rect, 5, 5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(color))
        if not compact:
            painter.drawEllipse(QRectF(rect.left() + 9, rect.center().y() - 2.5, 5, 5))
        painter.setPen(qcolor(color))
        painter.drawText(rect.adjusted(19 if not compact else 8, 0, -7, 0), Qt.AlignmentFlag.AlignVCenter, text)

    def _paint_paper_hint(self, painter: QPainter, rect: QRectF) -> None:
        if self._snapshot.get("drawing", {}).get("strokes"):
            return
        font = QFont(self.font())
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(qcolor("#8C8477"))
        painter.drawText(
            QRectF(rect.left() + 44, rect.top() + 48, rect.width() - 88, 80),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            "Point to draw in the air.\nUse the mouse as an alternative.",
        )
        font.setPixelSize(10)
        painter.setFont(font)
        painter.setPen(qcolor("#A99F90"))
        painter.drawText(
            QRectF(rect.left() + 44, rect.top() + 104, rect.width() - 88, 30),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            "Smart shapes corrects deliberate circles when enabled.",
        )

    def _paint_mirror_hint(self, painter: QPainter, rect: QRectF) -> None:
        text = ""
        if self._snapshot.get("mirror_tool") == "track":
            selection = self._snapshot.get("selection", {})
            points = selection.get("points", [])
            if points:
                text = str(selection.get("hint", "Hold still to lock the selection"))
            elif self._snapshot.get("tracks"):
                text = "Pinch a marker to remove it · or use the tracking panel"
            else:
                text = "Trace a loop around any object to track it"
        else:
            drawing = self._snapshot.get("drawing", {})
            if drawing.get("strokes"):
                text = "Annotate the live feed · Smart shapes can correct circles"
            else:
                text = "Point to annotate the feed · your marks stay aligned to the video"
        if not text:
            return
        font = QFont(self.font())
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        width = min(rect.width() - 40, painter.fontMetrics().horizontalAdvance(text) + 44)
        bar = QRectF(rect.center().x() - width / 2, rect.bottom() - 42, width, 28)
        painter.setPen(QPen(qcolor("#3B342C"), 1))
        painter.setBrush(qcolor("#100E0C", 225))
        painter.drawRoundedRect(bar, 14, 14)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(MINT if self._snapshot.get("mirror_tool") == "track" else ACCENT))
        painter.drawEllipse(QRectF(bar.left() + 12, bar.center().y() - 2.5, 5, 5))
        painter.setPen(qcolor(TEXT_DIM))
        painter.drawText(bar.adjusted(25, 0, -12, 0), Qt.AlignmentFlag.AlignVCenter, text)

    def _paint_shot_corners(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(QPen(qcolor("#EFE7DB", 40), 1.0))
        length = 16
        m = 8
        for x, y, dx, dy in [
            (rect.left() + m, rect.top() + m, 1, 1),
            (rect.right() - m, rect.top() + m, -1, 1),
            (rect.left() + m, rect.bottom() - m, 1, -1),
            (rect.right() - m, rect.bottom() - m, -1, -1),
        ]:
            painter.drawLine(QPointF(x, y), QPointF(x + length * dx, y))
            painter.drawLine(QPointF(x, y), QPointF(x, y + length * dy))

    @staticmethod
    def _rounded_path(rect: QRectF, radius: float) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        return path

    # ------------------------------------------------------------------ export
    def render_artwork(self, width: int = 1920, height: int = 1080) -> QImage:
        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor("#100F0E"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._mode() == "mirror" and self._frame is not None:
            target = QRectF(*aspect_fit_rect(self._frame.width(), self._frame.height(), width, height))
            painter.fillRect(QRectF(0, 0, width, height), QColor("#080706"))
            painter.drawImage(target, self._frame)
            self._paint_strokes(painter, target, mirror=True)
            self._paint_tracks(painter, target)
        else:
            paper = QRectF(0, 0, width, height)
            gradient = QLinearGradient(paper.topLeft(), paper.bottomRight())
            gradient.setColorAt(0, qcolor("#F4EFE6"))
            gradient.setColorAt(1, qcolor(PAPER_2))
            painter.fillRect(paper, gradient)
            self._paint_strokes(painter, paper, mirror=False)
            font = QFont(self.font())
            font.setPixelSize(32)
            font.setWeight(QFont.Weight.Bold)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
            painter.setFont(font)
            painter.setPen(qcolor("#B8AD9C"))
            painter.drawText(paper.adjusted(48, 40, -48, -40), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, "AIRCANVAS")
        painter.end()
        return image

    # ------------------------------------------------------------------ mouse
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            point = self._point_from_widget(event.position().toPoint())
            if point is not None and self._manual_drawing_allowed():
                self._manual_down = True
                self.manual_begin.emit(point.x, point.y)
                self.setCursor(Qt.CursorShape.CrossCursor)
                event.accept()
                return
            if point is not None:
                self.surface_clicked.emit()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        if self._manual_down:
            point = self._point_from_widget(event.position().toPoint())
            if point is not None:
                self.manual_move.emit(point.x, point.y)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._manual_down and event.button() == Qt.MouseButton.LeftButton:
            self._manual_down = False
            self.manual_end.emit()
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def _manual_drawing_allowed(self) -> bool:
        mode = self._mode()
        if mode == "screen":
            return self._snapshot.get("tool") == "draw"
        return self._snapshot.get("mirror_tool") == "annotate"

    def closeEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        super().closeEvent(event)
