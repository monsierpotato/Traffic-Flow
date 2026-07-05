from __future__ import annotations

import pytest

from tfengine.counting.methods import TrackObservation, build_counter


def test_counting_line_per_lane_counts_single_crossing() -> None:
    counter = build_counter(
        {
            "method": "counting_line_per_lane",
            "settings": {"movement_threshold_px": 1},
            "lanes": [
                {
                    "lane_id": "lane_1",
                    "counting_line": [[0, 10], [20, 10]],
                    "class_allowed": ["car"],
                }
            ],
        }
    )

    assert counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 8))], 0) == []
    assert len(counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 12))], 1)) == 1
    assert counter.counts == {"lane_1": {"car": 1}}


def test_counting_gate_rejects_wrong_direction() -> None:
    counter = build_counter(
        {
            "method": "counting_gate",
            "settings": {"movement_threshold_px": 1},
            "lanes": [
                {
                    "lane_id": "lane_1",
                    "counting_line": [[0, 10], [20, 10]],
                    "valid_zone": [[0, 0], [20, 0], [20, 20], [0, 20]],
                    "direction": [[10, 0], [10, 20]],
                    "class_allowed": ["car"],
                }
            ],
        }
    )

    assert counter.update([TrackObservation(2, "car", (0, 0, 0, 0), (10, 12))], 0) == []
    assert counter.update([TrackObservation(2, "car", (0, 0, 0, 0), (10, 8))], 1) == []
    assert counter.counts == {"lane_1": {}}


def test_counting_rejects_wrong_class() -> None:
    counter = build_counter(
        {
            "method": "counting_line_per_lane",
            "settings": {"movement_threshold_px": 1},
            "lanes": [
                {
                    "lane_id": "lane_1",
                    "counting_line": [[0, 10], [20, 10]],
                    "class_allowed": ["car"],
                }
            ],
        }
    )

    events = counter.update(
        [TrackObservation(1, "bus", (0, 0, 0, 0), (10, 8)),
         TrackObservation(1, "bus", (0, 0, 0, 0), (10, 12))],
        1,
    )
    assert events == []
    assert counter.counts == {"lane_1": {}}


def test_counting_ignores_first_frame() -> None:
    counter = build_counter(
        {
            "method": "counting_line_per_lane",
            "settings": {"movement_threshold_px": 1},
            "lanes": [
                {
                    "lane_id": "lane_1",
                    "counting_line": [[0, 10], [20, 10]],
                    "class_allowed": ["car"],
                }
            ],
        }
    )

    events = counter.update(
        [TrackObservation(1, "car", (0, 0, 0, 0), (10, 12))], 0
    )
    assert events == []


def test_counting_requires_min_movement() -> None:
    counter = build_counter(
        {
            "method": "counting_line_per_lane",
            "settings": {"movement_threshold_px": 100},
            "lanes": [
                {
                    "lane_id": "lane_1",
                    "counting_line": [[0, 10], [20, 10]],
                    "class_allowed": ["car"],
                }
            ],
        }
    )

    counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 8))], 0)
    events = counter.update(
        [TrackObservation(1, "car", (0, 0, 0, 0), (10, 12))], 1
    )
    assert events == []
    assert counter.counts == {"lane_1": {}}


def test_counting_multiple_lanes_counts_independently() -> None:
    counter = build_counter(
        {
            "method": "counting_line_per_lane",
            "settings": {"movement_threshold_px": 1},
            "lanes": [
                {
                    "lane_id": "lane_1",
                    "counting_line": [[0, 10], [20, 10]],
                    "class_allowed": ["car"],
                },
                {
                    "lane_id": "lane_2",
                    "counting_line": [[0, 30], [20, 30]],
                    "class_allowed": ["car"],
                },
            ],
        }
    )

    counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 8))], 0)
    counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 12))], 1)
    counter.update([TrackObservation(2, "car", (0, 0, 0, 0), (10, 28))], 2)
    counter.update([TrackObservation(2, "car", (0, 0, 0, 0), (10, 32))], 3)

    assert counter.counts["lane_1"]["car"] == 1
    assert counter.counts["lane_2"]["car"] == 1


def test_counting_no_double_count_same_track() -> None:
    counter = build_counter(
        {
            "method": "counting_line_per_lane",
            "settings": {"movement_threshold_px": 1},
            "lanes": [
                {
                    "lane_id": "lane_1",
                    "counting_line": [[0, 10], [20, 10]],
                    "class_allowed": ["car"],
                }
            ],
        }
    )

    counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 8))], 0)
    counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 12))], 1)
    counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 14))], 2)
    counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 16))], 3)

    assert counter.counts["lane_1"]["car"] == 1


