# TrafficFlow — User and Operations Guide

TrafficFlow analyzes traffic video with YOLO and ByteTrack, assigns vehicles to lanes, and returns an annotated video with statistics. The project runs natively on the local machine with Node.js, Python, Redis, and optional MongoDB; it has no container runtime.

## Architecture and Processing Flow

```text
React/Vite (8080)
  → FastAPI (8000)
    → MongoDB or local JSON fallback
    → Redis/Celery queue
      → Python worker + YOLO/ByteTrack + counting
        → local storage or Cloudflare R2
          → Frontend polls status and displays results
```

Upload flow:

```text
Upload → create preview → draw ROI/lane/counting line → save configuration
  → submit task → worker processes → progress callback → retrieve result
```

The live stream path uses FFmpeg/OpenCV to capture the newest frame, runs the same local inference, and returns an MJPEG frame with session metrics.

## Requirements

| Component | Minimum | Notes |
|---|---:|---|
| Node.js | 20+ | Orchestrator and Vite |
| Python | 3.10+ | FastAPI, Celery, and AI engine |
| FFmpeg + FFprobe | Available in `PATH` | Preview, normalization, and live ingest |
| Native Redis | 6379 | Required for the batch worker |
| MongoDB | Optional | Local JSON fallback is available for development |
| Model weights | Per `AI_MODEL_PATH` | Do not commit to Git |
| NVIDIA CUDA | Optional | Uses the GPU when supported by the environment |

## Start the Local Runtime

```bash
cp .env.example .env
python3 -m venv .venv
npm run install:python
npm run install:frontend
npm run preflight
npm run dev
```

Open:

- Frontend: `http://127.0.0.1:8080`
- API health: `http://127.0.0.1:8000/health`
- API readiness: `http://127.0.0.1:8000/ready`
- Swagger UI: `http://127.0.0.1:8000/docs`

`npm run dev` starts the API, Vite, and worker when Redis, Celery, and the model are ready. If the worker dependency, Redis, or model is missing, the API/frontend still starts but preflight reports `BLOCKED`; batch submission returns a clear error instead of creating a fake pending task.

Run individual processes:

```bash
npm run dev:api
npm run dev:frontend
npm run dev:worker
```

Check dependencies:

```bash
PYTHONPATH=src .venv/bin/python scripts/check_connections.py
```

## Important Configuration

```env
AI_LOCAL=true
AI_MODEL_DIR=inference/models
AI_MODEL_PATH=yolov8n.pt
REDIS_URL=redis://127.0.0.1:6379/0
CALLBACK_HOST=http://127.0.0.1:8000
MONGODB_LOCAL_FALLBACK=true
LOCAL_DB_PATH=storage/local_db.json
```

R2 uses the local filesystem while credentials are placeholders. When using MongoDB Atlas or real R2, store secrets only in `.env` and never commit them to the repository.

## Using the Frontend

1. Upload a video or resolve a live source.
2. Wait for the preview, then draw the ROI, lane zones, counting line, and direction.
3. Validate the geometry before submitting or starting a live session.
4. Monitor progress; when the task completes, open the output video and statistics dashboard.

The default vehicle classes are car, bus, truck, and motorcycle. Results are computed by counting event, lane, class, and direction; the frontend does not generate mock results when the API fails.

## Main API

| Method | Path | Purpose |
|---|---|---|
| POST | `/videos` | Upload a video |
| GET | `/videos/{id}/preview` | Retrieve a preview |
| POST | `/tasks` | Submit lane configuration and process a task |
| GET | `/tasks/{id}` | Poll task status |
| GET | `/tasks/{id}/result` | Retrieve the result |
| POST | `/live/resolve` | Resolve a live source |
| POST | `/live/validate-config` | Validate geometry |
| POST | `/live/sessions` | Create a live session |
| GET | `/live/sessions/{id}` | Retrieve metrics |
| GET | `/live/sessions/{id}/frame` | Retrieve an annotated frame |

API v1 and detailed schemas are documented in [API_INTEGRATION.md](API_INTEGRATION.md), [contracts](contracts/), and OpenAPI.

## Runtime Structure

```text
src/api/              FastAPI app, routes, schemas, and services
src/shared/           settings, database, and storage client
src/worker/           Celery task, local inference, tracking, rendering, and counting
src/tfengine/         shared AI/runtime engine
frontend/             React + Vite
scripts/              preflight, native orchestrator, and connection checks
inference/models/     shared local weights for serving and worker; not committed
storage/              local uploads, previews, chunks, and results
```

## Common Troubleshooting

| Symptom | Check |
|---|---|
| Preflight reports a missing model | Check `AI_MODEL_DIR`/`AI_MODEL_PATH` and place weights in `inference/models/` |
| Worker is `BLOCKED` | Check Redis on port 6379, Celery imports, and model imports |
| Submission returns `503` | The queue is not ready; start native Redis and restart the worker |
| MongoDB connection fails | Use the local fallback or check `MONGODB_URI` |
| No preview is available | Check FFmpeg/FFprobe and write permissions for `storage/` |
| Port is already in use | Inspect the listening process before changing the port |

## Verification Gates

```bash
npm run build
PYTHONPATH=src .venv/bin/python -m compileall -q src benchmark scripts
npm run test:frontend
npm run test:python
```

Passing build/import checks does not replace real E2E testing. Batch E2E requires Redis, model weights, FFmpeg, and the corresponding persistence; live E2E also requires a valid stream source.
