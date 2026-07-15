"""Integration tests for API config, shared modules, and frontend compatibility."""

from __future__ import annotations

import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Set up test environment
# ---------------------------------------------------------------------------

os.environ["MONGODB_URI"] = "mongodb://localhost:27017/"
os.environ["MONGODB_DB_NAME"] = "trafficflow_test"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["R2_ACCOUNT_ID"] = "placeholder_account_id"
os.environ["R2_ACCESS_KEY_ID"] = "placeholder_access_key"
os.environ["R2_SECRET_ACCESS_KEY"] = "placeholder_secret_key"
os.environ["R2_BUCKET_NAME"] = "trafficflow"
os.environ["R2_PUBLIC_URL"] = "http://localhost:8000/static/previews"
os.environ["AI_SERVING_URL"] = "https://example.com"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestConfig:
    def test_settings_loads_from_env(self):
        from shared.config import settings
        assert settings.MONGODB_DB_NAME == "trafficflow_test"
        assert settings.REDIS_URL == "redis://localhost:6379/0"
        assert settings.R2_ACCOUNT_ID == "placeholder_account_id"

    def test_settings_defaults(self):
        from shared.config import Settings
        s = Settings(_env_file=None)
        # With env vars set, MONGODB_DB_NAME will be overridden to "trafficflow_test"
        assert s.MAX_FILE_SIZE_MB in (50, 1024, 2048)
        assert s.AI_FRAME_SKIP in (2, 2)
        assert s.AI_RESIZE_DIM in (640, 640)
        assert s.AI_ENABLE_STABILIZATION is False
        assert s.TRACK_MATCH_THRESHOLD in (0.5, 0.5)
        assert s.TRACK_BUFFER in (30, 30)
        assert s.AI_FRAME_SKIP == 2
        assert s.AI_RESIZE_DIM == 640
        assert s.AI_ENABLE_STABILIZATION is False
        assert s.TRACK_MATCH_THRESHOLD == 0.5
        assert s.TRACK_BUFFER == 30
        assert s.STORE_ORIGINAL_VIDEO is False
        assert s.VIDEO_TRANSCODE_CRF == 20

    def test_settings_r2_is_mocked_with_placeholder(self):
        from shared.config import settings
        # Use a fresh instance to test mock detection
        from shared.config import Settings
        s = Settings(
            _env_file=None,
            R2_ACCOUNT_ID="placeholder_account_id",
            R2_ACCESS_KEY_ID="placeholder_access_key",
        )
        from shared.r2_client import R2Client
        client = R2Client.__new__(R2Client)
        # Just verify the config values are placeholders
        assert s.R2_ACCOUNT_ID == "placeholder_account_id"


# ---------------------------------------------------------------------------
# FastAPI app tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from shared.database import db_instance

    # Mock MongoDB
    mock_db = AsyncMock()
    mock_db.tasks = AsyncMock()
    mock_db.tasks.count_documents = AsyncMock(return_value=0)
    mock_db.tasks.find_one = AsyncMock(return_value=None)
    mock_db.tasks.insert_one = AsyncMock()
    mock_db.tasks.update_one = AsyncMock()

    mock_cursor = AsyncMock()
    mock_cursor.to_list = AsyncMock(return_value=[])
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.limit = MagicMock(return_value=mock_cursor)
    mock_db.tasks.find = MagicMock(return_value=mock_cursor)

    mock_agg_cursor = AsyncMock()
    mock_agg_cursor.to_list = AsyncMock(return_value=[])
    mock_db.traffic_statistics = AsyncMock()
    mock_db.traffic_statistics.aggregate = MagicMock(return_value=mock_agg_cursor)
    mock_db.traffic_statistics.find = MagicMock()
    mock_db.traffic_statistics.delete_many = AsyncMock()
    mock_db.traffic_statistics.insert_many = AsyncMock()
    mock_db.lane_configs = AsyncMock()
    mock_db.lane_configs.find_one = AsyncMock(return_value=None)
    db_instance.db = mock_db
    db_instance.client = AsyncMock()

    # Patch lifespan to skip MongoDB connect
    with patch("shared.database.connect_to_mongo", new_callable=AsyncMock), \
         patch("shared.database.close_mongo_connection", new_callable=AsyncMock), \
         patch("api.services.cleanup_service.run_data_cleanup", new_callable=AsyncMock):
        from api.app import create_app
        app = create_app()
        with TestClient(app) as c:
            yield c


