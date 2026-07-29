from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pymongo.errors import OperationFailure
from starlette.requests import Request

from api.routes.tasks import process_task, task_progress_callback
from api.routes import frontend_compat
from api.routes.lanes import configure_lanes
from api.routes.dashboard import get_dashboard_stats
from api.schemas.lane import LaneConfigRequest
from api.schemas.task import TaskCreateRequest, TaskCreateResponse, TaskProgressCallback
from shared.database import LocalJsonDatabase, _ensure_mongo_indexes


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


def test_mongo_index_migration_accepts_legacy_equivalent_index() -> None:
    import asyncio

    class Collection:
        name = "tasks"

        def __init__(self, field: str):
            self.field = field
            self.create_calls = 0

        async def create_index(self, field: str, **options):
            self.create_calls += 1
            if field == self.field:
                raise OperationFailure("IndexOptionsConflict", code=85)

        async def index_information(self):
            return {f"{self.field}_1": {"key": [(self.field, 1)], "unique": self.field == "task_id"}}

    class Database:
        tasks = type("Tasks", (), {})()
        lane_configs = type("LaneConfigs", (), {})()
        traffic_statistics = type("TrafficStatistics", (), {})()

    database = Database()
    database.tasks = Collection("task_id")
    database.lane_configs = Collection("video_id")
    database.traffic_statistics = Collection("task_id")

    asyncio.run(_ensure_mongo_indexes(database))

    assert database.tasks.create_calls == 4
    assert database.lane_configs.create_calls == 2
    assert database.traffic_statistics.create_calls == 1


def test_compat_submit_uses_canonical_task_id_and_video_id(tmp_path: Path, monkeypatch) -> None:
    import asyncio

    from starlette.requests import Request

    database = LocalJsonDatabase(str(tmp_path / "database.json"))
    now = __import__("datetime").datetime.utcnow()
    asyncio.run(database.tasks.insert_one({
        "task_id": "task-1",
        "video_id": "video-1",
        "status": "uploaded",
        "progress": 0,
        "created_at": now,
        "updated_at": now,
    }))
    monkeypatch.setattr(frontend_compat, "get_database", lambda: database)
    process = AsyncMock(return_value=TaskCreateResponse(task_id="task-1", status="pending", message="queued"))
    monkeypatch.setattr(frontend_compat, "process_task", process)

    response = asyncio.run(frontend_compat.compat_submit(
        Request({"type": "http", "method": "POST", "headers": [], "path": "/tasks"}),
        {"task_id": "task-1", "lane_config": _lane_config()},
    ))

    assert response["task_id"] == "task-1"
    assert response["status"] == "pending"
    assert process.await_args.args[0].video_id == "video-1"


def test_dashboard_tolerates_legacy_task_documents(tmp_path: Path) -> None:
    import asyncio

    database = LocalJsonDatabase(str(tmp_path / "database.json"))
    asyncio.run(database.tasks.insert_one({"video_id": "video-legacy", "status": "uploaded"}))

    response = asyncio.run(get_dashboard_stats(database))

    assert response.total_tasks == 1
    assert response.recent_tasks[0].task_id == "video-legacy"
    assert response.recent_tasks[0].progress == 0


def test_safe_error_message_redacts_connection_credentials() -> None:
    from shared.safe_errors import redact_url_credentials, safe_error_message

    error = ValueError(
        "redis://:super-secret@cache.example/0 failed with token=abc123"
    )

    message = safe_error_message(error)

    assert "super-secret" not in message
    assert "abc123" not in message
    assert "<redacted>" in message
    assert redact_url_credentials("rtsp://operator:secret@camera.example/live") == "rtsp://camera.example/live"


def test_inference_factory_falls_back_to_remote_when_local_is_unavailable(monkeypatch) -> None:
    from shared.config import settings
    from worker.pipeline import inference_factory

    class RemoteClient:
        def __init__(self, **_kwargs):
            pass

    monkeypatch.setattr(settings, "AI_LOCAL", True)
    monkeypatch.setattr(settings, "AI_SERVING_URL", "https://inference.example")
    monkeypatch.setattr(
        inference_factory,
        "LocalInferenceClient",
        lambda **_kwargs: (_ for _ in ()).throw(FileNotFoundError("model unavailable")),
    )
    monkeypatch.setattr(inference_factory, "InferenceClient", RemoteClient)

    client = inference_factory.build_inference_client()

    assert isinstance(client, RemoteClient)


