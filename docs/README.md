# TrafficFlow Serving

Model serving service for vehicle detection and tracking using YOLOv8 + ByteTrack. Exposes REST API để nhận frame ảnh, trả về bounding box kèm track ID.

---

## Cấu trúc thư mục

```
serving/
├── src/                          # Source code
│   ├── __init__.py
│   ├── main.py                   # FastAPI app factory + entrypoint
│   ├── config.py                 # Cấu hình từ biến môi trường
│   ├── schemas.py                # Pydantic request/response models
│   ├── engine.py                 # Core: detector + session management
│   ├── router.py                 # API routes
│   └── modal_app.py              # Modal deployment entry
├── model/
│   └── yolov8n.pt                # YOLOv8 nano weights (6.3 MB)
├── Dockerfile                    # Docker image build
├── requirements.txt              # Python dependencies
├── .env.example                  # Template config
├── .gitignore
└── README.md
```

---

## Cách từng file hoạt động

### `src/config.py` — Cấu hình

```python
class Settings(BaseSettings):
    model_path: str = "model/yolov8n.pt"
    classes: list[str] = ["car", "bus", "truck", "motorcycle", "motorbike"]
    confidence: float = 0.25
    device: str | None = None
    ttl: float = 600.0
    max_sessions: int = 32
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
```

Dùng `pydantic-settings`, đọc từ biến môi trường prefix `TRAFFICFLOW_` hoặc file `.env`. Khi deploy lên Modal, có thể set env qua `modal secret`.

Ví dụ:
```bash
export TRAFFICFLOW_CONFIDENCE=0.5
export TRAFFICFLOW_DEVICE="cuda:0"
```

---

### `src/engine.py` — Core logic

Ba class chính:

**`Detection`** — dataclass frozen, chứa kết quả detect của 1 object:
```python
@dataclass(frozen=True)
class Detection:
    track_id: int
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]
```

**`YoloByteTrackDetector`** — load YOLO model + chạy inference:
- `__init__`: lazy import `ultralytics.YOLO`, load weights từ `model_path`
- `detect_and_track(frame)` → `List[Detection]`:
  1. Gọi `self.model.track()` với `bytetrack.yaml` và `persist=True`
  2. Parse kết quả: lấy `xyxy`, `track_id`, `class_id`, `confidence`
  3. Lọc theo `self.classes` (chỉ giữ các class xe cộ)
  4. Trả về list `Detection`

ByteTrack hoạt động bằng cách gán `track_id` duy nhất cho mỗi object, tracking xuyên frame nhờ `persist=True`. Mỗi session duy trì 1 tracker riêng.

**`TrackSession`** — 1 session tracking:
- Khởi tạo `YoloByteTrackDetector` riêng
- `last_access` = timestamp, dùng để evict session cũ

**`SessionStore`** — quản lý nhiều session:
- `get_or_create(session_id, confidence)`: tạo mới hoặc lấy session cũ
- `remove(session_id)`: xoá session
- `_evict_stale()`: xoá session quá `ttl` giây không hoạt động
- Giới hạn `max_sessions`, tự động evict khi đầy

Flow:
```
request → store.get_or_create(sid) → TrackSession → YoloByteTrackDetector → model.track() → List[Detection]
```

---

### `src/schemas.py` — API models

```python
class DetectionOut(BaseModel):     # output 1 detection
    track_id: int
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]

class DetectResponse(BaseModel):   # response POST /detect
    session_id: str
    detections: list[DetectionOut]

class SessionCreateResponse(BaseModel):  # response POST /session
    session_id: str
```

---

### `src/router.py` — API routes

Sử dụng `APIRouter` mount tại prefix `/v1`.

**`GET /v1/health`**
```json
{ "status": "ok" }
```

**`POST /v1/session`** — Tạo tracking session mới
```json
{ "session_id": "a1b2c3d4e5f6g7h8" }
```

**`DELETE /v1/session/{session_id}`** — Xoá session

**`POST /v1/detect`** — Detect object trên 1 frame

Request: `multipart/form-data`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `image` | file | ✅ | Ảnh frame (JPEG/PNG) |
| `session_id` | string | ❌ | Track xuyên frame, để trống tạo mới |
| `confidence` | float | ❌ | Override threshold cho request này |