def test_counting_multiple_vehicle_types() -> None:
    counter = build_counter(
        {
            "method": "counting_line_per_lane",
            "settings": {"movement_threshold_px": 1, "cooldown_frames": 0, "cooldown_distance_px": 0},
            "lanes": [
                {
                    "lane_id": "lane_1",
                    "counting_line": [[0, 10], [100, 10]],
                    "class_allowed": ["car", "bus", "truck"],
                }
            ],
        }
    )

    counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 8))], 0)
    counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 12))], 1)
    counter.update([TrackObservation(2, "bus", (0, 0, 0, 0), (50, 8))], 2)
    counter.update([TrackObservation(2, "bus", (0, 0, 0, 0), (50, 12))], 3)

    assert counter.counts["lane_1"]["car"] == 1
    assert counter.counts["lane_1"]["bus"] == 1
    assert counter.counts["lane_1"].get("truck") is None


def test_counting_cooldown_prevents_duplicate() -> None:
    counter = build_counter(
        {
            "method": "counting_line_per_lane",
            "settings": {"movement_threshold_px": 1, "cooldown_frames": 10, "cooldown_distance_px": 100},
            "lanes": [
                {
                    "lane_id": "lane_1",
                    "counting_line": [[0, 10], [20, 10]],
                    "class_allowed": ["car"],
                }
            ],
        }
    )

    counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 8))], 0)
    counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 12))], 1)
    counter.update([TrackObservation(2, "car", (0, 0, 0, 0), (12, 8))], 2)
    counter.update([TrackObservation(2, "car", (0, 0, 0, 0), (12, 12))], 3)

    assert counter.counts["lane_1"]["car"] == 1


def test_counting_strict_zone_requires_point_inside() -> None:
    counter = build_counter(
        {
            "method": "counting_gate",
            "settings": {"movement_threshold_px": 1, "zone_policy": "strict"},
            "lanes": [
                {
                    "lane_id": "lane_1",
                    "counting_line": [[0, 10], [20, 10]],
                    "valid_zone": [[5, 5], [15, 5], [15, 15], [5, 15]],
                    "class_allowed": ["car"],
                }
            ],
        }
    )

    # Point (10, 12) is inside zone → should count
    counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 8))], 0)
    events = counter.update(
        [TrackObservation(1, "car", (0, 0, 0, 0), (10, 12))], 1
    )
    assert len(events) == 1


def test_counting_strict_zone_rejects_point_outside() -> None:
    counter = build_counter(
        {
            "method": "counting_gate",
            "settings": {"movement_threshold_px": 1, "zone_policy": "strict"},
            "lanes": [
                {
                    "lane_id": "lane_1",
                    "counting_line": [[0, 10], [20, 10]],
                    "valid_zone": [[5, 5], [15, 5], [15, 15], [5, 15]],
                    "class_allowed": ["car"],
                }
            ],
        }
    )

    # Point (10, 18) is OUTSIDE zone → should NOT count
    counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 8))], 0)
    events = counter.update(
        [TrackObservation(1, "car", (0, 0, 0, 0), (10, 18))], 1
    )
    assert events == []


def test_counting_accepts_correct_direction() -> None:
    counter = build_counter(
        {
            "method": "counting_gate",
            "settings": {"movement_threshold_px": 1},
            "lanes": [
                {
                    "lane_id": "lane_1",
                    "counting_line": [[0, 10], [20, 10]],
                    "valid_zone": [[0, 0], [20, 0], [20, 20], [0, 20]],
                    "direction": [[10, 0], [10, 20]],
                    "class_allowed": ["car"],
                }
            ],
        }
    )

    # Moving downward (same as direction) → should count
    counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 8))], 0)
    events = counter.update(
        [TrackObservation(1, "car", (0, 0, 0, 0), (10, 12))], 1
    )
    assert len(events) == 1
    assert counter.counts["lane_1"]["car"] == 1


def test_counting_counter_event_contains_all_fields() -> None:
    counter = build_counter(
        {
            "method": "counting_line_per_lane",
            "settings": {"movement_threshold_px": 1},
            "lanes": [
                {
                    "lane_id": "lane_1",
                    "counting_line": [[0, 10], [20, 10]],
                    "class_allowed": ["car"],
                }
            ],
        }
    )

    counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 8))], 0)
    events = counter.update(
        [TrackObservation(1, "car", (0, 0, 0, 0), (10, 12))], 1
    )

    assert len(events) == 1
    event = events[0]
    assert event.frame_index == 1
    assert event.track_id == 1
    assert event.lane_id == "lane_1"
    assert event.class_name == "car"
    assert event.point == (10.0, 12.0)
