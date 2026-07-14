# TrafficFlow

Hệ thống phân tích giao thông bằng video: phát hiện, tracking và đếm xe theo lane.  
Stack: **FastAPI + Celery + YOLOv8 + ByteTrack + React** — tất cả chạy qua **Docker + GPU local**.

---

## Quick Start (Docker)

```bash
cd C:\Users\ADMIN\OneDrive\Documents\_Project\TrafficFlow
docker compose up -d
# Mở http://localhost:8000
```

3 containers: **api** (FastAPI + React), **worker** (YOLO GPU), **redis** (broker).

Không cần cài Python, MongoDB, Redis riêng — tất cả trong Docker + cloud services.

---

## Tài liệu

| File | Nội dung |
|------|----------|
| [HUONG_DAN_SU_DUNG.md](./HUONG_DAN_SU_DUNG.md) | Hướng dẫn chi tiết: deploy, sử dụng, API, cấu trúc |
| [API_INTEGRATION.md](./API_INTEGRATION.md) | API integration guide (Modal inference cũ) |
| [traffic_flow.md](./traffic_flow.md) | Thiết kế hệ thống ban đầu |

---

## Cấu trúc thư mục chính

```
src/
├── api/             # FastAPI server + routes
├── shared/          # Config, database, R2 storage
├── worker/          # Celery worker + pipeline (YOLO, tracker, renderer)
└── tfengine/        # Core AI: YoloByteTrackDetector

models/              # YOLO weights (yolov8n.pt, yolov8s.pt)
frontend/            # React app (Vite)
configs/             # Config mẫu (Cầu Rồng, ...)
tests/               # 137 unit tests
```

---

## Inference

- **GPU**: NVIDIA RTX 5070 Ti (CUDA 12.4) — ~0.02-0.1s/frame
- **CPU fallback**: tự động nếu không có GPU
- **Model**: YOLOv8n (6.3MB) hoặc YOLOv8s (22MB)
- **Pipeline**: Frame → stabilize → polygon ROI crop/mask → resize 640px → YOLO → ByteTrack → counting gate

## Benchmark (UA-DETRAC + RTX 5070 Ti)

| Preset | Imgsz | Half | FPS | Real-time | Count Err | VRAM |
|--------|-------|------|-----|-----------|-----------|------|
| optimized-a | 640 | FP16 | 24 | 1.8× | **6.06%** | 3.4 GB |
| optimized-b | 512 | FP16 | 29 | 2.4× | 15.15% | 3.4 GB |
| optimized-c | 416 | FP16 | 30 | 2.4× | 21.21% | 3.4 GB |
| baseline | 640 | FP32 | 24 | 1.9× | 6.06% | 3.6 GB |

**Sweet spot**: `optimized-a-yolov8n-fp16-640` — 6% error, 24 FPS, 1.8× real-time.
Ground truth: UA-DETRAC 3 sequences (MVI_20011/20012/20035, 2,400 frames total).
Full matrix: 12 runs × 3 videos × 4 presets → `benchmark/reports/benchmark_report.md`.


