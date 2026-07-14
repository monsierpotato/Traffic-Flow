# TrafficFlow — Hướng dẫn sử dụng & Triển khai

Hệ thống phân tích giao thông bằng video: phát hiện, tracking và đếm xe theo lane với YOLOv8 + ByteTrack, chạy hoàn toàn local qua Docker với GPU acceleration.

---

## Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────┐
│  Docker Compose (local)                              │
│                                                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────┐ │
│  │  Redis   │   │  API     │   │  Worker (Celery)  │ │
│  │  :6379   │◄─►│  :8000   │◄─►│  YOLO GPU (5070Ti)│ │
│  │ (broker) │   │ FastAPI  │   │  prefork x2       │ │
│  └──────────┘   │ React FE │   └──────────────────┘ │
│                 └──────────┘                         │
│                      │                               │
│                 ┌────┴────┐                          │
│                 │ MongoDB │  (Atlas cloud)            │
│                 │  Atlas  │                          │
│                 └─────────┘                          │
│                 ┌────┴────┐                          │
│                 │   R2    │  (Cloudflare storage)    │
│                 └─────────┘                          │
└─────────────────────────────────────────────────────┘
```

**Flow xử lý 1 video:**
```
Upload → Lưu R2 → Extract preview → User vẽ ROI+Lanes
  → Save config MongoDB → Submit task
    → Celery gửi worker → Worker download video
      → Stabilize → Crop ROI (4K→640px) → YOLO GPU detect
        → ByteTrack → Counting gate → Render overlay
          → Upload kết quả R2 → Callback API → Frontend poll
```

---

## Yêu cầu hệ thống

| Thành phần | Tối thiểu | Khuyến nghị |
|-----------|----------|-------------|
| Docker + Docker Compose | ✅ Bắt buộc | Latest |
| GPU NVIDIA + CUDA 12.4+ | Tùy chọn | RTX 3060+ (có sẵn RTX 5070 Ti) |
| RAM | 8GB | 16GB+ |
| Disk | 30GB | 50GB (cho models + Docker) |

> **Không cần cài Python, MongoDB, Redis** — tất cả chạy trong Docker container. MongoDB Atlas & Redis cloud đã cấu hình sẵn trong `.env`.

---

## Triển khai (Docker)

### Build & Start

```bash
cd C:\Users\ADMIN\OneDrive\Documents\_Project\TrafficFlow

# Build image (lần đầu ~10 phút)
docker compose build

# Start tất cả services
docker compose up -d
```

3 container sẽ chạy:
| Container | Vai trò | Port |
|-----------|---------|------|
| `trafficflow-redis-1` | Message broker cho Celery | 6379 (internal) |
| `trafficflow-api-1` | FastAPI + React frontend | **8000** |
| `trafficflow-worker-1` | Celery worker — YOLO GPU inference | – |

### Kiểm tra GPU hoạt động

```bash
docker compose exec worker python -c "import torch; print(torch.cuda.get_device_name(0))"
# → NVIDIA GeForce RTX 5070 Ti
```

### Dừng

```bash
docker compose down
```

---

## Truy cập

Sau khi start, mở trình duyệt:

| URL | Mô tả |
|-----|-------|
| http://localhost:8000 | **Frontend React** (chính) |
| http://localhost:8000/docs | Swagger API docs |
| http://localhost:8000/api/v1/dashboard/stats | Dashboard stats (JSON) |

---

## Sử dụng (Frontend)

### 1. Upload video
- Kéo thả hoặc chọn file `.mp4`
- Hỗ trợ chunked upload cho video lớn (tự động resume nếu mất kết nối)
- Hệ thống trích xuất frame preview tự động
- Max file size: 2048MB

### 2. Vẽ ROI (Region of Interest)
- Click để thêm bao nhiêu điểm ROI tùy ý quanh vùng đường cần giám sát
- Kéo từng điểm neo để tinh chỉnh polygon; có thể xoá điểm đang chọn hoặc reset
- Hệ thống crop theo bounding rectangle của polygon, sau đó mask phần ngoài polygon trước khi đưa vào AI
- Input cho AI là vùng ROI đã crop/mask/resize, không phải toàn bộ frame 4K

### 3. Vẽ Lanes
- Mỗi lane gồm:
  - **Zone** (4 điểm): vùng phát hiện xe
  - **Counting Line** (2 điểm): đường đếm xe cắt ngang
  - **Direction** (vector): hướng xe đi
  - **Class allowed**: car, bus, truck, motorcycle

### 4. Submit & Theo dõi
- Nhấn Submit → task vào Celery queue
- Progress bar cập nhật realtime (poll mỗi 2s)
- Kết quả: video có overlay + bảng thống kê từng lane

---

## Inference Engine

### Local GPU (hiện tại)

- Model: **YOLOv8n** (6.3MB) hoặc **YOLOv8s** (22MB)
- Engine: PyTorch 2.x + CUDA 12.4
- Device: `cuda:0` — NVIDIA RTX 5070 Ti (16GB VRAM)
- Pipeline: frame → ROI crop → resize 640px → YOLO detect → ByteTrack → Counting gate
- Tốc độ: ~0.02-0.1s/frame (GPU), ~1-2s/frame (CPU fallback)
- Frame skip: 2 (xử lý mỗi frame thứ 3, configurable trong `.env`)

### Local CPU (fallback)

Khi GPU không khả dụng, tự động fallback về CPU. Đặt `AI_LOCAL=true` trong `.env`.

---

## API Endpoints

### Frontend Compat Routes

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/videos` | Upload video |
| GET | `/videos/{id}/preview` | Lấy preview frame |
| POST | `/tasks` | Submit lane config + trigger process |
| GET | `/tasks/{id}` | Poll task status |
| GET | `/tasks/{id}/result` | Lấy kết quả |

