"""A deterministic simulated camera feed for demos, screenshots and tests.

The simulated feed is intentionally labelled in the image.  It still drives the
real shared session: synthetic landmarks go through the same gesture mapper,
drawing engine, loop detector and CSRT tracker as a physical webcam.
"""

from __future__ import annotations

import math
import random
import threading
import time
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from .geometry import Point
from .models import HandObservation
from .synthetic import hand_with_index_tip, synthetic_hand


@dataclass
class DemoArc:
    start: float
    end: float
    kind: str
    center: Point
    radius_x: float
    radius_y: float
    pose: str = "point"


class DemoEngine:
    WIDTH = 960
    HEIGHT = 540

    def __init__(self, session: Any) -> None:
        self.session = session
        self.width = self.WIDTH
        self.height = self.HEIGHT
        self._mode = session.mode
        self._started_at = time.monotonic()
        self._background = self._build_background()
        self._grain = self._build_grain()
        self.mug_center = Point(0.59, 0.54)

    # ------------------------------------------------------------------ scene
    def _build_background(self) -> np.ndarray:
        w, h = self.width, self.height
        yy = np.mgrid[0:h, 0:w][0].astype(np.float32)
        # Wall gradient.
        wall_t = np.clip(yy / (h * 0.48), 0, 1)
        wall = np.stack(
            [
                34 + (57 - 34) * wall_t,
                31 + (51 - 31) * wall_t,
                30 + (47 - 30) * wall_t,
            ],
            axis=-1,
        )
        image = wall.astype(np.uint8)
        # Warm bokeh on the wall.
        bokeh = np.zeros_like(image)
        for cx, cy, r, strength in [
            (110, 85, 38, 26),
            (205, 55, 22, 20),
            (1010, 110, 45, 18),
            (860, 42, 16, 25),
            (1150, 70, 28, 12),
        ]:
            cv2.circle(bokeh, (cx, cy), r, (strength + 26, strength + 30, strength + 18), -1, cv2.LINE_AA)
        bokeh = cv2.GaussianBlur(bokeh, (0, 0), 18)
        image = cv2.addWeighted(image, 1.0, bokeh, 0.55, 0)

        # Oak desk top with a soft perspective.
        desk_top = int(h * 0.32)
        for y in range(desk_top, h):
            t = (y - desk_top) / max(1, h - desk_top)
            color = (
                int(134 - 25 * t),
                int(104 - 22 * t),
                int(79 - 16 * t),
            )
            cv2.line(image, (0, y), (w, y), color, 1)
        # Wood grain.
        rng = random.Random(4)
        for _ in range(34):
            y0 = rng.randint(desk_top + 8, h - 10)
            pts = []
            for x in range(-20, w + 20, 24):
                pts.append((x, int(y0 + 4 * math.sin(x / 90 + rng.random() * 3))))
            cv2.polylines(image, [np.array(pts)], False, (127, 96, 71), 1, cv2.LINE_AA)
        # Desk edge highlight.
        cv2.line(image, (0, desk_top), (w, desk_top - 18), (92, 74, 62), 18, cv2.LINE_AA)
        cv2.line(image, (0, desk_top + 6), (w, desk_top - 8), (198, 157, 113), 2, cv2.LINE_AA)

        # Linen mat in the centre.
        mat = np.array(
            [
                [int(w * 0.22), int(h * 0.43)],
                [int(w * 0.79), int(h * 0.37)],
                [int(w * 0.88), int(h * 0.88)],
                [int(w * 0.14), int(h * 0.94)],
            ],
            dtype=np.int32,
        )
        overlay = image.copy()
        cv2.fillPoly(overlay, [mat], (168, 160, 145))
        cv2.addWeighted(overlay, 0.50, image, 0.50, 0, image)
        cv2.polylines(image, [mat], True, (181, 172, 154), 2, cv2.LINE_AA)
        for i in range(1, 12):
            y = int(h * 0.46 + i * h * 0.035)
            cv2.line(image, (int(w * 0.17), y), (int(w * 0.86), y - 16), (176, 168, 151), 1, cv2.LINE_AA)

        # Notebook on the left.
        nb = np.array([[95, 345], [335, 325], [368, 500], [78, 518]], dtype=np.int32)
        cv2.fillPoly(image, [nb], (45, 50, 54))
        cv2.polylines(image, [nb], True, (25, 27, 29), 3, cv2.LINE_AA)
        cv2.line(image, (232, 328), (260, 502), (83, 90, 94), 2, cv2.LINE_AA)
        cv2.putText(image, "IDEAS", (124, 402), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (205, 198, 183), 2, cv2.LINE_AA)
        cv2.putText(image, "draw  ·  move  ·  track", (114, 438), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (148, 153, 151), 1, cv2.LINE_AA)
        # Pencil.
        cv2.line(image, (390, 500), (500, 435), (40, 40, 42), 9, cv2.LINE_AA)
        cv2.line(image, (390, 500), (500, 435), (220, 154, 74), 5, cv2.LINE_AA)
        cv2.circle(image, (388, 501), 5, (224, 202, 178), -1, cv2.LINE_AA)

        # Small plant on the right edge.
        pot_center = (1175, 480)
        cv2.ellipse(image, pot_center, (70, 48), 0, 0, 360, (122, 83, 65), -1, cv2.LINE_AA)
        cv2.ellipse(image, (1175, 460), (68, 22), 0, 0, 360, (80, 55, 45), -1, cv2.LINE_AA)
        rng = random.Random(11)
        for i in range(9):
            angle = -math.pi * 0.9 + i * 0.22
            length = 90 + rng.randint(-20, 50)
            bx, by = 1175 + 8 * math.cos(angle), 460 + 6 * math.sin(angle)
            ex = bx + math.cos(angle - 0.4) * length
            ey = by + math.sin(angle - 0.4) * length
            cv2.ellipse(
                image,
                (int((bx + ex) / 2), int((by + ey) / 2)),
                (45, 15),
                math.degrees(angle) + 8,
                0,
                360,
                (48 + i * 3, 93 + i * 4, 67 + i * 2),
                -1,
                cv2.LINE_AA,
            )
        # Phone at lower right.
        phone = np.array([[718, 438], [862, 428], [878, 556], [730, 568]], dtype=np.int32)
        cv2.fillPoly(image, [phone], (29, 31, 36))
        cv2.polylines(image, [phone], True, (72, 75, 82), 2, cv2.LINE_AA)
        cv2.rectangle(image, (744, 451), (855, 540), (43, 47, 57), -1)
        cv2.circle(image, (810, 550), 4, (100, 104, 110), -1, cv2.LINE_AA)

        # Vignette.
        mask = np.zeros((h, w), dtype=np.float32)
        cv2.ellipse(mask, (w // 2, h // 2), (int(w * 0.62), int(h * 0.66)), 0, 0, 360, 1.0, -1)
        mask = cv2.GaussianBlur(mask, (0, 0), 90)
        mask = np.clip(mask * 0.55 + 0.45, 0, 1)[..., None]
        image = (image.astype(np.float32) * mask).astype(np.uint8)
        return image

    def _build_grain(self) -> np.ndarray:
        rng = np.random.default_rng(12)
        grain = rng.normal(0, 3.0, (self.height, self.width, 1)).astype(np.float32)
        return grain

    def _mug_center(self, t: float, mode: str) -> Point:
        base = Point(0.585, 0.535)
        if mode == "mirror" and t > 2.9:
            phase = (t - 2.9) * 0.85
            return Point(base.x + 0.028 * math.sin(phase), base.y + 0.012 * math.cos(phase * 1.4))
        return base

    def _draw_mug(self, frame: np.ndarray, center: Point, t: float) -> None:
        h, w = frame.shape[:2]
        cx, cy = int(center.x * w), int(center.y * h)
        rx = 58
        top_y = cy - 38
        bottom_y = cy + 64
        # Contact shadow.
        shadow = frame.copy()
        cv2.ellipse(shadow, (cx + 10, bottom_y + 10), (82, 20), 0, 0, 360, (30, 24, 20), -1, cv2.LINE_AA)
        shadow = cv2.GaussianBlur(shadow, (0, 0), 15)
        cv2.addWeighted(shadow, 0.52, frame, 0.48, 0, frame)
        # Handle sits behind the body.
        cv2.ellipse(frame, (cx + 58, cy + 8), (34, 38), 0, -90, 90, (52, 89, 124), 13, cv2.LINE_AA)
        cv2.ellipse(frame, (cx + 58, cy + 8), (34, 38), 0, -90, 90, (124, 170, 201), 4, cv2.LINE_AA)
        # Body: rounded top and bottom with gently tapered sides.
        body = np.array(
            [
                [cx - rx, top_y],
                [cx + rx, top_y],
                [cx + rx - 5, bottom_y - 12],
                [cx + rx - 20, bottom_y],
                [cx - rx + 20, bottom_y],
                [cx - rx + 5, bottom_y - 12],
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(frame, [body], (96, 149, 190), cv2.LINE_AA)
        cv2.ellipse(frame, (cx, bottom_y - 5), (rx - 21, 12), 0, 0, 180, (80, 128, 166), -1, cv2.LINE_AA)
        cv2.ellipse(frame, (cx, top_y), (rx, 17), 0, 0, 360, (196, 221, 233), -1, cv2.LINE_AA)
        cv2.ellipse(frame, (cx, top_y), (rx - 6, 11), 0, 0, 360, (75, 51, 37), -1, cv2.LINE_AA)
        cv2.ellipse(frame, (cx, top_y), (rx - 12, 7), 0, 0, 360, (104, 72, 50), -1, cv2.LINE_AA)
        # Vertical highlight and label.
        cv2.ellipse(frame, (cx - 33, cy + 2), (9, 34), 8, 0, 360, (143, 187, 214), -1, cv2.LINE_AA)
        cv2.putText(frame, "AIR", (cx - 21, cy + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (224, 236, 239), 1, cv2.LINE_AA)
        cv2.line(frame, (cx - 26, cy + 28), (cx + 25, cy + 28), (173, 202, 219), 1, cv2.LINE_AA)
        # Steam.
        for i in range(3):
            pts = []
            for j in range(16):
                yy = top_y - 14 - j * 4
                xx = cx - 20 + i * 20 + 5 * math.sin(j * 0.55 + t * 1.6 + i)
                pts.append([int(xx), int(yy)])
            cv2.polylines(frame, [np.array(pts)], False, (223, 221, 214), 1, cv2.LINE_AA)

    def _draw_hand_silhouette(self, frame: np.ndarray, hand: HandObservation) -> None:
        h, w = frame.shape[:2]
        pts = [(int(p.x * w), int(p.y * h)) for p in hand.landmarks]
        layer = frame.copy()
        skin = (116, 158, 196)  # BGR
        # Soft shadow under the hand.
        for start, end in [
            (0, 5), (5, 6), (6, 7), (7, 8), (9, 10), (10, 11), (11, 12),
            (13, 14), (14, 15), (15, 16), (17, 18), (18, 19), (19, 20),
            (0, 1), (1, 2), (2, 3), (3, 4),
        ]:
            cv2.line(layer, (pts[start][0] + 5, pts[start][1] + 8), (pts[end][0] + 5, pts[end][1] + 8), (40, 30, 24), 26, cv2.LINE_AA)
        palm = np.array([pts[i] for i in (0, 1, 5, 9, 13, 17)], dtype=np.int32)
        cv2.fillPoly(layer, [palm], skin, cv2.LINE_AA)
        for start, end, thickness in [
            (0, 5, 36), (5, 6, 24), (6, 7, 20), (7, 8, 17),
            (9, 10, 25), (10, 11, 21), (11, 12, 18),
            (13, 14, 23), (14, 15, 19), (15, 16, 16),
            (17, 18, 19), (18, 19, 16), (19, 20, 14),
            (0, 1, 32), (1, 2, 25), (2, 3, 20), (3, 4, 16),
        ]:
            cv2.line(layer, pts[start], pts[end], skin, thickness, cv2.LINE_AA)
        layer = cv2.GaussianBlur(layer, (0, 0), 2)
        cv2.addWeighted(layer, 0.62, frame, 0.38, 0, frame)

    def _compose(self, frame: np.ndarray, hand: HandObservation | None, t: float, mode: str) -> np.ndarray:
        out = frame.copy()
        # Camera-like grain and a soft, stable vignette.
        noise = self._grain
        out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        if hand is not None:
            self._draw_hand_silhouette(out, hand)
        # Small camera HUD, intentionally visible in demos and screenshots.
        cv2.circle(out, (24, 25), 5, (72, 82, 232), -1, cv2.LINE_AA)
        cv2.putText(out, "SIMULATED CAMERA", (37, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (222, 226, 228), 1, cv2.LINE_AA)
        cv2.putText(out, f"{t:05.1f}s", (out.shape[1] - 74, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (196, 198, 199), 1, cv2.LINE_AA)
        return out

    # ------------------------------------------------------------------ script
    def _screen_observation(self, t: float) -> HandObservation | None:
        if t < 0.15:
            return synthetic_hand("open_palm", center=Point(0.54, 0.58), scale=0.16).observation()
        if t < 2.20:
            u = (t - 0.15) / 2.05
            angle = -math.pi / 2 + u * math.pi * 2.08
            tip = Point(0.45 + math.cos(angle) * 0.185, 0.45 + math.sin(angle) * 0.155)
            return hand_with_index_tip(tip, pose="point", scale=0.16).observation()
        if t < 2.55:
            return synthetic_hand("fist", center=Point(0.56, 0.62), scale=0.15).observation()
        if t < 2.86:
            return synthetic_hand("open_palm", center=Point(0.69, 0.62), scale=0.15).observation()
        if t < 3.92:
            u = (t - 2.86) / 1.06
            tip = Point(0.43 + u * 0.35, 0.68 + math.sin(u * math.pi * 2.4) * 0.017)
            return hand_with_index_tip(tip, pose="point", scale=0.14).observation()
        if t < 4.24:
            return synthetic_hand("fist", center=Point(0.74, 0.62), scale=0.14).observation()
        sway = math.sin(t * 1.4) * 0.008
        return synthetic_hand("open_palm", center=Point(0.72 + sway, 0.58), scale=0.15).observation()

    def _mirror_observation(self, t: float) -> HandObservation | None:
        if t < 0.15:
            return synthetic_hand("open_palm", center=Point(0.70, 0.64), scale=0.16).observation()
        center = self._mug_center(min(t, 2.9), "mirror")
        if t < 2.62:
            u = (t - 0.15) / 2.47
            angle = -math.pi / 2 + u * math.pi * 2.08
            tip = Point(center.x + math.cos(angle) * 0.145, center.y + math.sin(angle) * 0.155)
            return hand_with_index_tip(tip, pose="point", scale=0.16).observation()
        if t < 3.15:
            return synthetic_hand("open_palm", center=Point(0.78, 0.68), scale=0.16).observation()
        # Hand rests to the right, clear of the tracked object.
        sway = math.sin(t * 1.2) * 0.006
        return synthetic_hand("open_palm", center=Point(0.82 + sway, 0.67), scale=0.16).observation()

    def observation(self, t: float | None = None) -> HandObservation | None:
        t = self._elapsed(t)
        return self._mirror_observation(t) if self._mode == "mirror" else self._screen_observation(t)

    def frame(self, t: float | None = None) -> np.ndarray:
        t = self._elapsed(t)
        self._mode = self.session.mode
        image = self._background.copy()
        center = self._mug_center(t, self._mode)
        if self._mode == "mirror":
            self._draw_mug(image, center, t)
        hand = self.observation(t)
        frame = self._compose(image, hand, t, self._mode)
        self.mug_center = center
        return frame

    def _elapsed(self, t: float | None = None) -> float:
        if self._mode != self.session.mode:
            self._mode = self.session.mode
            self._started_at = time.monotonic()
        if t is None:
            return time.monotonic() - self._started_at
        return t

    def reset(self) -> None:
        self._started_at = time.monotonic()
        self._mode = self.session.mode


class DemoPipeline:
    """Threaded demo pipeline with the same poll() contract as CameraPipeline."""

    def __init__(self, session: Any, engine: DemoEngine | None = None) -> None:
        self.session = session
        self.engine = engine or DemoEngine(session)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._rgb: np.ndarray | None = None
        self._snapshot: dict[str, Any] | None = None
        self._events: list[Any] = []
        self._sequence = 0
        self._last_demo_mode = session.mode

    def start(self) -> bool:
        self._stop.clear()
        self.session.clear_tracks()
        self.engine.reset()
        self.session.set_camera_status("demo", "Simulated camera feed", source="demo", demo=True, width=960, height=540)
        self._thread = threading.Thread(target=self._run, name="aircanvas-demo", daemon=True)
        self._thread.start()
        return True

    def _run(self) -> None:
        interval = 1.0 / 24.0
        next_tick = time.monotonic()
        while not self._stop.is_set():
            if self.session.mode != self._last_demo_mode:
                self._last_demo_mode = self.session.mode
                self.engine.reset()
            t = time.monotonic()
            frame = self.engine.frame()
            observation = self.engine.observation()
            try:
                events = self.session.process_frame(frame, t, observation=observation)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            except Exception:
                time.sleep(0.05)
                continue
            snapshot = self.session.snapshot()
            with self._lock:
                self._rgb = rgb
                self._snapshot = snapshot
                self._events.extend(events)
                self._sequence += 1
            next_tick += interval
            delay = next_tick - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                next_tick = time.monotonic()

    def poll(self) -> tuple[np.ndarray | None, dict[str, Any] | None, list[Any], int]:
        with self._lock:
            events = list(self._events)
            self._events.clear()
            rgb = None if self._rgb is None else self._rgb.copy()
            return rgb, self._snapshot, events, self._sequence

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self.session.set_camera_status("stopped", "Simulation stopped", source="demo", demo=True)

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())