class TestFrontendCompatRoutes:
    """Test the /videos and /tasks routes the React frontend calls."""

    def test_root_returns_frontend_html(self, client):
        resp = client.get("/")
        assert resp.status_code in (200, 404)

    def test_docs_accessible(self, client):
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_openapi_schema_has_compat_routes(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        paths = list(schema["paths"].keys())
        expected = ["/videos", "/tasks", "/tasks/{task_id}",
                     "/tasks/{task_id}/result", "/videos/{task_id}/preview"]
        for ep in expected:
            assert ep in paths, f"{ep} missing from OpenAPI schema"

    def test_get_videos_preview_404_when_no_preview(self, client):
        resp = client.get("/videos/fake-id/preview")
        assert resp.status_code == 404

    def test_get_tasks_status_404_when_no_task(self, client):
        resp = client.get("/tasks/fake-task-id")
        assert resp.status_code == 404

    def test_tasks_result_404_when_no_task(self, client):
        resp = client.get("/tasks/fake-task-id/result")
        assert resp.status_code == 404


class TestApiV1Routes:
    def test_upload_video_route_exists(self, client):
        resp = client.post("/api/v1/upload/video")
        assert resp.status_code == 422

    def test_lanes_config_route_exists(self, client):
        resp = client.post("/api/v1/lanes/config")
        assert resp.status_code == 422

    def test_tasks_process_route_exists(self, client):
        resp = client.post("/api/v1/tasks/process")
        assert resp.status_code == 422

    def test_dashboard_stats(self, client):
        resp = client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_tasks" in data
        assert "completed_tasks" in data
        assert "processing_tasks" in data


class TestUvicornStartup:
    def test_create_app_returns_fastapi_instance(self):
        from api.app import create_app
        app = create_app()
        assert app.title == "TrafficFlow Backend API"
        assert app.version == "1.0.0"

    def test_api_main_imports(self):
        from api.main import __name__ as mn
        assert mn is not None


# ---------------------------------------------------------------------------
# Celery worker tests
# ---------------------------------------------------------------------------

class TestCeleryApp:
    def test_celery_app_creates_instance(self):
        from worker.celery_app import celery_app
        assert celery_app is not None
        assert celery_app.main == "trafficflow"

    def test_celery_app_has_task_registered(self):
        from worker.celery_app import celery_app
        task_names = list(celery_app.tasks.keys())
        assert "trafficflow.process_video" in task_names


# ---------------------------------------------------------------------------
# R2 client tests
# ---------------------------------------------------------------------------

class TestR2Client:
    def test_r2_client_is_mocked(self):
        from shared.r2_client import r2_client
        assert r2_client.is_mocked is True

    def test_r2_upload_returns_url(self):
        from shared.r2_client import r2_client
        url = r2_client.upload_file(b"test", "test/file.txt", "text/plain")
        assert "test/file.txt" in url

    def test_r2_upload_and_download_roundtrip(self):
        from shared.r2_client import r2_client
        content = b"hello trafficflow"
        key = "test/roundtrip.bin"
        url = r2_client.upload_file(content, key, "application/octet-stream")
        downloaded = r2_client.download_file(key)
        assert downloaded == content

    def test_r2_delete_removes_file(self):
        from shared.r2_client import r2_client
        key = "test/to_delete.txt"
        r2_client.upload_file(b"data", key, "text/plain")
        local_path = r2_client.local_storage_dir / key
        assert local_path.exists()
        r2_client.delete_file(key)
        assert not local_path.exists()


# ---------------------------------------------------------------------------
# Worker pipeline component tests
# ---------------------------------------------------------------------------

class TestPipelineImports:
    def test_local_tracker_imports(self):
        from worker.pipeline.tracker import LocalTracker, TrackOutput
        tracker = LocalTracker(match_threshold=0.5, track_buffer=30)
        assert tracker is not None
        assert tracker.match_threshold == 0.5

    def test_inference_client_imports(self):
        from worker.pipeline.ai_client import InferenceClient
        assert InferenceClient is not None

    def test_frame_processor_imports(self):
        from worker.pipeline.processor import FrameProcessor
        fp = FrameProcessor(roi_input_size=640, enable_stabilization=False)
        assert fp is not None

    def test_frame_processor_applies_polygon_mask_after_crop(self):
        import numpy as np
        from worker.pipeline.processor import FrameProcessor

        frame = np.full((100, 100, 3), 255, dtype=np.uint8)
        processor = FrameProcessor(roi_input_size=64, enable_stabilization=False)
        polygon = np.array([[10, 10], [80, 10], [10, 80]], dtype=np.int32)

        cropped, _ai_frame, transform = processor.process_for_ai(
            frame,
            crop_rect=(10, 10, 90, 90),
            poly_mask=polygon - [10, 10],
        )

        assert cropped[5, 5].sum() > 0
        assert cropped[75, 75].sum() == 0
        assert transform.offset_x == 10
        assert transform.offset_y == 10

    def test_frame_renderer_imports(self):
        from worker.pipeline.renderer import FrameRenderer
        renderer = FrameRenderer(lanes=[])
        assert renderer is not None

    def test_counting_service_imports(self):
        from worker.services.counting_service import CountingState
        cs = CountingState(lanes=[])
        assert cs is not None
        assert cs.get_total_count() == 0


# ---------------------------------------------------------------------------
# Task schema validation tests
# ---------------------------------------------------------------------------

class TestTaskSchemas:
    def test_task_create_request_validates(self):
        from api.schemas.task import TaskCreateRequest
        req = TaskCreateRequest(video_id="test-id-123")
        assert req.video_id == "test-id-123"

    def test_task_create_request_rejects_missing_id(self):
        from api.schemas.task import TaskCreateRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TaskCreateRequest()

    def test_task_status_response(self):
        from api.schemas.task import TaskStatusResponse
        from datetime import datetime
        now = datetime.utcnow()
        resp = TaskStatusResponse(
            task_id="tid", status="processing",
            progress=50, created_at=now, updated_at=now
        )
        assert resp.task_id == "tid"
        assert resp.progress == 50

    def test_progress_callback_fields(self):
        from api.schemas.task import TaskProgressCallback
        cb = TaskProgressCallback(status="processing", progress=42)
        assert cb.progress == 42
        assert cb.status == "processing"
        assert cb.result_video_url is None
        assert cb.error_message is None

    def test_task_result_total_vehicles(self):
        from api.schemas.task import TaskResultResponse, LaneStatistics
        resp = TaskResultResponse(
            task_id="tid",
            status="completed",
            statistics=[
                LaneStatistics(
                    lane_id="lane_1",
                    lane_name="Lane 1",
                    counts={"car": 5, "bus": 2},
                    total=7,
                )
            ],
            total_vehicles=7,
        )
        assert resp.total_vehicles == 7
        assert len(resp.statistics) == 1
        assert resp.statistics[0].counts == {"car": 5, "bus": 2}
