from __future__ import annotations

from trafficflow.counting.methods import TrackObservation, build_counter


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
