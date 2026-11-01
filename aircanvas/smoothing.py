"""Temporal smoothing used by the pointer and stroke pipelines."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from .geometry import Point


class OneEuroFilter:
    """Adaptive low-pass filter (Casiez, Roussel & Vogel, 2012).

    Slow movement is heavily smoothed while fast movement remains responsive -
    the right trade-off for an air pointer.  Times are in seconds.
    """

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.012,
        derivative_cutoff: float = 1.0,
    ) -> None:
        self.min_cutoff = max(0.001, min_cutoff)
        self.beta = max(0.0, beta)
        self.derivative_cutoff = max(0.001, derivative_cutoff)
        self._x: float | None = None
        self._dx = 0.0
        self._last_time: float | None = None
        self._initialised = False

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / max(dt, 1e-6))

    def filter(self, value: float, timestamp: float | None = None) -> float:
        now = time.perf_counter() if timestamp is None else timestamp
        if self._x is None or self._last_time is None:
            self._x = value
            self._last_time = now
            self._initialised = True
            return value
        dt = max(1e-4, now - self._last_time)
        self._last_time = now
        raw_dx = (value - self._x) / dt
        alpha_d = self._alpha(self.derivative_cutoff, dt)
        self._dx = alpha_d * raw_dx + (1.0 - alpha_d) * self._dx
        cutoff = self.min_cutoff + self.beta * abs(self._dx)
        alpha = self._alpha(cutoff, dt)
        self._x = alpha * value + (1.0 - alpha) * self._x
        return self._x

    def reset(self) -> None:
        self._x = None
        self._dx = 0.0
        self._last_time = None
        self._initialised = False


class PointerSmoother:
    """Two-dimensional One Euro filter with a small dead-band."""

    def __init__(self, smoothing: float = 0.6, deadband: float = 0.0015) -> None:
        self.smoothing = max(0.0, min(0.95, smoothing))
        # More smoothing -> a lower cutoff frequency.
        cutoff = 0.9 + (1.0 - self.smoothing) * 5.0
        self.x_filter = OneEuroFilter(min_cutoff=cutoff, beta=0.008 * (1.0 - self.smoothing) + 0.004)
        self.y_filter = OneEuroFilter(min_cutoff=cutoff, beta=0.008 * (1.0 - self.smoothing) + 0.004)
        self.deadband = max(0.0, deadband)
        self._last: Point | None = None

    def filter(self, point: Point, timestamp: float | None = None) -> Point:
        smoothed = Point(
            self.x_filter.filter(point.x, timestamp),
            self.y_filter.filter(point.y, timestamp),
        )
        if self._last is not None and smoothed.distance(self._last) < self.deadband:
            return self._last
        self._last = smoothed
        return smoothed

    def reset(self) -> None:
        self.x_filter.reset()
        self.y_filter.reset()
        self._last = None


@dataclass
class StableValue:
    value: object
    held_s: float
    changed: bool


class HoldStabilizer:
    """Require a value to remain unchanged for several frames before acting."""

    def __init__(self, window: int = 5) -> None:
        self.window = max(1, window)
        self._history: list[object] = []
        self._stable: object | None = None
        self._stable_since = 0.0
        self._last_change = 0.0

    def update(self, value: object, now: float) -> StableValue:
        if not self._history or self._history[-1] != value:
            self._last_change = now
        self._history.append(value)
        if len(self._history) > self.window:
            self._history.pop(0)
        counts: dict[object, int] = {}
        for item in self._history:
            counts[item] = counts.get(item, 0) + 1
        candidate, count = max(counts.items(), key=lambda pair: pair[1])
        changed = False
        if count >= max(2, (self.window + 1) // 2) and candidate != self._stable:
            self._stable = candidate
            self._stable_since = now
            changed = True
        if self._stable is None:
            self._stable = candidate
            self._stable_since = now
        return StableValue(self._stable, max(0.0, now - self._stable_since), changed)

    @property
    def stable(self) -> object | None:
        return self._stable

    @property
    def since(self) -> float:
        return self._stable_since

    def reset(self) -> None:
        self._history.clear()
        self._stable = None
        self._stable_since = 0.0
        self._last_change = 0.0
