# Native Local Development

This is the default TrafficFlow runtime path. Docker is not required.

## Components

- Node.js runs the orchestrator and Vite development server.
- Python `.venv` runs FastAPI and the Celery worker.
- MongoDB is optional; the API falls back to `LOCAL_DB_PATH` when MongoDB is unavailable.
- Native Redis is the broker for the batch worker.
- R2 uses a local filesystem mock while `.env` contains placeholder credentials.
- FFmpeg/FFprobe normalize and preview video.

## Start the Stack

```bash
cp .env.example .env
python3 -m venv .venv
npm run install:python
npm run install:frontend
npm run preflight
npm run dev
```

URLs:

- Frontend: `http://127.0.0.1:8080`
- API health: `http://127.0.0.1:8000/health`
- API readiness: `http://127.0.0.1:8000/ready`
- OpenAPI: `http://127.0.0.1:8000/docs`

The Vite proxy forwards `/api`, `/videos`, `/tasks`, `/live`, `/static`, `/health`, and `/ready` to the API. The frontend no longer falls back to mock data when the API fails; it displays the error clearly to the operator.

## Check Connections

```bash
PYTHONPATH=src .venv/bin/python scripts/check_connections.py
```

This command only reads MongoDB, Redis, and R2 configuration status. It does not create a test object in cloud storage.

## Dependency Status

`npm run preflight` checks Python, Celery, FFmpeg, FFprobe, and the model path. Model weights are not committed to the repository, so a missing model is reported as `BLOCKED`; the API/frontend can still run to check uploads, previews, and the database fallback.

If Redis is not running, `npm run dev` does not start the worker. Upload and preview still work; batch submission returns `503 Worker queue unavailable` instead of creating a fake pending task.

## Run Individual Processes

```bash
npm run dev:api
npm run dev:frontend
npm run dev:worker
```

Use `dev:worker` only after native Redis and model weights are ready.

Docker/Compose has been removed from the project. The local development and runtime path uses only the Node.js orchestrator, Python `.venv`, native Redis, and the services configured in `.env`.
