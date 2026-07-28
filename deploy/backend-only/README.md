# Backend-only deployment

The pilot deployment uses separate API and worker images. Build both from the
repository root:

```bash
docker build -f deploy/backend-only/Dockerfile.api -t trafficflow-api:pilot .
docker build -f deploy/backend-only/Dockerfile.worker -t trafficflow-worker:pilot .
```

For a repeatable two-container pilot, copy `deploy/backend-only/.env.example`
to `deploy/backend-only/.env`, replace every placeholder, then run:

```bash
docker compose -f deploy/backend-only/docker-compose.yml up -d --build
docker compose -f deploy/backend-only/docker-compose.yml ps
```

The Compose profile expects managed MongoDB, Redis, object storage, and the
external model service. It only manages the API and worker containers.

Run them with the same `.env` and secret mounts. Do not bake `.env`, R2 keys,
MongoDB credentials, Redis credentials, or model-serving tokens into images.

This profile deploys the FastAPI API, Celery orchestration, video I/O, lane
geometry, tracking/counting logic, and storage integration. It does not deploy
model weights and does not install the GPU/Ultralytics dependency group.

The worker sends each frame to the external model service configured by
`AI_SERVING_URL`. Set `AI_LOCAL=false` in the server `.env`; otherwise the
worker will try to initialize a local model.

## Files to deploy

Copy the repository source needed by the API and worker, excluding local model
weights, frontend build artifacts, benchmark assets, and test/demo data. The
source tree must retain `src/`, `pyproject.toml`, `package.json`, and the
runtime configuration files.

On the server, from the project directory:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[api,worker]"
sudo apt-get update
sudo apt-get install -y ffmpeg
```

Copy this file to `.env`, replace every placeholder, and create the storage
directory configured by `STORAGE_DIR`.

Before the first production start, take a MongoDB backup and run the index
migration in dry-run mode. Apply it only after reviewing duplicate groups:

```bash
PYTHONPATH=src .venv/bin/python scripts/migrate_indexes.py
PYTHONPATH=src .venv/bin/python scripts/migrate_indexes.py --apply
```

## Process contract

```text
Frontend -> FastAPI :8000 -> MongoDB
                    -> Redis/Celery -> worker
                                      -> external AI_SERVING_URL
                                      -> R2 result storage
```

The worker must consume the same `CELERY_QUEUE_NAME` that the API uses. The
external model service must expose the existing HTTP contract:

```text
POST   {AI_SERVING_URL}/v1/session       -> {"session_id": "..."}
POST   {AI_SERVING_URL}/v1/detect        -> {"detections": [...]}
DELETE {AI_SERVING_URL}/v1/session/{id}
```

## Start

```bash
PYTHONPATH=src .venv/bin/python -m uvicorn api.app:create_app --factory --host 0.0.0.0 --port 8000
PYTHONPATH=src .venv/bin/celery -A worker.celery_app worker --pool=solo --concurrency=1 -Q "${CELERY_QUEUE_NAME:-trafficflow_queue}" --loglevel=info
```

Run the worker as a separate service/process. Do not run `scripts/preflight.mjs`
as a deployment gate because it intentionally checks for local model weights;
use the backend-only checks below instead.

## Smoke checks after deployment

```bash
curl -fsS http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready
PYTHONPATH=src .venv/bin/python - <<'PY'
from shared.config import settings
from api.app import create_app

assert settings.AI_LOCAL is False
paths = create_app().openapi()["paths"]
for method, path in [
    ("post", "/videos"),
    ("post", "/tasks"),
    ("get", "/tasks/{task_id}"),
    ("get", "/tasks/{task_id}/result"),
    ("post", "/live/resolve"),
    ("post", "/live/sessions"),
]:
    assert method in paths[path], (method, path)
print("backend-only contract: PASS")
PY
```

A real upload-to-result check additionally requires reachable MongoDB, Redis,
R2, a valid video, and a reachable external model service. The expected state
sequence is `uploaded -> configured -> pending -> processing -> completed`.
