# TrafficFlow — API Cập Nhật (2026-07-10)

## Kiến trúc mới: Local Docker + GPU

Hệ thống đã chuyển từ **Modal GPU inference** sang **local Docker với GPU acceleration**.

### Thay đổi lớn

| Thành phần | Trước (cũ) | Sau (mới) |
|-----------|-----------|----------|
| Inference | Modal GPU server (`tienpm205--trafficflow-inference-fastapi-app.modal.run`) | **Local YOLO** (CUDA GPU) |
| Deploy | `python -m api.main` + `celery worker` | **Docker Compose** (3 services) |
| Worker pool | `--pool=solo` | `--pool=prefork --concurrency=2` |
| Upload | Single HTTP POST | **Chunked upload** với resume |
| Docker image | `python:3.10-slim` (9.76GB) | `python:3.12-slim` + **torch CUDA** (18.1GB) |
| Model serving | `/v1/detect` via Modal | **`LocalInferenceClient`** (autodetect GPU/CPU) |

### Tại sao chuyển?

1. **`cv::gemm` crash**: OpenCV 5.0.0 trên Modal server crash với ONNX YOLO model — tất cả detection fail
2. **Độ trễ network**: Mỗi frame phải upload lên Modal → 3-5s latency mỗi request
3. **Chi phí**: GPU local RTX 5070 Ti (có sẵn) → nhanh hơn + không tốn Modal credit
4. **ROI crop**: Frame sau khi crop chỉ còn ~640px → không cần GPU server mạnh

---

## API mới

### Chunked Upload (mới)

```
POST /api/v1/upload/video/chunk
```
Fields: `upload_id`, `chunk_index`, `total_chunks`, `filename`, `file`

```
POST /api/v1/upload/video/chunk/{upload_id}/complete
```
Ghép tất cả chunks → upload R2 → tạo task document.

---

## Docker Compose

```yaml
services:
  redis:    # Message broker
  api:      # FastAPI + React (port 8000)
  worker:   # Celery + YOLO GPU (runtime: nvidia, prefork x2)
```

### Biến môi trường mới

```env
CALLBACK_HOST=http://api:8000    # Worker gọi callback qua internal Docker network
AI_LOCAL=true                     # Bắt buộc: dùng local YOLO thay Modal
```

---

## File đã thay đổi

| File | Thay đổi |
|------|----------|
| `Dockerfile` | Multi-stage: Node FE → Python 3.12 + torch CUDA |
| `docker-compose.yml` | GPU device reservation, prefork, CALLBACK_HOST |
| `.dockerignore` | Clean exclude patterns |
| `src/worker/pipeline/local_client.py` | **Mới** — YOLO local GPU/CPU |
| `src/worker/celery_app.py` | Switch `InferenceClient` → `LocalInferenceClient` khi `AI_LOCAL=true` |
| `src/api/routes/frontend_compat.py` | Fix: lưu lane_config, truyền BackgroundTasks |
| `src/api/routes/tasks.py` | Fix: CALLBACK_HOST, strip ObjectId, serializable config |
| `src/api/routes/upload.py` | **Mới**: chunked upload endpoints |
| `src/shared/config.py` | Default MAX_FILE_SIZE_MB=2048 |
| `.env` | AI_LOCAL=true, MAX_FILE_SIZE_MB=2048 |
| `docs/README.md` | Rewrite: kiến trúc mới |
| `docs/HUONG_DAN_SU_DUNG.md` | Rewrite: full guide |
| `docs/API_INTEGRATION.md` | Unchanged (Modal reference) |

---

## Performance

| Metric | CPU | GPU (RTX 5070 Ti) |
|--------|-----|-------------------|
| 10-frame test video | ~3s | **~0.5s** |
| 4K video (3300 frames, ROI crop) | ~25-50 phút | **~2-5 phút** |
| VRAM usage | N/A | <1GB (YOLOv8n) |
