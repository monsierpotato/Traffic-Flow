# TrafficFlow

TrafficFlow is a vehicle-counting system for uploaded videos and live traffic streams. It combines FastAPI, Celery, Redis, local GPU inference, YOLO, Kalman tracking, lane geometry, and a React frontend into one workflow for traffic monitoring.

The current stable live baseline is YouTube/HLS streaming at 15 FPS with `models/yolo11m.pt`, ROI cropping, realtime FFmpeg pacing, and low-latency latest-frame scheduling.

## What This Project Does

- Upload a video, configure ROI/lane/counting lines, and process it through a Celery worker.
- Resolve YouTube/HLS/RTSP/MJPEG/direct video sources, annotate a preview frame, and run live counting.
- Render annotated output with lanes, counting lines, tracked vehicles, and live metrics.
- Persist task metadata in MongoDB Atlas when available, with local JSON fallback for development.
- Store video artifacts through Cloudflare R2 in production-style flows.

## Runtime Shape

```text
Frontend
  -> FastAPI api
       -> upload/batch task -> Redis -> Celery worker -> result artifacts
       -> live session      -> FFmpeg reader -> local YOLO -> tracker -> MJPEG/status
```

Important runtime split:

- Uploaded videos are processed by the Celery `worker`.
- Live YouTube/HLS inference runs inside the FastAPI `api` process.
- Both `api` and `worker` need NVIDIA runtime access when using local GPU inference.

## Repository Layout

```text
TrafficFlow/
├── src/
│   ├── api/          # FastAPI app, routes, live sessions, upload/task APIs
│   ├── shared/       # Shared config, database, storage clients
│   ├── worker/       # Celery worker and counting pipeline
│   └── tfengine/     # Reusable AI/counting/geometry engine
├── frontend/         # React + Vite UI
├── configs/          # Lane/ROI configuration examples
├── docs/             # User docs, contracts, and development wiki
├── models/           # Model weights, not committed
├── tests/            # Unit/integration tests
├── docker-compose.yml
└── Dockerfile
```

## Requirements

| Component | Recommended | Notes |
| --- | --- | --- |
| Docker Desktop | Recent version | Easiest path for API, worker, Redis, frontend build |
| NVIDIA driver + container toolkit | Required for local GPU | Needed by both `api` and `worker` services |
| Python | 3.10+ local, 3.12 in Docker | Local scripts/tests only |
| Node.js | 18+ | Frontend build and YouTube JS challenge support |
| Redis | Docker service by default | Celery broker |
| MongoDB Atlas | Optional for local dev | Local JSON fallback is available |
| FFmpeg/ffprobe | Included in Docker | Required for live HLS ingest |

Model weights are expected under `models/`. The stable live setup uses:

```text
models/yolo11m.pt
```

## Docker GPU Quick Start

From the project root:

```bash
docker compose up -d --build --force-recreate
docker compose logs -f api
```

Open the app:

```text
http://localhost:8000
```

Check live sessions:

```bash
curl http://localhost:8000/live/sessions
```

Check GPU visibility:

```bash
docker compose exec api nvidia-smi
docker compose exec worker nvidia-smi
```

If you only changed API/live code and do not want to restart the upload worker:

```bash
docker compose up -d --build --force-recreate api
```

## Stable Live Baseline

Keep these values when you want the known-good YouTube/HLS 15 FPS setup:

```env
AI_MODEL_PATH=models/yolo11m.pt
AI_CLASS_IDS=2,3,5,7
AI_IMGSZ=640
AI_CONFIDENCE=0.4
AI_IOU=0.45
AI_MAX_DET=100
AI_FRAME_SKIP=1

ROI_MODE=crop_rect
OUTPUT_FRAME_MODE=roi

LIVE_FFMPEG_OUTPUT_FPS=15
LIVE_FFMPEG_REALTIME_PACING=true
LIVE_FRAME_QUEUE_SIZE=1
LIVE_MAX_FRAME_AGE_SECONDS=0.25

LIVE_TRACK_MIN_HITS=3
LIVE_TRACK_MAX_LOST_SECONDS=0.7
LIVE_TRACK_RESET_GAP_SECONDS=1.0

TRACK_BUFFER=8
TRACK_MATCH_THRESHOLD=0.3
TRACK_FILTER_ZONE_PADDING_PX=12
RENDER_DEBUG=false
RENDER_SHOW_LOST=false
RENDER_SHOW_OUT_OF_ZONE=false
```

