"""Object selection and robust single-object tracking for Mirror Mode.

Tracking strategy
-----------------
1. The user's fingertip loop produces a normalised region.
2. A CSRT tracker is initialised inside that region (good scale handling).
3. Every frame a colour-histogram consistency check guards against drift.
4. If CSRT fails or consistency collapses, the tracker searches a predicted
   neighbourhood with normalised template matching, which recovers after a
   short occlusion.  On recovery CSRT is re-initialised.
5. Repeated failure marks the object *lost*; leaving the frame for several
   consecutive frames marks it *out_of_view* and stops tracking permanently.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from .geometry import BBox, Point

TRACK_COLORS = ["#71d6b5", "#5aa9e6", "#f6c453", "#c79bff", "#ff8b8b"]


@dataclass
class TrackerParams:
    max_objects: int = 5
    min_box_px: int = 24
    iou_jump_limit: float = 0.45
    history_confidence: float = 0.28
    recover_after: int = 2
    recovery_timeout_s: float = 2.4
    out_of_view_frames: int = 10
    template_match_threshold: float = 0.52
    velocity_smoothing: float = 0.6


class SingleObjectTracker:
    def __init__(
        self,
        object_id: int,
        frame: np.ndarray,
        bbox: BBox,
        *,
        label: str,
        color: str,
        now: float,
        params: TrackerParams | None = None,
    ) -> None:
        self.id = object_id
        self.label = label
        self.color = color
        self.params = params or TrackerParams()
        self.bbox = bbox.clipped()
        self.status = "tracking"
        self.confidence = 1.0
        self.age_frames = 0
        self.missed_frames = 0
        self.lost_reason = ""
        self.lost_since: float | None = None
        self.last_seen = now
        self.velocity = Point(0.0, 0.0)
        self._template_gray: np.ndarray | None = None
        self._match_template: np.ndarray | None = None
        self._hist_ref: np.ndarray | None = None
        self._tracker: Any = None
        self._frame_shape = frame.shape[:2]
        self._out_frames = 0
        self._lock = threading.RLock()
        self._initialise(frame, self.bbox)
        self._refresh_appearance(frame)

    def _pixel_box(self, bbox: BBox, shape: tuple[int, int]) -> tuple[int, int, int, int]:
        height, width = shape
        x = max(0, int(round(bbox.x * width)))
        y = max(0, int(round(bbox.y * height)))
        w = max(2, int(round(bbox.w * width)))
        h = max(2, int(round(bbox.h * height)))
        w = min(w, width - x)
        h = min(h, height - y)
        return x, y, w, h

    @staticmethod
    def _crop(frame: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
        x, y, w, h = box
        return frame[y : y + h, x : x + w]

    def _initialise(self, frame: np.ndarray, bbox: BBox) -> None:
        self._frame_shape = frame.shape[:2]
        x, y, w, h = self._pixel_box(bbox, self._frame_shape)
        if w < self.params.min_box_px or h < self.params.min_box_px:
            raise ValueError("Selection is too small to track")
        try:
            self._tracker = cv2.TrackerCSRT_create()
            self._tracker.init(frame, (x, y, w, h))
        except Exception:
            self._tracker = None

    def _refresh_appearance(self, frame: np.ndarray) -> None:
        height, width = frame.shape[:2]
        x, y, w, h = self._pixel_box(self.bbox, (height, width))
        patch = self._crop(frame, (x, y, w, h))
        if patch.size == 0:
            return
        gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        # A square-ish reference for appearance scoring plus a full-resolution
        # template for translation-only recovery.
        self._template_gray = cv2.resize(gray, (max(16, min(96, w)), max(16, min(96, h))))
        self._match_template = gray.copy()
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [24, 24], [0, 180, 0, 256])
        cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        self._hist_ref = hist

    def _gray_similarity(self, frame: np.ndarray, bbox: BBox) -> float:
        """Zero-normalised correlation between the reference patch and box.

        This is the main guard against CSRT confidently tracking a uniform
        occluder (a hand, a passing person, a lens cap).
        """
        if self._template_gray is None:
            return 0.5
        height, width = frame.shape[:2]
        x, y, w, h = self._pixel_box(bbox, (height, width))
        patch = self._crop(frame, (x, y, w, h))
        if patch.size == 0:
            return 0.0
        gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        if gray.shape != self._template_gray.shape:
            gray = cv2.resize(gray, (self._template_gray.shape[1], self._template_gray.shape[0]))
        a = gray.astype(np.float32) - float(gray.mean())
        b = self._template_gray.astype(np.float32) - float(self._template_gray.mean())
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom < 1e-5:
            return 0.0
        corr = float(np.sum(a * b) / denom)
        return max(0.0, min(1.0, (corr + 1.0) / 2.0))

    def _appearance_similarity(self, frame: np.ndarray, bbox: BBox) -> float:
        hist_score = self._hist_similarity(frame, bbox)
        gray_score = self._gray_similarity(frame, bbox)
        # Correlation is signed but converted to 0..1; a true match is > 0.65.
        return max(0.0, min(1.0, 0.38 * hist_score + 0.62 * gray_score))

    def _hist_similarity(self, frame: np.ndarray, bbox: BBox) -> float:
        if self._hist_ref is None:
            return 0.5
        height, width = frame.shape[:2]
        x, y, w, h = self._pixel_box(bbox, (height, width))
        patch = self._crop(frame, (x, y, w, h))
        if patch.size == 0:
            return 0.0
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [24, 24], [0, 180, 0, 256])
        cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        score = float(cv2.compareHist(self._hist_ref, hist, cv2.HISTCMP_CORREL))
        return max(0.0, min(1.0, (score + 1.0) / 2.0))

    def _iou(self, a: BBox, b: BBox) -> float:
        inter = a.intersection_area(b)
        union = a.area + b.area - inter
        return inter / union if union > 1e-9 else 0.0

    def _recover(self, frame: np.ndarray) -> BBox | None:
        if self._match_template is None:
            return None
        height, width = frame.shape[:2]
        cx = (self.bbox.center.x + self.velocity.x * 6) * width
        cy = (self.bbox.center.y + self.velocity.y * 6) * height
        half_w = max(30, self.bbox.w * width * 1.9)
        half_h = max(30, self.bbox.h * height * 1.9)
        x0 = max(0, int(cx - half_w))
        y0 = max(0, int(cy - half_h))
        x1 = min(width, int(cx + half_w))
        y1 = min(height, int(cy + half_h))
        if x1 - x0 < 12 or y1 - y0 < 12:
            return None
        search = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
        template = self._match_template
        if search.shape[0] < template.shape[0] or search.shape[1] < template.shape[1]:
            return None
        try:
            result = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
        except cv2.error:
            return None
        if max_val < self.params.template_match_threshold:
            return None
        px = x0 + max_loc[0]
        py = y0 + max_loc[1]
        candidate = BBox(px / width, py / height, self.bbox.w, self.bbox.h).clipped()
        # Uniform occluders can make CCOEFF_NORMED numerically unstable; verify
        # that the patch still looks like the reference object.
        if self._appearance_similarity(frame, candidate) < 0.35:
            return None
        return candidate

    def _check_out_of_view(self, predicted: BBox) -> bool:
        center_out = not (0.0 <= predicted.center.x <= 1.0 and 0.0 <= predicted.center.y <= 1.0)
        visible = predicted.clipped().area / max(predicted.area, 1e-6)
        far_out = visible < 0.15
        # Require either a centre outside with outward velocity, or almost the
        # entire box outside the frame.
        moving_out = (
            center_out
            and (
                (predicted.center.x < 0.0 and self.velocity.x < 0.0)
                or (predicted.center.x > 1.0 and self.velocity.x > 0.0)
                or (predicted.center.y < 0.0 and self.velocity.y < 0.0)
                or (predicted.center.y > 1.0 and self.velocity.y > 0.0)
            )
        )
        return far_out or moving_out

    def update(self, frame: np.ndarray, now: float) -> None:
        with self._lock:
            self.age_frames += 1
            if self.status in ("out_of_view", "lost"):
                return
            height, width = frame.shape[:2]
            predicted = BBox(
                self.bbox.x + self.velocity.x,
                self.bbox.y + self.velocity.y,
                self.bbox.w,
                self.bbox.h,
            )
            if self._check_out_of_view(predicted):
                self.missed_frames += 1
                if self.status not in ("out_of_view",):
                    self.status = "reacquiring"
                if self.missed_frames >= self.params.out_of_view_frames:
                    self.status = "out_of_view"
                    self.lost_reason = "left camera view"
                    self._tracker = None
                    return

            ok, raw_box = (False, None)
            if self._tracker is not None:
                try:
                    ok, raw_box = self._tracker.update(frame)
                except cv2.error:
                    ok = False
            candidate: BBox | None = None
            confidence = 0.0
            if ok and raw_box is not None:
                x, y, w, h = (float(v) for v in raw_box)
                candidate = BBox(x / width, y / height, w / width, h / height).clipped()
                if candidate.area < 1e-5:
                    candidate = None
                else:
                    appearance = self._appearance_similarity(frame, candidate)
                    jump_iou = self._iou(candidate, predicted)
                    if jump_iou < 0.05 and self._iou(candidate, self.bbox) < 0.05:
                        # An implausible teleport is treated as a failed frame.
                        candidate = None
                    elif appearance < 0.43:
                        # CSRT can happily follow a uniform occluder.  The
                        # appearance check catches that case so recovery runs.
                        candidate = None
                    else:
                        confidence = 0.70 * appearance + 0.30 * max(0.0, min(1.0, jump_iou + 0.15))
            if candidate is None or confidence < self.params.history_confidence:
                recovered = self._recover(frame)
                if recovered is not None:
                    candidate = recovered
                    appearance = self._appearance_similarity(frame, candidate)
                    confidence = max(0.5, appearance)
                    self._initialise(frame, candidate)
                    self.status = "tracking"
                else:
                    self.missed_frames += 1
                    self.confidence = max(0.0, self.confidence * 0.82)
                    if self.missed_frames >= self.params.recover_after:
                        self.status = "occluded"
                        self.lost_since = self.lost_since or now
                    # A continuously occluded object near the frame edge is
                    # much more likely to have left the camera than to be
                    # temporarily covered.  Confirm over several frames.
                    near_edge = (
                        self.bbox.center.x < 0.10
                        or self.bbox.center.x > 0.90
                        or self.bbox.center.y < 0.08
                        or self.bbox.center.y > 0.92
                    )
                    if near_edge:
                        self._out_frames += 1
                    else:
                        self._out_frames = 0
                    if self._out_frames >= max(6, self.params.out_of_view_frames - 2):
                        self.status = "out_of_view"
                        self.lost_reason = "left camera view"
                        self._tracker = None
                        return
                    if self.lost_since is not None and now - self.lost_since > self.params.recovery_timeout_s:
                        self.status = "lost"
                        self.lost_reason = "lost after occlusion"
                        self._tracker = None
                    if self.status == "occluded":
                        self.bbox = predicted.clipped()
                    return

            previous = self.bbox
            dx = candidate.center.x - previous.center.x
            dy = candidate.center.y - previous.center.y
            alpha = self.params.velocity_smoothing
            self.velocity = Point(
                alpha * dx + (1 - alpha) * self.velocity.x,
                alpha * dy + (1 - alpha) * self.velocity.y,
            )
            self.bbox = candidate
            self.confidence = max(0.0, min(1.0, confidence))
            self.missed_frames = 0
            self._out_frames = 0
            self.lost_since = None
            self.status = "tracking"
            self.last_seen = now
            # Update the reference appearance gradually to tolerate lighting
            # changes, but never while the tracker is uncertain.
            if self.age_frames % 18 == 0:
                self._refresh_appearance(frame)

    def marker_state(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "bbox": self.bbox.as_list(),
            "status": self.status,
            "label": self.label,
            "confidence": round(float(self.confidence), 2),
            "color": self.color,
            "age_frames": self.age_frames,
            "missed_frames": self.missed_frames,
            "lost_reason": self.lost_reason,
        }


class ObjectTrackerManager:
    def __init__(self, params: TrackerParams | None = None) -> None:
        self.params = params or TrackerParams()
        self._trackers: list[SingleObjectTracker] = []
        self._next_id = 1
        self._lock = threading.RLock()
        self.last_error = ""

    @property
    def count(self) -> int:
        return len(self._trackers)

    def add_from_region(
        self,
        frame: np.ndarray,
        bbox: BBox,
        *,
        label: str | None = None,
        color: str | None = None,
        now: float | None = None,
    ) -> SingleObjectTracker:
        with self._lock:
            if len(self._trackers) >= self.params.max_objects:
                raise ValueError(f"At most {self.params.max_objects} objects can be tracked")
            object_id = self._next_id
            tracker = SingleObjectTracker(
                object_id,
                frame,
                bbox,
                label=label or f"Object {object_id}",
                color=color or TRACK_COLORS[(object_id - 1) % len(TRACK_COLORS)],
                now=time.time() if now is None else now,
                params=self.params,
            )
            self._next_id += 1
            self._trackers.append(tracker)
            self.last_error = ""
            return tracker

    def update(self, frame: np.ndarray, now: float) -> list[dict[str, Any]]:
        with self._lock:
            if frame is None or frame.size == 0:
                return [t.marker_state() for t in self._trackers]
            for tracker in list(self._trackers):
                try:
                    tracker.update(frame, now)
                except Exception:
                    tracker.status = "lost"
                    tracker.lost_reason = "tracker error"
                    tracker._tracker = None
            return [t.marker_state() for t in self._trackers]

    def markers(self) -> list[dict[str, Any]]:
        with self._lock:
            return [t.marker_state() for t in self._trackers]

    def active_markers(self) -> list[dict[str, Any]]:
        return [m for m in self.markers() if m["status"] in ("tracking", "occluded", "reacquiring")]

    def get(self, object_id: int) -> SingleObjectTracker | None:
        with self._lock:
            return next((t for t in self._trackers if t.id == object_id), None)

    def remove(self, object_id: int | None = None) -> bool:
        with self._lock:
            if object_id is None:
                if not self._trackers:
                    return False
                self._trackers.clear()
                return True
            before = len(self._trackers)
            self._trackers = [t for t in self._trackers if t.id != object_id]
            return len(self._trackers) != before

    def remove_at(self, point: Point) -> int | None:
        with self._lock:
            # Newest first, so overlapping markers are removable.
            for tracker in reversed(self._trackers):
                if tracker.bbox.contains(point) or tracker.bbox.padded(0.08).contains(point):
                    self._trackers.remove(tracker)
                    return tracker.id
        return None

    def clear(self) -> None:
        with self._lock:
            self._trackers.clear()

    def summary(self) -> list[dict[str, Any]]:
        return self.markers()
