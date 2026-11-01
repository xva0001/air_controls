from __future__ import annotations

import pytest

from aircanvas.config import GestureSettings
from aircanvas.gestures import GestureStabilizer, classify_hand
from aircanvas.models import GestureReading
from aircanvas.synthetic import synthetic_hand


@pytest.mark.parametrize(
    "pose,expected",
    [
        ("point", "point"),
        ("pinch", "pinch"),
        ("peace", "peace"),
        ("three", "three"),
        ("open_palm", "open_palm"),
        ("fist", "fist"),
    ],
)
def test_synthetic_pose_classification(pose, expected):
    hand = synthetic_hand(pose).observation()
    result = classify_hand(hand, GestureSettings())
    assert result.raw == expected


def test_fist_never_becomes_pinch_at_high_sensitivity():
    settings = GestureSettings(pinch_sensitivity=1.8)
    result = classify_hand(synthetic_hand("fist").observation(), settings)
    assert result.raw == "fist"


def test_pinch_precedence_over_point():
    result = classify_hand(synthetic_hand("pinch").observation())
    assert result.raw == "pinch"
    assert result.pinch_ratio < 0.2


def test_stabilizer_votes_out_single_frame_noise():
    stabilizer = GestureStabilizer(window=5)
    results = []
    for i in range(10):
        raw = "pinch" if i == 5 else "point"
        reading = GestureReading(raw=raw, confidence=0.9)
        results.append(stabilizer.update(reading, i / 30))
    assert results[-1].stable == "point"
    assert all(item.stable != "pinch" or i >= 7 for i, item in enumerate(results))


def test_stabilizer_tracks_hold_duration():
    stabilizer = GestureStabilizer(window=3)
    reading = GestureReading(raw="open_palm", confidence=0.9)
    first = stabilizer.update(reading, 0.0)
    for i in range(1, 10):
        first = stabilizer.update(reading, i / 30)
    assert first.stable == "open_palm"
    assert first.held_s > 0.2


def test_hand_lost_resets_stabilizer():
    stabilizer = GestureStabilizer(window=3)
    for i in range(5):
        stabilizer.update(GestureReading(raw="point"), i / 30)
    lost = stabilizer.update(None, 0.5)
    assert lost.stable == "none"
