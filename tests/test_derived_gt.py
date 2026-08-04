import json

import pytest

from benchmark.derived_gt import aggregate_counts, derive_events_for_sequence, load_geometry
from benchmark.detrac_parser import Tracklet


def test_derive_events_requires_side_change_intersection_and_direction():
    geometry = {
        "geometry_version": "synthetic-v1",
        "geometry_space": "source_frame",
        "resolution": {"width": 100, "height": 100},
        "lanes": [
            {
                "lane_id": "full_down",
                "direction_name": "down",
                "valid_zone": [[0, 0], [100, 0], [100, 100], [0, 100]],
                "counting_line": [[0, 50], [100, 50]],
                "direction": [[50, 0], [50, 100]],
                "class_allowed": ["car"],
            },
            {
                "lane_id": "full_up",
                "direction_name": "up",
                "valid_zone": [[0, 0], [100, 0], [100, 100], [0, 100]],
                "counting_line": [[0, 50], [100, 50]],
                "direction": [[50, 100], [50, 0]],
                "class_allowed": ["car"],
            },
        ],
    }
    tracklets = {
        1: Tracklet(track_id=1, class_name="car", frames={1: (40, 20, 60, 40), 2: (40, 40, 60, 60)}),
        2: Tracklet(track_id=2, class_name="car", frames={1: (10, 70, 30, 90), 2: (10, 20, 30, 40)}),
    }

    events = derive_events_for_sequence("SYN", tracklets, geometry, fps=25)
    assert [(e["gt_track_id"], e["lane_id"], e["direction"]) for e in events] == [
        (1, "full_down", "down"),
        (2, "full_up", "up"),
    ]
    assert all(e["anchor"] == "bottom_center" for e in events)
    assert aggregate_counts(events) == [
        {"video_id": "SYN", "lane_id": "full_down", "class_name": "car", "direction": "down", "expected_count": 1},
        {"video_id": "SYN", "lane_id": "full_up", "class_name": "car", "direction": "up", "expected_count": 1},
    ]


def test_derive_events_deduplicates_per_track_lane():
    geometry = {
        "geometry_version": "synthetic-v1",
        "geometry_space": "source_frame",
        "resolution": {"width": 100, "height": 100},
        "lanes": [
            {
                "lane_id": "full_down",
                "direction_name": "down",
                "valid_zone": [[0, 0], [100, 0], [100, 100], [0, 100]],
                "counting_line": [[0, 50], [100, 50]],
                "direction": [[50, 0], [50, 100]],
                "class_allowed": ["car"],
            }
        ],
    }
    tracklets = {
        1: Tracklet(
            track_id=1,
            class_name="car",
            frames={
                1: (40, 20, 60, 40),
                2: (40, 40, 60, 60),
                3: (40, 20, 60, 40),
                4: (40, 40, 60, 60),
            },
        )
    }

    events = derive_events_for_sequence("SYN", tracklets, geometry, fps=25)
    assert len(events) == 1
    assert events[0]["gt_track_id"] == 1


def test_load_manual_geometry_requires_matching_sequence_id(tmp_path):
    geometry_dir = tmp_path / "geometry"
    geometry_dir.mkdir()
    (geometry_dir / "SYN.json").write_text(
        json.dumps(
            {
                "geometry_version": "synthetic-manual-v1",
                "sequence_id": "OTHER",
                "geometry_space": "source_frame",
                "resolution": {"width": 100, "height": 100},
                "lanes": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="sequence_id mismatch"):
        load_geometry(
            "SYN",
            {"sequence_id": "SYN", "resolution": {"width": 100, "height": 100}},
            geometry_dir,
            "manual",
        )


def test_load_default_geometry_writes_geometry_file(tmp_path):
    geometry = load_geometry(
        "SYN",
        {"sequence_id": "SYN", "resolution": {"width": 100, "height": 100}},
        tmp_path,
        "default",
    )

    assert geometry["geometry_version"] == "SYN-geometry-v1"
    assert (tmp_path / "SYN.json").exists()
