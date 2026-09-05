"""Behavioral coverage for bounded, irregular crystal movement."""

import random

import pytest

from oh_no_parent_control_kiosk.floating_islands import (
    EXCURSION, FloatingIslands, RandomFloat,
)


def test_paths_are_bounded_visible_and_independent():
    paths = [RandomFloat(random.Random(seed)) for seed in range(4)]
    samples = [[path.position(frame / 30) for frame in range(30 * 120)]
               for path in paths]
    for positions in samples:
        assert max(positions) <= EXCURSION[1]
        assert min(positions) >= -EXCURSION[1]
        assert max(positions) - min(positions) > 20 / 1080
        # Less than half a screen pixel per frame even at the fastest point.
        assert max(abs(b - a) * 1080 for a, b in zip(positions, positions[1:])) < 0.5
    for index, positions in enumerate(samples):
        for other in samples[index + 1:]:
            assert any((b - a) * (d - c) < 0
                       for a, b, c, d in zip(positions, positions[1:], other, other[1:]))


def test_turn_heights_and_intervals_keep_changing():
    path = RandomFloat(random.Random(42))
    positions = [path.position(frame / 20) for frame in range(20 * 120)]
    turns = [index for index in range(1, len(positions) - 1)
             if (positions[index] - positions[index - 1])
             * (positions[index + 1] - positions[index]) < 0]
    intervals = [(b - a) / 20 for a, b in zip(turns, turns[1:])]
    heights = [abs(positions[index]) * 1080 for index in turns]
    assert len(turns) > 15
    assert max(intervals) - min(intervals) > 2
    assert max(heights) - min(heights) > 4


def test_turns_do_not_jump_in_position_velocity_or_acceleration():
    path = RandomFloat(random.Random(7))
    for _ in range(20):
        turn_at = path._starts_at + path._duration
        step = 0.001
        before = path.position(turn_at - 2 * step)
        near_before = path.position(turn_at - step)
        at_turn = path.position(turn_at)
        near_after = path.position(turn_at + step)
        after = path.position(turn_at + 2 * step)
        assert abs(near_before - near_after) * 1080 < 0.001
        assert abs((near_after - near_before) / (2 * step)) * 1080 < 0.001
        left_acceleration = (at_turn - 2 * near_before + before) / step ** 2
        right_acceleration = (after - 2 * near_after + at_turn) / step ** 2
        assert abs(left_acceleration - right_acceleration) * 1080 < 0.1


def test_elapsed_time_is_independent_of_frame_rate_or_hidden_window():
    sparse = RandomFloat(random.Random(9))
    dense = RandomFloat(random.Random(9))
    for frame in range(1, 7201):
        position = dense.position(frame / 30)
    assert sparse.position(240) == pytest.approx(position)
    assert sparse.position(240) == pytest.approx(position)


def test_missing_artwork_preserves_static_scene_and_lightning_origins():
    layers = FloatingIslands(None, None)
    assert all(layers.offset(index, 10) == 0 for index in range(6))
    layers.draw(None, (0, 0, 1920, 1080), 10)
