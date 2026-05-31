from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trafficflow.counting.methods import TrackObservation, build_counter


def test_counting_line_per_lane() -> None:
    counter = build_counter(
        {
            "method": "counting_line_per_lane",
            "settings": {
                "movement_threshold_px": 1,
                "cooldown_frames": 12,
                "cooldown_distance_px": 32,
                "zone_policy": "flexible",
            },
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
    assert len(counter.update([TrackObservation(1, "car", (0, 0, 0, 0), (10, 8))], 2)) == 0
    assert counter.counts == {"lane_1": {"car": 1}}


def test_counting_gate_direction() -> None:
    counter = build_counter(
        {
            "method": "counting_gate",
            "settings": {
                "movement_threshold_px": 1,
                "cooldown_frames": 12,
                "cooldown_distance_px": 32,
                "zone_policy": "flexible",
            },
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

    assert counter.update([TrackObservation(2, "car", (0, 0, 0, 0), (10, 8))], 0) == []
    assert len(counter.update([TrackObservation(2, "car", (0, 0, 0, 0), (10, 12))], 1)) == 1
    assert counter.update([TrackObservation(3, "car", (0, 0, 0, 0), (10, 12))], 2) == []
    assert len(counter.update([TrackObservation(3, "car", (0, 0, 0, 0), (10, 8))], 3)) == 0
    assert counter.counts == {"lane_1": {"car": 1}}


def main() -> int:
    test_counting_line_per_lane()
    test_counting_gate_direction()
    print("manual counting smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
