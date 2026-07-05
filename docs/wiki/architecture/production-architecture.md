# Production Architecture

## Summary

TrafficFlow has a production-style system with backend API (`backend/`), background worker (Celery), queue (Redis), storage (Cloudflare R2 + local mock), observability, and a reusable AI runtime (`ai-core/`).

## Current State

- **Backend**: `src/api/` — FastAPI app, MongoDB, Celery client, R2 storage
- **Worker**: `src/worker/` — Celery worker with refactored **pipeline stages**:
  - `src/worker/pipeline/processor.py` — `FrameProcessor` (stabilize → crop → polygon mask → resize → JPEG encode)
  - `src/worker/pipeline/ai_client.py` — `InferenceClient` (Modal GPU `/v1/detect` session mgmt + ThreadPoolExecutor pipelining)
  - `src/worker/pipeline/tracker.py` — `LocalTracker` (8-state Kalman filter per track, IoU greedy matching, lost-track prediction, exposes `kalman_velocity`)
  - `src/worker/pipeline/renderer.py` — `FrameRenderer` (draw lanes + bboxes + track info overlay)
- **Counting**: `src/worker/services/counting_service.py` — `CountingState` driven by `kalman_velocity` from tracker; `DirectionFilter` uses `cos_sim >= 0.3` threshold
- **AI Engine**: `src/tfengine/` — installable Python library (`tfengine` package) with `TrafficFlowEngine` in `tfengine/runtime/engine.py`. Renamed from `ai-core/trafficflow/` to avoid name collision with the root project.
- **Inference Server**: `inference/` — Docker container for GPU inference (`/detect/raw` endpoint), imports `tfengine.core_ai`
- **Shared Infra**: `src/lib/` — `config.py`, `database.py`, `r2_client.py` shared between api and worker
- **Frontend**: `frontend/` — React + Vite app (moved from `ai-core/frontend/`)
- **Configs**: `configs/` — Lane configuration YAML/JSON files (moved from `ai-core/configs/`)
- **Database**: MongoDB Atlas (production), local (future SQLite for MVP)
- **Queue**: Celery + Redis (Redis Cloud)
- **Storage**: Cloudflare R2 with local filesystem fallback