def test_chunk_completion_rejects_corrupt_metadata(tmp_path: Path, monkeypatch) -> None:
    import asyncio

    from api.routes import upload

    upload_dir = tmp_path / "upload-1"
    upload_dir.mkdir()
    (upload_dir / "meta.json").write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(upload, "CHUNK_DIR", tmp_path)

    with pytest.raises(HTTPException) as error:
        asyncio.run(upload.complete_chunked_upload("upload-1", db=object()))

    assert error.value.status_code == 400


def test_lane_config_cannot_reopen_processing_task(tmp_path: Path) -> None:
    import asyncio

    database = LocalJsonDatabase(str(tmp_path / "database.json"))
    now = __import__("datetime").datetime.utcnow()
    asyncio.run(database.tasks.insert_one({
        "task_id": "task-1",
        "video_id": "video-1",
        "status": "processing",
        "created_at": now,
        "updated_at": now,
    }))

    with pytest.raises(HTTPException) as error:
        asyncio.run(configure_lanes(LaneConfigRequest.model_validate(_lane_config()), database))

    assert error.value.status_code == 409


def test_lane_config_claims_uploaded_task_and_persists_config(tmp_path: Path) -> None:
    import asyncio

    database = LocalJsonDatabase(str(tmp_path / "database.json"))
    now = __import__("datetime").datetime.utcnow()
    asyncio.run(database.tasks.insert_one({
        "task_id": "task-1",
        "video_id": "video-1",
        "status": "uploaded",
        "created_at": now,
        "updated_at": now,
    }))

    response = asyncio.run(configure_lanes(LaneConfigRequest.model_validate(_lane_config()), database))
    task = asyncio.run(database.tasks.find_one({"task_id": "task-1"}))
    saved = asyncio.run(database.lane_configs.find_one({"video_id": "video-1"}))

    assert response.lane_count == 1
    assert task["status"] == "configured"
    assert saved["task_id"] == "task-1"


def test_expired_task_cleanup_removes_local_preview(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    from datetime import datetime, timedelta

    from api.services import cleanup_service
    from shared.config import settings

    database = LocalJsonDatabase(str(tmp_path / "database.json"))
    now = datetime.utcnow()
    asyncio.run(database.tasks.insert_one({
        "task_id": "task-1",
        "video_id": "video-1",
        "status": "completed",
        "expires_at": now - timedelta(minutes=1),
        "created_at": now,
        "updated_at": now,
    }))
    preview = tmp_path / "previews" / "video-1.jpg"
    preview.parent.mkdir()
    preview.write_bytes(b"preview")

    monkeypatch.setattr(cleanup_service.db_instance, "db", database)
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(cleanup_service.r2_client, "delete_file", lambda _key: None)

    asyncio.run(cleanup_service.run_data_cleanup())

    task = asyncio.run(database.tasks.find_one({"task_id": "task-1"}))
    assert task["status"] == "archived"
    assert not preview.exists()


def test_queue_failure_marks_claimed_task_failed(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    from datetime import datetime

    database = LocalJsonDatabase(str(tmp_path / "database.json"))
    now = datetime.utcnow()
    task = {
        "task_id": "task-1",
        "video_id": "video-1",
        "status": "configured",
        "progress": 0,
        "video_url": "https://storage.example/video.mp4",
        "working_video_url": "https://storage.example/video.mp4",
        "created_at": now,
        "updated_at": now,
    }
    config = _lane_config()
    config["task_id"] = "task-1"
    asyncio.run(database.tasks.insert_one(task))
    asyncio.run(database.lane_configs.insert_one(config))

    from api.routes import tasks
    monkeypatch.setattr(tasks.celery_app, "send_task", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("redis down")))
    monkeypatch.setattr(tasks.settings, "CALLBACK_HOST", "http://api.test")

    request = Request({"type": "http", "method": "POST", "path": "/api/v1/tasks/process", "headers": []})
    with pytest.raises(HTTPException) as error:
        asyncio.run(process_task(TaskCreateRequest(video_id="video-1"), request, database))

    saved = asyncio.run(database.tasks.find_one({"task_id": "task-1"}))
    assert error.value.status_code == 503
    assert saved["status"] == "failed"
    assert saved["stage"] == "queue_unavailable"
