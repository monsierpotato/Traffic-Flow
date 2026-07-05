# TrafficFlow

Hệ thống đếm phương tiện giao thông sử dụng YOLOv8 + ByteTrack + Kalman Filter, với kiến trúc production gồm API server, Celery worker, và GPU inference.

## Cấu trúc thư mục

```
TrafficFlow/
├── src/
│   ├── api/          # FastAPI server (routes, schemas, middleware)
│   ├── worker/       # Celery worker + pipeline (processor, tracker, ai_client, renderer)
│   ├── tfengine/     # AI engine library (detector, geometry, counting, runtime)
│   └── lib/          # Shared utilities (config, database, r2_client)
├── inference/        # Docker GPU inference server (Modal / self-hosted)
├── frontend/         # React + Vite UI
├── configs/          # Lane configuration files
├── docs/             # User docs + development wiki
├── scripts/          # Dev/utility scripts
├── tests/            # Unit + integration tests
├── scratch/          # Ad-hoc test/debug scripts
├── data/             # Raw video samples (gitignored)
├── models/           # ML model weights (gitignored)
├── pyproject.toml
└── .env
```

## Yêu cầu

| Thành phần | Phiên bản | Ghi chú |
|-----------|-----------|---------|
| Python | 3.10+ | |
| Redis | 6.0+ | Dùng Redis Cloud, có sẵn trong .env |
| MongoDB | 5.0+ | Dùng MongoDB Atlas, có sẵn trong .env |
| Node.js | 18+ | Chỉ cần khi build frontend |

## Cài đặt

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

Copy `.env` từ template hoặc file có sẵn, đảm bảo các biến `MONGODB_URI`, `REDIS_URL`, `AI_SERVING_URL`.

## Chạy

### API Server

```bash
python -m src.api.main
# Mặc định: http://localhost:8000
```

### Celery Worker

```bash
celery -A src.worker.celery_app worker --loglevel info --concurrency 1
```

### CLI counting (chạy local không cần API)

```bash
python -m src.tfengine.cli.run_counting ^
  --video "data\raw\video.mp4" ^
  --config configs\camera\config.json ^
  --model models\yolov8n.pt ^
  --output-video outputs\result.mp4
```

## Pipeline kiến trúc

```
Upload video → API Server → Celery task → Redis → Worker
                                                    │
                          FrameProcessor ←───────────┘ (stabilize → crop → mask → resize → JPEG)
                               │
                          InferenceClient ───→ Modal GPU /detect
                               │
                          LocalTracker (Kalman 8-state → IoU match → correct/lost)
                               │
                          CountingState (line-cross + DirectionFilter)
                               │
                          FrameRenderer (overlay → output video)
                               │
                          Upload R2 + callback API
```

## Dịch vụ cloud

| Dịch vụ | URL | Mục đích |
|---------|-----|----------|
| Modal GPU | `https://tienpm205--trafficflow-inference-fastapi-app.modal.run` | YOLO detection + ByteTrack |
| MongoDB Atlas | Atlas cluster | Lưu task, config, thống kê |
| Redis Cloud | Redis instance | Celery broker |
| Cloudflare R2 | R2 bucket | Lưu video gốc + kết quả |

## Tài liệu thêm

- `docs/HUONG_DAN_SU_DUNG.md` — Hướng dẫn chi tiết
- `docs/API_INTEGRATION.md` — API endpoints
- `docs/wiki/` — Development wiki, decision log, architecture
