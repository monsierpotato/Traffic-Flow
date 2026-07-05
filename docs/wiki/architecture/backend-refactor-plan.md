# Backend Refactor Plan

## Status: Phase 1-2 Complete

The refactoring described below has been implemented:
- **Phase 1 (Package Restructure)**: Done. `backend/` split into `src/api/`, `src/worker/`, `src/lib/`; `ai-core/trafficflow/` renamed to `src/tfengine/`; `server/` moved to `inference/`.
- **Phase 2 (Worker → AI Core Direct Integration)**: Partially done. The Celery worker now imports `tfengine` directly (the renamed AI core). However, Modal HTTP API is still used for GPU inference (fallback until Azure VM is fixed).

## Summary

Refactor the backend application to resolve package name collision with the AI core,
eliminate empty stub directories, and align the implementation with the architecture
described in the wiki (direct `TrafficFlowEngine` integration instead of HTTP calls to Modal).

## Current Problems

### 1. Package name collision
- Root `trafficflow/` = backend application
- `Traffic-Flow_Frontend/trafficflow/` = AI core library
- Both share the `trafficflow` namespace → import conflicts
- Empty stubs in root `trafficflow/runtime/`, `core_ai/`, `counting/`, etc. shadow the real AI core

### 2. Worker bypasses AI core engine
- `celery_app.py` calls Modal GPU via HTTP API instead of importing `TrafficFlowEngine`
- Duplicate counting logic in `services/counting_service.py` while `Traffic-Flow_Frontend/trafficflow/counting/` has another implementation
- Violates the architecture described in `docs/wiki/ai-workflow/ai-core-integration.md`

### 3. Empty stub directories
10 directories in root `trafficflow/` contain only `__pycache__/`:
- `runtime/`, `core_ai/`, `counting/`, `geometry/`, `pipeline/`
- `worker/`, `queue/`, `storage/`, `observability/`, `cli/`

### 4. Task status validation gap
- `tasks.py:process_task` only blocks status `"uploaded"` but allows re-processing of `"completed"` or `"failed"` tasks

## Proposed Solution

### Phase 1: Extract backend to `backend/` package
Move root `trafficflow/` → `backend/` to resolve namespace collision:
- `backend/api/` — FastAPI routes
- `backend/core/` — MongoDB, Redis, Celery, R2 clients
- `backend/services/` — Business logic services
- `backend/schemas/` — Pydantic models
- `backend/middleware/` — File validation, etc.
- `backend/config.py` — Settings
- `backend/main.py` — Entry point

### Phase 2: Integrate AI core directly into worker
- Rewrite `backend/core/celery_app.py` to import `TrafficFlowEngine` from the AI core
- Remove duplicate `CountingState` from `backend/services/counting_service.py`
- Worker calls `TrafficFlowEngine.process_video()` instead of HTTP to Modal
- Remove AI_SERVING_URL dependency entirely

### Phase 3: Clean up empty stubs
- Remove empty directories from root `trafficflow/`
- Update `PYTHONPATH` references and run scripts

### Phase 4: Backlog tasks from Sprint 2
- Task status state machine (uploaded → configured → pending → processing → completed/failed)
- Data retention working with local R2 mock
- File size/format validation

## Task List

### Phase 1: Package Restructure
- [ ] P1.1: Rename `trafficflow/` → `backend/` (the backend application)
- [ ] P1.2: Update all imports in backend code to use `backend.*` prefix
- [ ] P1.3: Update `run_server.bat`, `run_worker.bat` to use new path
- [ ] P1.4: Update `trafficflow/main.py` entrypoint → `backend/main.py`
- [ ] P1.5: Verify all imports resolve correctly
- [ ] P1.6: Run full E2E test

### Phase 2: Worker → AI Core Direct Integration
- [ ] P2.1: Install AI core package in venv (`pip install -e Traffic-Flow_Frontend`)
- [ ] P2.2: Rewrite `celery_app.py` to use `TrafficFlowEngine.process_video()`
- [ ] P2.3: Remove duplicate `counting_service.py` logic
- [ ] P2.4: Wire progress_callback from engine to backend task progress API
- [ ] P2.5: Remove Modal HTTP API client code
- [ ] P2.6: Remove `AI_SERVING_URL` and `AI_FRAME_SKIP` from config
- [ ] P2.7: Test worker with real video processing locally

### Phase 3: Stub Cleanup
- [ ] P3.1: Remove all empty stub directories in root `trafficflow/`
- [ ] P3.2: Remove duplicate `__init__.py` files in stubs
- [ ] P3.3: Update `.gitignore` if needed

### Phase 4: Quality & Bug Fixes
- [ ] P4.1: Fix task status state machine — reject re-processing completed/failed tasks
- [ ] P4.2: Replace deprecated `HTTP_422_UNPROCESSABLE_ENTITY` → `HTTP_422_UNPROCESSABLE_CONTENT`
- [ ] P4.3: Add task status constants/enum to avoid magic strings
- [ ] P4.4: Add proper error handling when AI Serving is unreachable
- [ ] P4.5: Add unit tests for task state transitions

### Phase 5: Documentation & Wiki
- [ ] P5.1: Update `project-backlog.md` to reflect Sprint 1-2 completion
- [ ] P5.2: Update `production-architecture.md` to match current state
- [ ] P5.3: Document the new worker → AI core integration flow
- [ ] P5.4: Update `decision-log.md` with accepted refactor decisions

## Dependencies

- AI core package (`Traffic-Flow_Frontend/`) must be installable (`pip install -e .`)
- GPU drivers for local YOLO inference (optional — can still use Modal as fallback)
- Redis + MongoDB must be running for full E2E

## Open Questions

1. Keep Modal HTTP API as a fallback when GPU is not available locally?
2. Rename `Traffic-Flow_Frontend/` folder to `ai-core/` or similar?
3. Should the backend and AI core be separate repos eventually?

## Links
- [[Production Architecture]]
- [[AI Core Integration Guide]]
- [[Runtime Engine]]
- [[Project Backlog]]
- [[Decision Log]]
