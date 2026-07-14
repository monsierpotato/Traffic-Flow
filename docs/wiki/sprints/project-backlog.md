# Project Backlog

## Summary

The MVP target is a local end-to-end system: upload video, draw lane with rectangular ROI support, process asynchronously, view progress, and inspect video/statistics output.

## Current State

- AI prototype and manual config generator exist.
- Runtime engine exists and CLI counting delegates to it; progress callback and API-ready result contract exist.
- ROI annotation contract, coordinate helper, tests, and OpenCV config generator integration exist.
- OpenCV config generator now supports rectangular annotation ROI for cropped drawing while preserving source-frame lane coordinates.
- Backend, worker, queue, database, and frontend integration are implemented and E2E verified.
- **Package collision resolved**: `backend/` (FastAPI) vs `ai-core/` (AI library). Local GPU inference via `LocalInferenceClient` (no Modal).
- **Docker optimized**: image 8GB→4.3GB, Celery `--concurrency=1`, worker-to-API via `http://api:8000`.
- **Video pipeline complete**: 1080p normalize, ROI crop + letterbox 640×640, coordinate remap.
- **COCO 4-class canonical**: car(2), motorcycle(3), bus(5), truck(7). OpenCV 4.10.x (not 5.0.0).
- **Benchmark system**: `run_benchmark.py` CLI, 8 presets, stage profiler, ground truth comparison.
- **UA-DETRAC integrated**: parser, converter, 3 sequences benchmarked. Key result: `optimized-a-yolov8n-fp16-640` = 6% count error, 24 FPS, 1.8× on RTX 5070 Ti.
- **Next 2026-07-11**: tune lane config per DETRAC video, add model comparison (n vs s), final portfolio report.

## Ownership

| Member | Role | Primary Scope |
|---|---|---|
| Member 1 | AI Pipeline Engineer | Runtime engine, progress callback, result contract, optional model optimization |
| Member 2 | Frontend Engineer | Upload UI, canvas lane drawing, coordinate scaling, progress/result dashboard |
| Member 3 | Backend Engineer | FastAPI, DB schema, upload/preview API, task/result APIs, retention, file validation |
| Member 4 | DevOps / Worker Engineer | Celery/Redis, worker, Docker, compose, timeouts, environment settings |
| Member 5 | Integration / QA / Release | End-to-end QA, coordinate alignment, queue stress, release checklist |

## Sprint Order

1. Stabilize `TrafficFlowEngine`, result contract, and progress callback.
2. Build FastAPI upload, preview-frame, task, status, and result APIs.
3. Build frontend upload, rectangular ROI drawing, lane drawing, progress polling, and charts.
4. Integrate Celery/Redis worker with the runtime engine.
5. Add Docker Compose and run local end-to-end QA.

## Sprint 0: Stabilize AI Foundation

Goal: make the existing AI engine clear, reusable, and callable from API/worker.

| Task | Owner | Status |
|---|---|---|
| Complete `TrafficFlowEngine.process_video(...)` | Member 1 | Done |
| Add `progress_callback` | Member 1 | Done |
| Create `result_sample.json` | Member 1 + 3 | Done |
| Create rectangular ROI annotation contract/helper | Member 1 + 2 + 3 | Done |
| Finalize full web lane config sample/contract | Member 1 + 2 + 3 | Done |
| Run short-video smoke test after refactor | Member 1 + 5 | Done; synthetic runtime smoke passes and real YOLO smoke completed on 5 frames |

## Sprint 1: Backend + Frontend Skeleton

Goal: upload video, extract preview frame, draw lane, and create task.

| Task | Owner | Status |
|---|---|---|
| FastAPI skeleton in `trafficflow/api/app.py` | Member 3 | Done |
| DB schema: Task, TrafficStatistic, LaneConfig | Member 3 | Done |
| Upload video API | Member 3 | Done |
| Preview frame API | Member 3 | Done |
| Frontend upload video | Member 2 | Done |
| Frontend canvas draw line/zone/direction | Member 2 | Done |
| Coordinate scaling | Member 2 + 5 | Done |

