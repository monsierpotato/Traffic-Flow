# TrafficFlow API integration

API hiện tại dùng local inference trong worker. Modal không còn là runtime
dependency của luồng chính.

## Service boundary

```text
React/Vite -> FastAPI (:8000) -> MongoDB hoặc local JSON fallback
                         -> Redis/Celery -> worker -> tfengine
                         -> local storage hoặc Cloudflare R2
```

## Endpoint chính

| Method | Path | Mục đích |
|---|---|---|
| `POST` | `/videos` | Upload tương thích với frontend |
| `GET` | `/videos/{id}/preview` | Preview frame |
| `POST` | `/tasks` | Lưu lane config và enqueue task |
| `GET` | `/tasks/{id}` | Poll trạng thái/progress |
| `GET` | `/tasks/{id}/result` | Lấy thống kê và output |
| `POST` | `/api/v1/upload/video` | Upload file đơn |
| `POST` | `/api/v1/upload/video/chunk` | Upload chunk |
| `POST` | `/api/v1/upload/video/chunk/{id}/complete` | Ghép và tạo task |
| `POST` | `/api/v1/tasks/process` | Enqueue task theo `video_id` |
| `GET` | `/api/v1/tasks/status/{id}` | Trạng thái task |
| `GET` | `/api/v1/tasks/result/{id}` | Kết quả task |
| `PUT` | `/api/v1/tasks/progress/{id}` | Callback nội bộ từ worker |

## Task state machine

```text
uploaded -> configured -> pending -> processing -> completed
                                      └─────────> failed
```

Task `pending`/`processing` không được enqueue trùng; task terminal không được
process lại. Frontend phải hiển thị lỗi API thay vì tự tạo mock result.

## Local configuration

Copy `.env.example` thành `.env`. Các biến quan trọng:

```env
AI_LOCAL=true
# Set this when using remote inference instead of local weights/runtime.
AI_SERVING_URL=
AI_MODEL_DIR=inference/models
AI_MODEL_PATH=yolov8n.pt
REDIS_URL=redis://127.0.0.1:6379/0
MONGODB_LOCAL_FALLBACK=true
CALLBACK_HOST=http://127.0.0.1:8000
CALLBACK_TOKEN=
```

For public deployments, set `CALLBACK_TOKEN` to a long random value so only the
worker can write task progress callbacks.

Đường chạy native dùng `CALLBACK_HOST=http://127.0.0.1:8000` và Redis native tại
`127.0.0.1:6379`. File `.env` phải cấu hình secret thật trước khi dùng
MongoDB Atlas/R2.

## Error contract

- `400`: request/state/config không hợp lệ.
- `404`: task/video/config không tồn tại.
- `409`: task đang được xử lý.
- `413`: file vượt giới hạn.
- `503`: Redis/worker hoặc persistence chưa sẵn sàng.

Chi tiết schema nằm trong [docs/contracts](contracts/) và OpenAPI tại
`http://localhost:8000/docs`.
