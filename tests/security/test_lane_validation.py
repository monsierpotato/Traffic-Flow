import pytest
from pydantic import ValidationError

from api.schemas.lane import LaneConfigRequest


def _payload(**overrides):
    payload = {
        "video_id": "video-1",
        "camera_id": "camera-1",
        "resolution": {"width": 1920, "height": 1080},
        "roi_polygon": [[0, 0], [1920, 0], [1920, 1080]],
        "processing_roi": {"type": "rect", "x": 0, "y": 0, "width": 1920, "height": 1080, "purpose": "processing"},
        "settings": {"movement_threshold_px": 10, "cooldown_frames": 3, "cooldown_distance_px": 10, "zone_policy": "inside"},
        "lanes": [{"lane_id": "lane-1", "valid_zone": [[0, 0], [100, 0], [100, 100]], "counting_line": [[0, 0], [100, 0]], "direction": [[0, 0], [1, 0]], "class_allowed": ["car"]}],
    }
    payload.update(overrides)
    return payload


def test_lane_ids_must_be_unique():
    payload = _payload()
    payload["lanes"].append(dict(payload["lanes"][0]))
    with pytest.raises(ValidationError):
        LaneConfigRequest.model_validate(payload)


def test_geometry_must_stay_inside_resolution():
    payload = _payload()
    payload["lanes"][0]["valid_zone"][0] = [1921, 1]
    with pytest.raises(ValidationError):
        LaneConfigRequest.model_validate(payload)
