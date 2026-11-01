from __future__ import annotations

import math

import pytest

from aircanvas.drawing import DrawingEngine
from aircanvas.geometry import Point
from aircanvas.shapes import LoopSelectionDetector, recognize_shape


def circle_points(count: int = 100, turns: float = 1.0, rx: float = 0.16, ry: float = 0.13) -> list[Point]:
    return [
        Point(0.5 + rx * math.cos(2 * math.pi * turns * i / count), 0.5 + ry * math.sin(2 * math.pi * turns * i / count))
        for i in range(count + 1)
    ]


def test_perfect_circle_is_recognised_and_corrected():
    result = recognize_shape(circle_points())
    assert result.recognized
    assert result.kind == "circle"
    assert result.confidence >= 0.55
    assert result.circle is not None
    assert result.circle.center.x == pytest.approx(0.5, abs=0.02)
    assert len(result.corrected_points) == 96


def test_open_arc_is_not_corrected():
    points = [Point(0.5 + 0.16 * math.cos(a), 0.5 + 0.13 * math.sin(a)) for a in [i * 0.25 for i in range(10)]]
    result = recognize_shape(points)
    assert not result.recognized
    assert result.kind == "freehand"


def test_natural_overshoot_still_closes():
    result = recognize_shape(circle_points(turns=1.08))
    assert result.recognized


def test_tiny_scribble_is_ignored():
    points = [Point(0.5 + i * 0.0005, 0.5) for i in range(20)]
    assert not recognize_shape(points).recognized


def test_drawing_engine_corrects_and_undo_redo():
    engine = DrawingEngine(auto_shapes=True)
    engine.begin(Point(0.34, 0.5))
    for point in circle_points(count=80)[1:]:
        engine.add(point)
    commit = engine.end()
    assert commit is not None and commit.corrected
    assert engine.strokes[0].kind == "circle"
    assert engine.can_undo
    assert engine.undo()
    assert not engine.strokes
    assert engine.redo()
    assert len(engine.strokes) == 1


def test_drawing_engine_keeps_freehand_when_disabled():
    engine = DrawingEngine(auto_shapes=False)
    engine.begin(Point(0.34, 0.5))
    for point in circle_points(count=60)[1:]:
        engine.add(point)
    commit = engine.end()
    assert commit is not None and not commit.corrected
    assert engine.strokes[0].kind == "freehand"


def test_clear_is_reversible():
    engine = DrawingEngine()
    engine.begin(Point(0.1, 0.1))
    engine.add(Point(0.3, 0.2))
    engine.end()
    assert engine.clear()
    assert not engine.strokes
    assert engine.undo()
    assert len(engine.strokes) == 1


def test_loop_selection_completes_after_hold():
    detector = LoopSelectionDetector(hold_seconds=0.25)
    points = circle_points(count=70, rx=0.12, ry=0.12)
    for i, point in enumerate(points):
        detector.add(point, i / 30)
    completed = None
    for i in range(30):
        completed = detector.maybe_complete(2.4 + i / 30)
        if completed:
            break
    assert completed is not None
    assert completed.status == "acquired"
    assert completed.bbox is not None
    assert completed.bbox.area > 0.01


def test_loop_selection_rejects_open_curve():
    detector = LoopSelectionDetector(hold_seconds=0.1)
    for i in range(24):
        detector.add(Point(0.2 + i * 0.01, 0.3 + i * 0.002), i / 30)
    assert detector.maybe_complete(1.0) is None
    finished = detector.finish(1.2)
    assert finished is None or finished.status == "rejected"