## Pipeline Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│                      Celery Worker (celery_app.py)                  │
│                                                                     │
│  ┌────────────────┐    ┌──────────────┐    ┌──────────────────┐     │
│  │ FrameProcessor │───▶│ Inference    │───▶│ LocalTracker     │     │
│  │ (stabilize,    │    │ Client       │    │ (Kalman 8-state, │     │
│  │  crop, mask,   │    │ (Modal HTTP  │    │  IoU matching,   │     │
│  │  resize, JPEG) │    │  /v1/detect) │    │  lost prediction)│     │
│  └────────────────┘    └──────────────┘    └────────┬─────────┘     │
│                                                      │               │
│  ┌────────────────┐    ┌──────────────┐              │               │
│  │ FrameRenderer  │◀───│ CountingState│◀─────────────┘               │
│  │ (overlay:      │    │ (line-cross, │   kalman_velocity            │
│  │  lanes, bboxes,│    │  Direction   │                              │
│  │  track info)   │    │  Filter)     │                              │
│  └────────────────┘    └──────────────┘                              │
└─────────────────────────────────────────────────────────────────────┘
```

### Frame Processing Pipeline (per-frame)

Each frame goes through these stages in order:

1. **Camera stabilization** — phase-correlation against a reference frame; sub-pixel warp correction when shift > 0.3px
2. **ROI crop** — rectangular crop from `annotation_roi` config
3. **Polygon mask** — zero-out pixels outside the `roi_polygon` quadrilateral
4. **Resize** — scale longest side to `AI_RESIZE_DIM` (640px), maintaining aspect ratio
5. **JPEG encode** — quality 85 for transport to Modal GPU

### Inference & Tracking Pipeline (per frame_skip interval)

1. **Modal inference** — submit JPEG via HTTP POST to `/v1/detect`; runs YOLO + ByteTrack server-side
2. **Bbox rescale** — scale detections from AI resize space back to cropped-frame coordinates
3. **Local Kalman tracking** — `LocalTracker.update()` strips Modal's ByteTrack track IDs and re-tracks locally:
   - Kalman predict all existing tracks (8-state: cx,cy,w,h,vx,vy,vw,vh)
   - IoU greedy matching against new detections (threshold: `TRACK_MATCH_THRESHOLD` = 0.5)
   - Matched → Kalman correct with observed bbox
   - Unmatched detections → new tracks
   - Unmatched tracks → lost_frames++, predict forward with velocity
   - Expire tracks with `lost_frames > track_buffer` (default 30)
4. **Counting** — `CountingState.process_detections()` per lane:
   - Assign detection to best lane (bbox-polygon overlap area)
   - Check trajectory segment crosses the `counting_line`
   - Filter by `DirectionFilter.is_aligned(velocity)` using `cos_sim >= 0.3`
   - Count unique track IDs per lane + class

### Frame Rendering Pipeline (every frame)

- Draw lane `valid_zone` polygon (blue)
- Draw `counting_line` (red)
- Draw bboxes: green if inside any valid_zone, grey if outside
- Annotate with `class_name` + `track_id` + center dot

## Project Structure

```
TrafficFlow/
├── src/                          # Python source packages
│   ├── api/                      # FastAPI server (was backend/)
│   ├── worker/                   # Celery worker + pipeline (was backend/core/ + services/ + pipeline/)
│   ├── tfengine/                 # AI engine library (was ai-core/trafficflow/)
│   └── lib/                      # Shared infra (config, database, r2_client)
├── inference/                    # Docker GPU inference server (was server/)
├── frontend/                     # React + Vite app (was ai-core/frontend/)
├── configs/                      # Lane configuration files (was ai-core/configs/)
├── docs/                         # Wiki + user documentation
│   ├── wiki/                     # Development wiki (was ai-core/docs/wiki/)
│   ├── contracts/                # API contracts (was ai-core/docs/contracts/)
│   ├── README.md
│   ├── API_INTEGRATION.md
│   └── HUONG_DAN_SU_DUNG.md
├── scripts/                      # Dev scripts (run_server.bat, run_worker.bat)
├── tests/                        # All tests (from ai-core/tests/ + new)
├── data/                         # Raw video samples
├── models/                       # ML model files
├── storage/                      # Local file storage
├── scratch/                      # Ad-hoc test scripts
├── pyproject.toml                # Project config
└── .env                          # Environment variables
```

**PYTHONPATH** must include `src/` at runtime. The `.bat` scripts set this automatically.

## Refactoring History

Originally the Celery worker (`celery_app.py`) was a single 499-line file containing all logic. It was split into 4 isolated `pipeline/` modules, and the project was restructured from a flat `backend/` + `ai-core/` layout into the `src/`-based structure above.

| Module | Responsibility | Extracted From |
|---|---|---|
| `src/worker/pipeline/processor.py` | Frame stabilization, crop, mask, resize, JPEG encode | `celery_app.py` frame loop |
| `src/worker/pipeline/ai_client.py` | Modal HTTP session management + pipelining | `celery_app.py` session code |
| `src/worker/pipeline/tracker.py` | 8-state Kalman tracker with IoU matching | `celery_app.py` inline tracking + counting_service.py |
| `src/worker/pipeline/renderer.py` | Overlay drawing (lanes, bboxes, labels) | `celery_app.py` drawing code |

## Flow

```text
Frontend (frontend/)
  └── POST /api/v1/upload/video ──┐
  └── POST /api/v1/lanes/config   ├── API Server (src/api/)
  └── POST /api/v1/tasks/process  │   └── MongoDB ─── Task, LaneConfig, TrafficStatistic
  └── GET /api/v1/tasks/status    │   └── Redis ───── Celery broker
  └── GET /api/v1/tasks/result   ──┘   └── R2 ─────── Video storage
                                            │
                                     Celery Worker (src/worker/celery_app)
                                       ├── Download video from R2 (presigned URL)
                                       ├── Open with OpenCV, read frame-by-frame
                                       ├── FrameProcessor: stabilize → crop → mask → resize → JPEG
                                       ├── InferenceClient: HTTP POST to Modal GPU (async pipelined)
                                       ├── LocalTracker: Kalman predict → IoU match → correct/lost
                                       ├── CountingState: line-cross + direction filter
                                       ├── FrameRenderer: overlay annotation → write output video
                                       ├── Upload result video to R2
                                       └── PUT progress callback → API Server
```

## LocalTracker (Kalman Filter)

| Property | Value |
|---|---|
| State vector | 8D: cx, cy, w, h, vx, vy, vw, vh |
| Measurement | 4D: cx, cy, w, h (from bbox) |
| Process noise (pos) | 0.01 |
| Process noise (vel) | 1.0 |
| Measurement noise (pos) | 0.5 |
| Measurement noise (size) | 0.1 |
| Initial error cov (pos) | 1.0 |
| Initial error cov (vel) | 10.0 |
| Match threshold (IoU) | 0.5 (configurable via `TRACK_MATCH_THRESHOLD`) |
| Lost track buffer | 30 frames (configurable via `TRACK_BUFFER`) |
| Velocity convergence | 2-3 frames for vehicles at ~30px/frame |

## Decisions

- **Pipeline refactoring**: monolithic `celery_app.py` (499 lines) split into 4 single-responsibility `pipeline/` modules for testability and maintainability
- **Local Kalman tracking (approach B)**: worker runs `LocalTracker` instead of simple center-history velocity; provides smooth velocity and lost-track prediction up to `track_buffer` frames
- **Modal GPU HTTP API** is used for YOLO detection + ByteTrack; worker strips server track IDs and re-tracks locally
- **Counting logic** in `CountingState` with `DirectionFilter` (cosine similarity >= 0.3) instead of raw dot-product
- **ThreadPoolExecutor pipelining**: `InferenceClient.submit_frame()` runs HTTP POST in a background thread while caller prepares the next frame (frame_skip interval)
- **Package separation**: `backend/` = web API, `ai-core/` = reusable AI library

## Links

- [[Runtime Engine]]
- [[Project Backlog]]
- [[Decision Log]]
- [[Backend Refactor Plan]]