Remaining Sprint 1 items:
| Data retention (cron cleanup expired files) | Member 3 | Done |
| File size & format validation middleware | Member 3 | Done |
| Package refactor: rename `trafficflow/` → `backend/` | Member 3 | Done |
| Rename `Traffic-Flow_Frontend/` → `ai-core/` | Member 3 | Done |

## Sprint 2: Worker + AI Integration

Goal: enqueue task and process real video asynchronously.

| Task | Owner | Status |
|---|---|---|
| Redis/Celery setup | Member 4 | Done |
| `process_video_task(task_id)` | Member 4 | Done |
| Worker calls `TrafficFlowEngine` (currently uses Modal HTTP API instead) | Member 4 + 1 | Partial — implemented but bypasses AI core |
| Update task progress via callback | Member 4 + 3 | Done |
| Save result to DB/file | Member 3 + 4 | Done |
| Status/result APIs | Member 3 | Done |

Remaining Sprint 2 items:
| Refactor worker to import `TrafficFlowEngine` directly (currently uses Modal HTTP API — accepted decision to keep Modal) | Member 4 + 1 | Done (decision: keep Modal HTTP, counting runs locally) |
| Remove duplicate CountingState in backend | Member 4 | Done (verified — backend CountingState is unique and needed) |

## Sprint 3: End-To-End Local

Goal: local full flow works: upload, preview, draw lane, submit, worker processing, progress, output video, chart.

| Task | Owner | Status |
|---|---|---|
| Frontend polling progress | Member 2 | Todo |
| Result charts from real data | Member 2 | Todo |
| Output video URL | Member 3 + 4 | Todo |
| Coordinate alignment QA | Member 5 | Todo |
| Fix path/storage issues | Member 4 + 5 | Todo |

## Sprint 4: Docker Compose Production-Like

Goal: run the system through containers locally.

| Task | Owner | Status |
|---|---|---|
| Dockerfile backend | Member 4 | Todo |
| Dockerfile worker | Member 4 | Todo |
| docker-compose with frontend/backend/worker/redis/db | Member 4 | Todo |
| Shared storage volume | Member 4 | Todo |
| Smoke test docker-compose | Member 5 | Todo |

## Sprint 5: QA, Performance, Optional Deploy

Goal: harden the demo and deploy only if local is stable.

| Task | Owner | Status |
|---|---|---|
| Test 3-4 queued videos | Member 5 | Todo |
| Test long/short videos | Member 5 + 1 | Todo |
| Structured error logging | Member 3 + 4 | Todo |
| Cloud deployment | Member 4 + 5 | Later |
| Demo script/documentation | Member 5 | Todo |

## Additional Backend/Worker Tasks From Google Doc

- Member 3: data retention for old videos, keeping statistics.
- Member 3: file size and format validation, including 413 responses for oversized uploads.
- Member 4: AI exception handling and Celery timeouts.
- Member 4: `.env` and `pydantic-settings` for environment configuration.

## Links

- [[Production Architecture]]
- [[ROI Annotation]]
- [[Decision Log]]
- [[Deploy AI Traffic Work Plan Source]]

## Video Upload / Normalization Policy

- Upload routes normalize videos to a max 1080p / 30fps H.264 working copy before preview and worker processing.
- `STORE_ORIGINAL_VIDEO=false` is the default: R2 stores only the normalized working video at `uploads/{video_id}.mp4` and both `video_url` / `working_video_url` point to that asset.
- Set `STORE_ORIGINAL_VIDEO=true` only when archive/debug requires the original upload; then R2 stores `uploads/{video_id}.mp4` plus `uploads/{video_id}_1080p.mp4`.
- The frontend compatibility endpoint `POST /videos` uses the same normalization/upload service as the main upload endpoint, so it no longer bypasses 1080p normalization.

