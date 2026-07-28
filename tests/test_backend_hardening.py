from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.routes.tasks import task_progress_callback
from api.schemas.lane import LaneConfigRequest
from api.schemas.task import TaskProgressCallback
from shared.database import LocalJsonDatabase


def _lane_config() -> dict:
    return {
        "video_id": "video-1",
        "camera_id": "camera-1",
        "resolution": {"width": 1280, "height": 720},
        "roi_polygon": [[0, 0], [1280, 0], [1280, 720]],
        "processing_roi": {
            "type": "rectangle",
            "x": 0,
            "y": 0,
            "width": 1280,
            "height": 720,
            "purpose": "inference_processing",
        },
        "settings": {
            "movement_threshold_px": 5,
            "cooldown_frames": 12,
            "cooldown_distance_px": 32,
            "zone_policy": "flexible",
        },
        "lanes": [
            {
                "lane_id": "lane-1",
                "valid_zone": [[0, 0], [600, 0], [600, 720]],
                "counting_line": [[300, 100], [300, 600]],
                "direction": [[0, 0], [1, 0]],
                "class_allowed": ["car", "truck"],
            }
        ],
    }


def test_lane_config_rejects_out_of_bounds_geometry() -> None:
    payload = _lane_config()
    payload["lanes"][0]["counting_line"] = [[300, 100], [1300, 600]]

    with pytest.raises(ValueError, match="outside"):
        LaneConfigRequest.model_validate(payload)


def test_local_json_save_is_atomic(tmp_path: Path) -> None:
    database = LocalJsonDatabase(str(tmp_path / "database.json"))

    # The collection write exercises the same save path used by API fallback
    # mode and should never leave a partially written JSON document behind.
    import asyncio

    asyncio.run(database.tasks.insert_one({"task_id": "task-1"}))
    assert (tmp_path / "database.json").exists()
    assert not (tmp_path / ".database.json.tmp").exists()


def test_progress_callback_rejects_regression() -> None:
    import asyncio

    db = AsyncMock()
    db.tasks.find_one = AsyncMock(return_value={
        "task_id": "task-1",
        "status": "processing",
        "progress": 60,
    })
    db.tasks.update_one = AsyncMock()
    request = Request({"type": "http", "headers": []})
    payload = TaskProgressCallback(status="processing", progress=40)

    with pytest.raises(HTTPException) as error:
        asyncio.run(task_progress_callback("task-1", payload, request, db))

    assert error.value.status_code == 409
    db.tasks.update_one.assert_not_awaited()