### API v1

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/api/v1/upload/video` | Upload video (single) |
| POST | `/api/v1/upload/video/chunk` | Upload chunked |
| POST | `/api/v1/upload/video/chunk/{id}/complete` | Ghép chunks |
| POST | `/api/v1/lanes/config` | Lưu lane config |
| GET | `/api/v1/lanes/config/{id}` | Lấy lane config |
| POST | `/api/v1/tasks/process` | Trigger process |
| GET | `/api/v1/tasks/status/{id}` | Task status |
| GET | `/api/v1/tasks/result/{id}` | Task result |
| GET | `/api/v1/dashboard/stats` | Dashboard thống kê |

---

## Cấu hình (.env)

```env
# MongoDB Atlas
MONGODB_URI=mongodb+srv://...
MONGODB_DB_NAME=trafficflow

# Cloudflare R2
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=traffic-flow
R2_PUBLIC_URL=https://...r2.dev

# Redis cloud
REDIS_URL=redis://default:...@...redis.io:17295

# Callback (worker gọi API trong Docker)
CALLBACK_HOST=http://api:8000

# Inference
AI_LOCAL=true                    # Bắt buộc: dùng local YOLO
AI_FRAME_SKIP=2                  # Process mỗi frame thứ 3
AI_RESIZE_DIM=640                # Resize frame về 640px
AI_ENABLE_STABILIZATION=true     # Chống rung camera

# Upload
MAX_FILE_SIZE_MB=2048
RETENTION_DAYS=3

# Local tracker
TRACK_MATCH_THRESHOLD=0.5
TRACK_BUFFER=30
```

---

## Cấu trúc thư mục

```
TrafficFlow/
├── Dockerfile                    # Multi-stage: Node FE + Python CUDA
├── docker-compose.yml            # 3 services: redis, api, worker
├── .dockerignore
├── .env                          # Biến môi trường
│
├── src/
│   ├── api/
│   │   ├── app.py                # FastAPI app factory + lifespan
│   │   ├── main.py               # Entry point (uvicorn)
│   │   ├── middleware/
│   │   │   └── file_validator.py # Validate upload (size, type)
│   │   ├── routes/
│   │   │   ├── upload.py         # Upload + chunked upload
│   │   │   ├── lanes.py          # Lane config CRUD
│   │   │   ├── tasks.py          # Process, status, result
│   │   │   ├── dashboard.py      # Stats
│   │   │   └── frontend_compat.py# Routes cho React frontend
│   │   ├── schemas/              # Pydantic models
│   │   └── services/             # Video processing
│   ├── shared/
│   │   ├── config.py             # Settings từ .env
│   │   ├── database.py           # MongoDB async (Motor)
│   │   └── r2_client.py          # Cloudflare R2 storage
│   ├── worker/
│   │   ├── celery_app.py         # Celery task process_video
│   │   ├── pipeline/
│   │   │   ├── processor.py      # Stabilize → crop → resize
│   │   │   ├── local_client.py   # YOLO GPU/CPU inference
│   │   │   ├── tracker.py        # Kalman + IoU tracking
│   │   │   └── renderer.py       # Overlay drawing
│   │   └── services/
│   │       └── counting_service.py
│   └── tfengine/
│       └── core_ai/
│           └── detector.py       # YoloByteTrackDetector
│
├── models/
│   ├── yolov8n.pt                # 6.3MB (nano)
│   └── yolov8s.pt                # 22MB (small)
│
├── frontend/                     # React (Vite)
│   └── dist/                     # Production build
│
├── configs/                      # Config mẫu
│   └── danang/
│       └── cau_rong_manual.json  # 2 lanes, 4K
│
├── data/raw/danang/              # Video nguồn
├── storage/                      # Local previews/chunks
├── tests/                        # 137 unit tests
└── docs/                         # Tài liệu
```

---

## Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân | Fix |
|-----|------------|-----|
| Docker build fail | Thiếu Docker Desktop | Chạy Docker Desktop trước |
| `CUDA not available` | Chưa cài nvidia-container-toolkit | `winget install Nvidia.ContainerToolkit` |
| Upload timeout | Video quá lớn (>2GB) | Dùng chunked upload hoặc giảm `MAX_FILE_SIZE_MB` |
| Task stuck "pending" | Worker không kết nối Redis | Kiểm tra `docker compose ps` |
| Progress không cập nhật | Callback URL sai | Đảm bảo `CALLBACK_HOST=http://api:8000` |
| Preview không hiển thị | Thiếu `storage/previews/` | Tự động tạo khi start |

---

## Benchmark

| Cấu hình | 10-frame test | Video 4K (~3300 frames, ROI crop) |
|----------|--------------|-----------------------------------|
| CPU (YOLOv8n) | ~3s | ~25-50 phút |
| **GPU RTX 5070 Ti** (YOLOv8n) | **~0.5s** | **~2-5 phút** |
| GPU RTX 5070 Ti (YOLOv8s) | ~1s | ~5-8 phút |

