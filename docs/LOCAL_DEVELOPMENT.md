# Native local development

Đây là đường chạy mặc định hiện tại của TrafficFlow. Không cần Docker.

## Thành phần

- Node.js chạy orchestrator và Vite dev server.
- Python `.venv` chạy FastAPI và Celery worker.
- MongoDB tùy chọn; API tự fallback sang `LOCAL_DB_PATH` khi MongoDB không khả dụng.
- Redis native là broker cho batch worker.
- R2 dùng local filesystem mock khi `.env` còn placeholder credentials.
- FFmpeg/FFprobe xử lý normalize và preview video.

## Khởi động

```bash
cp .env.example .env
python3 -m venv .venv
npm run install:python
npm run install:frontend
npm run preflight
npm run dev
```

URLs:

- Frontend: `http://127.0.0.1:5173`
- API health: `http://127.0.0.1:8000/health`
- API readiness: `http://127.0.0.1:8000/ready`
- OpenAPI: `http://127.0.0.1:8000/docs`

Vite proxy chuyển `/api`, `/videos`, `/tasks`, `/live`, `/static`, `/health` và `/ready` sang API. Frontend không còn fallback sang dữ liệu mock khi API lỗi; lỗi được hiển thị rõ cho operator.

## Kiểm tra kết nối

```bash
PYTHONPATH=src .venv/bin/python scripts/check_connections.py
```

Lệnh này chỉ đọc trạng thái MongoDB, Redis và R2 config; không tạo test object trên cloud storage.

## Trạng thái phụ thuộc

`npm run preflight` kiểm tra Python, Celery, FFmpeg, FFprobe và model path. Model weights không commit trong repo nên thiếu model sẽ hiện `BLOCKED`; API/frontend vẫn có thể chạy để kiểm tra upload, preview và database fallback.

Nếu Redis không chạy, `npm run dev` không khởi động worker. Upload/preview vẫn hoạt động; submit batch trả `503 Worker queue unavailable` thay vì tạo task pending giả.

## Các lệnh riêng

```bash
npm run dev:api
npm run dev:frontend
npm run dev:worker
```

`dev:worker` chỉ dùng sau khi Redis native và model weights đã sẵn sàng.

Docker/Compose đã được loại khỏi project. Luồng phát triển và chạy local chỉ dùng
Node.js orchestrator, Python `.venv`, Redis native và các dịch vụ phụ thuộc được
cấu hình trong `.env`.
