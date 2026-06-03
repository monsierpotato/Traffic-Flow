# Google Doc Source Snapshot: Phan chia cong viec deploy AI Traffic

Source URL: https://docs.google.com/document/d/1x_FbgG4XOSfbQDaqcqXk9Rz4iTaEZP2VXozowfbT0KU/edit?usp=sharing
Fetched: 2026-05-31

This raw note preserves the durable planning content from the Google Doc in a repo-local form for wiki ingest.

## Team Roles And Tasks

### Member 1: AI Pipeline Engineer

Purpose: make AI core usable by CLI, worker, and API.

- 1.1 Standardize the existing `TrafficFlowEngine`: complete `trafficflow/runtime/engine.py`; `process_video(...)` should return `VideoCountingResult` with frames, counts, and event summary.
- 1.2 Add `progress_callback`: call `callback(progress)` every 5-10 percent of frames so worker/API can update task progress.
- 1.3 Standardize result contract: create `result_sample.json` with `task_id`, `status`, `total_counts`, lanes, classes, output video URL/path, and events if needed.
- 1.4 Keep ONNX as optional optimization after the end-to-end flow is stable.

### Member 2: Frontend Engineer

Purpose: upload UI, lane drawing, progress, and result display.

- 2.1 Upload video UI: send video to backend and receive `video_id` plus `frame_preview_url`.
- 2.2 Canvas lane configuration: draw line/zone/direction on preview frame and export config in backend format.
- 2.3 Coordinate scaling: convert web display coordinates to original video coordinates.
- 2.4 Progress and result dashboard: poll `/tasks/{id}/status`, then call `/tasks/{id}/result` for chart/table/video output.

### Member 3: Backend Engineer

Purpose: FastAPI, database, and API contract.

- 3.1 FastAPI structure: create `trafficflow/api/app.py` and routes for upload, tasks, results, and lanes.
- 3.2 Database schema: create `Task`, `TrafficStatistic`, and `LaneConfig`.
- 3.3 Upload and preview frame API: `POST /api/v1/upload/video`, save video, extract first frame, return `video_id` and preview image URL.
- 3.4 Task API: `POST /api/v1/tasks/process`, `GET /api/v1/tasks/status/{task_id}`, and `GET /api/v1/tasks/result/{task_id}`.
- 3.5 Data retention: cron/background task to delete video files older than 3 days while keeping statistics.
- 3.6 File size and format limits: validate common video formats, reject files that are too large or too long, return 413 where appropriate.

### Member 4: DevOps / Worker Engineer

Purpose: Celery, Redis, Docker, and local compose.

- 4.1 Celery and Redis setup: configure `trafficflow/worker/` with Redis broker and `process_video_task(task_id)`.
- 4.2 Worker calls `TrafficFlowEngine`: load task from DB, call `engine.process_video(...)`, use `progress_callback` to update DB.
- 4.3 Dockerfile: backend image is lightweight; worker image includes OpenCV, ultralytics, torch, and other AI dependencies.
- 4.4 docker-compose: connect frontend, backend, worker, redis, and db with shared storage volume.
- 4.5 Exception handling and timeouts: wrap AI work in `try/except/finally`; failed tasks become `FAILED`; configure Celery time limit around 600 seconds.
- 4.6 Environment variables and security: use `.env` and `pydantic-settings` for `DB_URL`, `REDIS_URL`, and sensitive settings.

### Member 5: Integration / QA / Release

Purpose: end-to-end testing and release quality.

- 5.1 End-to-end local test: docker-compose flow from upload to preview, draw lane, submit, and result.
- 5.2 Coordinate QA: verify frontend lane and AI overlay alignment.
- 5.3 Queue stress test: upload 3-4 videos continuously and verify queue/worker stability.
- 5.4 Deployment checklist: deploy cloud only after local is stable; record bugs, logs, and performance bottlenecks.

## Five-Day Sprint Plan

### Day 1

- Finalize API contract, result JSON, and lane config.
- Member 1 standardizes engine.
- Member 3 builds FastAPI skeleton and DB schema.
- Member 2 builds upload/canvas mock.
- Member 4 builds Redis/Celery skeleton.

### Day 2

- Upload video and preview frame work.
- Frontend can draw lane and submit config.
- Engine can run from worker with local video.
- Worker can update task status.

### Day 3

- Local end-to-end via docker-compose.
- Fix paths, shared volumes, coordinate scale, and output result.

### Day 4

- Dashboard result, chart, output video.
- Queue stress test.
- Integration fixes.

### Day 5

- Optional cloud deploy.
- If unstable, prioritize production-like local docker-compose demo.

## Current Project Progress From Source

- Geometry core exists: primitives, polygon, intersection, direction.
- Counting logic exists: lane, line, zone, direction counting.
- YOLO + ByteTrack detector exists under `trafficflow/core_ai/`.
- CLI counting exists: `trafficflow/cli/run_counting.py`.
- OpenCV config generator exists: `trafficflow/cli/config_generator.py`.
- Runtime engine was newly separated: `trafficflow/runtime/engine.py`.
- Pipeline overlay was newly separated: `trafficflow/pipeline/overlay.py`.
- Basic tests exist for geometry/counting.
- API backend, worker async, queue, storage/database, observability, frontend web, Docker/deployment are not implemented yet except package boundaries.

## Priority Backlog

High priority:

1. Add `progress_callback` to `TrafficFlowEngine`.
2. Create `result_sample.json`.
3. Create `lane_config_sample.json`.
4. Implement FastAPI upload video and preview frame.
5. Create DB schema for task/status/result.
6. Connect Celery worker to engine.
7. Implement frontend canvas coordinate scaling.
8. Run end-to-end local test.

Medium priority:

1. Dockerfile backend.
2. Dockerfile worker.
3. docker-compose.
4. CSV report export.
5. Result dashboard.
6. Structured logging.
7. Health check endpoint.

After MVP:

1. ONNX/OpenVINO optimization.
2. Authentication.
3. Multi-camera or RTSP realtime.
4. Prometheus/Grafana monitoring.
5. Cloud production deployment.
6. Model versioning.
7. Object storage such as S3/GCS.

## MVP

Local web app via docker-compose:

```text
Upload video -> draw lane -> async processing -> progress -> output video -> statistics
```