Validated result for this baseline:

- `fps`: about `14.97-15.05`
- `frame_interarrival_ms`: about `66.7`
- `frame_age_ms`: about `0.7-1.3`
- `frames_dropped`: `0`
- `infer_wall_ms`: usually `9-18`
- `lost_tracks`: `0`
- `last_error`: `null`

Avoid reverting this baseline to older debug settings such as:

```env
AI_IMGSZ=960
ROI_MODE=full_frame
```

Those settings were useful during model experiments, but they are not the stable live configuration.

## YouTube/HLS Live Workflow

1. Open the frontend at `http://localhost:8000`.
2. Enter a YouTube live URL, HLS URL, RTSP URL, MJPEG URL, or direct video URL.
3. Resolve the source and capture a preview frame.
4. Draw/select the processing ROI, lane polygons, counting lines, and direction vectors.
5. Start the live session.
6. Monitor `/live/sessions` for FPS, frame age, inference wall time, tracks, and errors.

For YouTube sources, Docker mounts browser cookies into the API container:

```yaml
C:/Users/ADMIN/Downloads/cookies.txt:/run/secrets/youtube_cookies.txt:ro
```

The resolver uses `yt-dlp`, Node.js, and remote JS components for YouTube challenge handling.

## Uploaded Video Workflow

1. Upload a video through the frontend.
2. Configure ROI/lane geometry.
3. Submit processing.
4. The API enqueues a Celery task into Redis.
5. The worker runs frame processing, detection, tracking, counting, rendering, and artifact upload.
6. The frontend polls task status and shows the result.

## Local Development

Create a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[api,worker,gpu,dev]"
```

Run the API locally:

```powershell
$env:PYTHONPATH="src"
python -m uvicorn api.app:create_app --factory --host 0.0.0.0 --port 8000
```

Run a worker locally:

```powershell
$env:PYTHONPATH="src"
celery -A worker.celery_app worker --loglevel info --concurrency 1
```

Run tests:

```powershell
python -m pytest tests -q
```

## Useful Commands

Inspect active live sessions:

```bash
curl http://localhost:8000/live/sessions
```

Follow live-related API logs:

```powershell
docker compose logs --tail=200 api | Select-String -Pattern "Live source opened|Live inference ready|Live session tick|Live session failed"
```

Verify current API environment:

```bash
docker compose exec api sh -lc "env | sort | grep -E 'AI_MODEL_PATH|AI_IMGSZ|ROI_MODE|LIVE_FFMPEG|LIVE_TRACK|RENDER_DEBUG|TRACK_'"
```

## Troubleshooting

- Live FPS is around 15 and `loop_idle_ms` is high: this is expected when `LIVE_FFMPEG_OUTPUT_FPS=15`; the loop is waiting for the next paced frame.
- `frame_age_ms` grows above 250 ms: the live loop is accumulating latency; check FFmpeg pacing and stale-frame dropping.
- `infer_wall_ms` jumps to hundreds of milliseconds: check CUDA contention, model warmup, or another process using the GPU.
- First live inference is slow: model warmup may still be needed before marking a session as running.
- MongoDB Atlas SSL/TLS fails locally: the API can fall back to `storage/local_db.json` when fallback is enabled.
- Geometry warning about `geometry_space`: frontend should send `geometry_space: "crop_local"` for crop-local ROI/lane configs.

## Documentation

- `docs/HUONG_DAN_SU_DUNG.md` - user guide
- `docs/API_INTEGRATION.md` - API integration notes
- `docs/contracts/` - request/response and config contracts
- `docs/wiki/` - architecture, decision log, runtime notes, and live optimization history
- `docs/wiki/ai-workflow/gpu-docker-live-optimization.md` - live GPU/HLS optimization baseline
