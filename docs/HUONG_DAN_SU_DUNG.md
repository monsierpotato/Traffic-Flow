# TrafficFlow — Hướng dẫn sử dụng và vận hành

TrafficFlow phân tích video giao thông bằng YOLO + ByteTrack, sau đó gán xe vào
từng lane và trả về video có overlay cùng thống kê. Project chạy native trên máy
local bằng Node.js, Python, Redis và MongoDB tùy chọn; không còn runtime container.

## Kiến trúc và luồng xử lý

```text
React/Vite (5173)
  → FastAPI (8000)
    → MongoDB hoặc local JSON fallback
    → Redis/Celery queue
      → Python worker + YOLO/ByteTrack + counting
        → local storage hoặc Cloudflare R2
          → Frontend poll status và hiển thị kết quả
```

Luồng upload:

```text
Upload → tạo preview → vẽ ROI/lane/counting line → lưu config
  → submit task → worker xử lý → callback progress → lấy result
```

Live stream dùng FFmpeg/OpenCV để lấy frame mới nhất, sau đó chạy cùng local
inference và trả frame MJPEG cùng metrics theo session.

## Yêu cầu

| Thành phần | Tối thiểu | Ghi chú |
|---|---:|---|
| Node.js | 20+ | Orchestrator và Vite |
| Python | 3.10+ | FastAPI, Celery, AI engine |
| FFmpeg + FFprobe | Có trong PATH | Preview, normalize và live ingest |
| Redis native | 6379 | Bắt buộc cho batch worker |
| MongoDB | Tùy chọn | Có local JSON fallback cho development |
| Model weights | Theo `AI_MODEL_PATH` | Cần cho local inference; có thể dùng remote fallback qua `AI_SERVING_URL`; không commit vào Git |
| NVIDIA CUDA | Tùy chọn | Dùng GPU nếu environment hỗ trợ |

## Khởi động local

```bash
cp .env.example .env
python3 -m venv .venv
npm run install:python
npm run install:frontend
npm run preflight
npm run dev
```

Mở:

- Frontend: `http://127.0.0.1:5173`
- API health: `http://127.0.0.1:8000/health`
- API readiness: `http://127.0.0.1:8000/ready`
- Swagger: `http://127.0.0.1:8000/docs`

`npm run dev` khởi động API, Vite và worker khi Redis, Celery và inference path
đã sẵn sàng. Nếu thiếu Redis, API/frontend vẫn khởi động nhưng worker báo
`BLOCKED`; submit batch sẽ trả lỗi rõ ràng thay vì tạo task pending giả. Local
model/dependency có thể bỏ qua khi `AI_SERVING_URL` được cấu hình để dùng remote
fallback.

Các process riêng:

```bash
npm run dev:api
npm run dev:frontend
npm run dev:worker
```

Kiểm tra dependency:

```bash
PYTHONPATH=src .venv/bin/python scripts/check_connections.py
```

## Cấu hình quan trọng

```env
AI_LOCAL=true
AI_SERVING_URL=
AI_MODEL_DIR=inference/models
AI_MODEL_PATH=yolov8n.pt
REDIS_URL=redis://127.0.0.1:6379/0
CALLBACK_HOST=http://127.0.0.1:8000
CALLBACK_TOKEN=
MONGODB_LOCAL_FALLBACK=true
LOCAL_DB_PATH=storage/local_db.json
```

Khi deploy public, đặt `CALLBACK_TOKEN` là một chuỗi ngẫu nhiên dài để chỉ
worker được phép ghi callback tiến độ.

R2 dùng local filesystem khi credentials còn là placeholder. Khi dùng MongoDB
Atlas hoặc R2 thật, chỉ khai báo secret trong `.env`, không đưa vào repository.

## Sử dụng frontend

1. Upload video hoặc resolve nguồn live.
2. Chờ preview rồi vẽ ROI, vùng lane, counting line và direction.
3. Validate geometry trước khi submit hoặc start live.
4. Theo dõi progress; khi task hoàn tất, mở video output và bảng thống kê.

Vehicle class mặc định gồm car, bus, truck và motorcycle. Kết quả được tính theo
counting event, lane, class và direction; frontend không tự sinh mock result khi
API lỗi.

## API chính

| Method | Path | Mục đích |
|---|---|---|
| POST | `/videos` | Upload video |
| GET | `/videos/{id}/preview` | Lấy preview |
| POST | `/tasks` | Submit lane config và process |
| GET | `/tasks/{id}` | Poll task status |
| GET | `/tasks/{id}/result` | Lấy kết quả |
| POST | `/live/resolve` | Resolve live source |
| POST | `/live/validate-config` | Validate geometry |
| POST | `/live/sessions` | Tạo live session |
| GET | `/live/sessions/{id}` | Lấy metrics |
| GET | `/live/sessions/{id}/frame` | Lấy frame đã annotate |

API v1 và schema chi tiết nằm trong [API_INTEGRATION.md](API_INTEGRATION.md),
[contracts](contracts/) và OpenAPI.

## Cấu trúc runtime

```text
src/api/       FastAPI app, routes, schemas và services
src/shared/    settings, database, storage client
src/worker/    Celery task, local inference, tracking, render và counting
src/tfengine/  AI/runtime engine dùng chung
frontend/      React + Vite
scripts/       preflight, native orchestrator và connection checks
inference/models/ local weights dùng chung cho serving và worker, không commit
storage/       uploads, previews, chunks và results local
```

## Xử lý lỗi thường gặp

| Hiện tượng | Cách kiểm tra |
|---|---|
| Preflight báo thiếu model | Kiểm tra `AI_MODEL_DIR`/`AI_MODEL_PATH`, tải weights vào `inference/models/` |
| Worker bị `BLOCKED` | Kiểm tra Redis 6379, Celery import và model import |
| Submit trả `503` | Queue chưa sẵn sàng; chạy Redis native rồi khởi động lại worker |
| MongoDB không kết nối | Dùng local fallback hoặc kiểm tra `MONGODB_URI` |
| Preview không có | Kiểm tra FFmpeg/FFprobe và quyền ghi `storage/` |
| Port đã được dùng | Kiểm tra process đang listen trước khi đổi port |

## Verification gates

```bash
npm run build
PYTHONPATH=src .venv/bin/python -m compileall -q src benchmark scripts
npm run test:frontend
npm run test:python
```

Build/import pass chưa thay thế cho real E2E. Batch E2E cần Redis, model weights,
FFmpeg và persistence tương ứng; live E2E cần thêm nguồn stream hợp lệ.
