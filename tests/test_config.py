from __future__ import annotations

import pytest

from tfengine.counting.config import (
    CounterConfig,
    CounterSettings,
    LaneConfig,
    parse_counter_config,
)


def test_parse_counter_config_full() -> None:
    raw = {
        "method": "counting_gate",
        "settings": {
            "movement_threshold_px": 2.0,
            "cooldown_frames": 5,
            "cooldown_distance_px": 16.0,
            "zone_policy": "strict",
        },
        "lanes": [
            {
                "lane_id": "lane_1",
                "counting_line": [[0, 10], [20, 10]],
                "valid_zone": [[0, 0], [20, 0], [20, 20], [0, 20]],
                "direction": [[10, 0], [10, 20]],
                "segment_ratio": [0.5, 0.5],
                "class_allowed": ["car", "bus"],
            }
        ],
    }

    config = parse_counter_config(raw)

    assert config.method == "counting_gate"
    assert config.settings.movement_threshold_px == 2.0
    assert config.settings.cooldown_frames == 5
    assert config.settings.cooldown_distance_px == 16.0
    assert config.settings.zone_policy == "strict"

    assert len(config.lanes) == 1
    lane = config.lanes[0]
    assert lane.lane_id == "lane_1"
    assert lane.counting_line == ((0.0, 10.0), (20.0, 10.0))
    assert lane.valid_zone == [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)]
    assert lane.direction == ((10.0, 0.0), (10.0, 20.0))
    assert lane.segment_ratio == (0.5, 0.5)
    assert lane.class_allowed == ["car", "bus"]


def test_parse_counter_config_default_settings() -> None:
    raw = {
        "method": "counting_line_per_lane",
        "lanes": [
            {
                "lane_id": "lane_1",
                "counting_line": [[0, 0], [10, 10]],
            }
        ],
    }

    config = parse_counter_config(raw)

    assert config.settings.movement_threshold_px == 5.0
    assert config.settings.cooldown_frames == 12
    assert config.settings.cooldown_distance_px == 32.0
    assert config.settings.zone_policy == "flexible"


def test_parse_counter_config_optional_fields_none() -> None:
    raw = {
        "method": "counting_line_per_lane",
        "lanes": [
            {
                "lane_id": "lane_1",
                "counting_line": [[0, 0], [10, 10]],
            }
        ],
    }

    config = parse_counter_config(raw)
    lane = config.lanes[0]

    assert lane.valid_zone is None
    assert lane.direction is None
    assert lane.segment_ratio is None
    assert lane.class_allowed is None


def test_parse_counter_config_multiple_lanes() -> None:
    raw = {
        "method": "counting_line_per_lane",
        "lanes": [
            {"lane_id": "lane_1", "counting_line": [[0, 0], [10, 10]]},
            {"lane_id": "lane_2", "counting_line": [[0, 20], [10, 20]]},
            {"lane_id": "lane_3", "counting_line": [[0, 40], [10, 40]]},
        ],
    }

    config = parse_counter_config(raw)
    assert len(config.lanes) == 3
    assert [l.lane_id for l in config.lanes] == ["lane_1", "lane_2", "lane_3"]


def test_parse_counter_config_empty_lanes() -> None:
    raw = {"method": "counting_line_per_lane", "lanes": []}

    config = parse_counter_config(raw)
    assert config.lanes == []