Response:
```json
{
  "session_id": "a1b2c3d4e5f6g7h8",
  "detections": [
    {
      "track_id": 1,
      "class_id": 2,
      "class_name": "car",
      "confidence": 0.93,
      "bbox_xyxy": [100.5, 200.3, 250.1, 350.7]
    }
  ]
}
```

Dependency injection qua `Depends(get_store)` — lấy `SessionStore` từ `request.app.state.store`, được khởi tạo trong lifespan.

---

### `src/main.py` — App factory

```python
def create_app(settings: Settings) -> FastAPI:
```

Làm những việc sau:
1. **Lifespan**: khởi tạo `SessionStore` khi app start, clear khi shutdown
2. **CORS middleware**: cho phép tất cả origin (để frontend bên ngoài gọi được)
3. **Logging middleware**: log method + path mỗi request
4. **Router**: mount `router.py` vào prefix `/v1`
5. **Global error handler**: catch all exception, trả về 500

`main()` function cho phép chạy bằng `python -m src.main` với CLI args.

---

### `src/modal_app.py` — Modal deployment

```python
image = (
    modal.Image.from_registry("pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime")
    .apt_install("libgl1-mesa-glx", "libglib2.0-0")
    .pip_install_from_file("requirements.txt")
    .copy_local_dir(".", "/app")
)

@app.cls(gpu="any", container_idle_timeout=300, allow_concurrent_inputs=10)
class Inference:
    @modal.enter()
    def setup(self):
        settings = Settings()
        self.fastapi_app = create_app(settings)

    @modal.asgi_app()
    def api(self):
        return self.fastapi_app
```

- Dùng base image `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime`
- Copy toàn bộ serving/ vào `/app` trong container
- `PYTHONPATH=/app` (set trong Dockerfile, Modal cần set riêng)
- `container_idle_timeout=300s`: giữ container warm 5 phút sau request cuối
- `allow_concurrent_inputs=10`: xử lý 10 request đồng thời / container
- `gpu="any"`: Modal tự chọn GPU (A10G, L4, T4)
- Model path: `model/yolov8n.pt` (relative, resolve từ `/app/model/yolov8n.pt`)

---

### `Dockerfile` — Docker build

```dockerfile
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV PYTHONPATH=/app
ENTRYPOINT ["python", "-m", "src.main"]
```

Build context là thư mục `serving/`. Kết quả là 1 image tự chứa:
- Python dependencies
- Source code (`/app/src/`)
- Model weights (`/app/model/yolov8n.pt`)

```bash
docker build -t trafficflow:latest .
docker run -p 8000:8000 trafficflow:latest
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/health` | Health check |
| POST | `/v1/session` | Tạo session mới |
| DELETE | `/v1/session/{id}` | Xoá session |
| POST | `/v1/detect` | Detect + track object |

---

## Session & Tracking

```
Frame 1 ── POST /v1/detect (session_id="video_1") ──→ track_id=1, track_id=2
Frame 2 ── POST /v1/detect (session_id="video_1") ──→ track_id=1, track_id=2 (giữ ID)
Frame 3 ── POST /v1/detect (session_id="video_1") ──→ ...
```

- Mỗi session giữ 1 `YoloByteTrackDetector` riêng (có internal tracker state)
- ByteTrack dùng `persist=True` để tracking ID xuyên frame
- Session tự động bị xoá sau `ttl` giây (mặc định 600s = 10 phút) không hoạt động
- Tối đa `max_sessions` (mặc định 32), cũ nhất bị evict nếu đầy

---

## Deploy

### Modal (recommended)

```bash
cd serving
modal deploy modal_app.py
# Output: https://tienpm205--trafficflow-inference-fastapi-app.modal.run
```

Gọi từ ngoài:
```bash
curl -X POST https://tienpm205--trafficflow-inference-fastapi-app.modal.run/v1/detect \
  -F "image=@frame.jpg" \
  -F "session_id=video_1"
```

### Docker

```bash
cd serving
docker build -t trafficflow:latest .
docker run -p 8000:8000 trafficflow:latest
```
