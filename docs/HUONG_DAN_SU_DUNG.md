# 🚦 Hướng dẫn chạy & sử dụng TrafficFlow

## 📋 Yêu cầu hệ thống

| Phần mềm | Phiên bản tối thiểu | Mục đích |
|----------|---------------------|----------|
| Python | 3.10+ | Backend API |
| Redis | 6.0+ | Celery message broker |
| MongoDB | 5.0+ hoặc Atlas cloud | Cơ sở dữ liệu |
| Node.js | 18+ (nếu build frontend) | Build React frontend |
| FFmpeg | Bất kỳ (tùy chọn) | Xử lý video nâng cao |

> **Lưu ý:** Project đã được cấu hình sẵn MongoDB Atlas và Redis cloud trong file `.env`, nên bạn **không cần cài MongoDB/Redis local**.

---

## 🔧 Cài đặt

### Bước 1: Tạo Virtual Environment

```bash
cd d:\Backend_traffic_flow
python -m venv .venv
```

### Bước 2: Kích hoạt Virtual Environment

```bash
# Windows CMD
.venv\Scripts\activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

### Bước 3: Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### Bước 4: Kiểm tra file `.env`

Đảm bảo file `.env` ở thư mục gốc `d:\Backend_traffic_flow\.env` chứa đầy đủ các biến:

```env
# MongoDB Atlas
MONGODB_URI=mongodb+srv://...
MONGODB_DB_NAME=trafficflow

# Cloudflare R2 (để placeholder nếu chưa có → tự động dùng local storage)
R2_ACCOUNT_ID=placeholder_account_id
R2_ACCESS_KEY_ID=placeholder_access_key
R2_SECRET_ACCESS_KEY=placeholder_secret_key
R2_BUCKET_NAME=trafficflow
R2_PUBLIC_URL=http://localhost:8000/static/previews

# Redis (Celery broker)
REDIS_URL=redis://...

# Upload settings
MAX_FILE_SIZE_MB=1024
RETENTION_DAYS=3
```

> Nếu `R2_ACCOUNT_ID` là `placeholder_account_id`, hệ thống sẽ tự động lưu file vào thư mục `storage/` local thay vì Cloudflare R2.

---

## 🚀 Khởi chạy

Bạn cần mở **2 terminal riêng biệt** — một cho API Server, một cho Celery Worker.

### Terminal 1 — Chạy FastAPI Server

```bash
cd d:\Backend_traffic_flow
.venv\Scripts\activate
set PYTHONPATH=.
python -m trafficflow.main
```

Hoặc dùng file bat có sẵn:

```bash
run_server.bat
```

Khi thấy dòng này nghĩa là server đã sẵn sàng:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Mounted static directory 'storage' at '/static'
INFO:     Mounted frontend dist directory at '/'
```

### Terminal 2 — Chạy Celery Worker

```bash
cd d:\Backend_traffic_flow
.venv\Scripts\activate
celery -A trafficflow.core.celery_app worker --pool=solo -l info
```

Hoặc dùng file bat có sẵn:

```bash
run_worker.bat
```

Khi thấy dòng này nghĩa là worker đã sẵn sàng nhận task:

```
[2026-xx-xx xx:xx:xx] celery@YOUR_PC ready.
```

> ⚠️ **Trên Windows** phải dùng `--pool=solo` vì Celery prefork không hỗ trợ đầy đủ trên Windows.

---

## 🌐 Truy cập giao diện

Sau khi cả 2 terminal đều đã chạy, mở trình duyệt:

| Giao diện | URL | Mô tả |
|-----------|-----|-------|
| **Frontend React** (chính) | [http://localhost:8000](http://localhost:8000) | Giao diện React đầy đủ |
| **Test Dashboard** (HTML) | [http://localhost:8000/static/index.html](http://localhost:8000/static/index.html) | Dashboard test đơn giản |
| **API Docs** (Swagger) | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI để test API trực tiếp |
| **API Docs** (ReDoc) | [http://localhost:8000/redoc](http://localhost:8000/redoc) | ReDoc — dạng tài liệu API |

---

## 📖 Hướng dẫn sử dụng (Frontend React)

### Step 1: Upload Video

1. Truy cập [http://localhost:8000](http://localhost:8000)
2. Ở trang **"Video Source"**, click vào vùng **"Drag and drop video feed"** hoặc nhấn **"Browse Files"**
3. Chọn file video (`.mp4` hoặc `.avi`)
4. Đợi upload hoàn tất — hệ thống sẽ:
   - Upload video lên server
   - Trích xuất frame đầu tiên làm preview
   - Tự động chuyển sang bước tiếp theo

### Step 2: Vẽ ROI (Region of Interest)

1. Trên canvas hiển thị frame preview, bạn sẽ thấy **4 điểm neo màu đỏ** tạo thành hình tứ giác
2. **Kéo thả** 4 điểm để bao quanh vùng đường bạn muốn giám sát
3. Mục đích: crop video chỉ giữ lại vùng đường, loại bỏ phần thừa (vỉa hè, cây cối...)
4. Quan sát thông số **Crop X, Y, Width, Height** ở panel phải
5. Nhấn **"Confirm ROI"** để xác nhận

### Step 3: Vẽ Lane (Làn đường)

1. Ở canvas crop, bạn cần vẽ **3 thành phần** cho mỗi lane:

   | Thành phần | Cách vẽ | Ý nghĩa |
   |-----------|---------|---------|
   | **Zone** (vùng) | Click 4 điểm tạo tứ giác | Vùng phát hiện xe |
   | **Line** (đường đếm) | Kéo chuột vẽ đoạn thẳng | Đường counting gate |
   | **Arrow** (hướng) | Kéo chuột vẽ mũi tên | Hướng di chuyển của xe |

2. Chọn tab **"Zone"** → Click 4 điểm trên canvas bao quanh 1 làn đường
3. Chọn tab **"Line"** → Kéo chuột vẽ đường đếm cắt ngang làn
4. Chọn tab **"Arrow"** → Kéo chuột vẽ hướng xe đi (vào/ra)
5. Để thêm lane mới, nhấn nút **"+"** ở panel phải
6. Đặt tên lane trong ô input (ví dụ: `lane_1`, `lane_2`)
7. Có thể kéo thả các điểm để chỉnh sửa vị trí
8. Điều chỉnh **Runtime parameters** nếu cần:
   - **Movement threshold**: Ngưỡng pixel để phát hiện xe đang di chuyển
   - **Cooldown frames**: Số frame chờ trước khi đếm lại cùng 1 xe
   - **Cooldown distance**: Khoảng cách pixel tối thiểu giữa 2 lần đếm
9. Nhấn **"Submit Task"** khi đã hoàn tất

### Step 4: Xem kết quả Analytics

1. Sau khi submit, hệ thống sẽ:
   - Gửi cấu hình lane lên backend
   - Crop video theo ROI
   - Đẩy task vào hàng đợi Celery
2. **Progress bar** sẽ tự động cập nhật: 0% → 25% → 60% → 90% → 100%
3. Khi hoàn tất, bạn sẽ thấy:
   - 🎬 **Video kết quả** (có đánh dấu xe)
   - 📊 **Bảng thống kê** số lượng xe theo từng lane và loại xe (car, bus, truck, motorcycle)
   - 📈 **Biểu đồ bar** trực quan
4. Nhấn **"View JSON"** để xem raw data payload

---

## 📖 Hướng dẫn sử dụng (Test Dashboard HTML)

Truy cập [http://localhost:8000/static/index.html](http://localhost:8000/static/index.html)

### Step 1: Upload Video
- Click vào vùng upload hoặc kéo thả file video vào
- Đợi upload hoàn tất → frame preview sẽ hiện ra

### Step 2: Vẽ ROI & Lane
- Nhấn **"🔴 Vẽ ROI"** → Click trên ảnh ít nhất 3 điểm để vẽ vùng quan sát
- **Double-click** hoặc nhấn **"✅ Hoàn thành"** để kết thúc vẽ ROI
- Nhấn **"➕ Thêm Lane"** → Click vẽ polygon ít nhất 3 điểm cho mỗi lane
- **Double-click** để kết thúc vẽ lane
- Kéo thả các điểm để điều chỉnh vị trí
- Đặt tên lane và chọn hướng (Vào/Ra/Cả hai)
- Nhấn **"💾 Lưu cấu hình & Tiếp tục"**

### Step 3: Xử lý
- Nhấn **"Trigger Process Queue"**
- Theo dõi progress bar tự động cập nhật

### Step 4: Xem kết quả
- Khi hoàn tất, video kết quả và bảng thống kê sẽ tự động hiện ra
- Dashboard bên phải hiển thị tổng quan tất cả tasks

---

## 🔌 API Reference (Tóm tắt)

Truy cập [http://localhost:8000/docs](http://localhost:8000/docs) để xem Swagger UI đầy đủ.

### Upload video
```bash
curl -X POST http://localhost:8000/api/v1/upload/video \
  -F "file=@sample.mp4"
```

### Cấu hình lane
```bash
curl -X POST http://localhost:8000/api/v1/lanes/config \
  -H "Content-Type: application/json" \
  -d '{
    "video_id": "<VIDEO_ID>",
    "lanes": [{
      "lane_id": "lane-1",
      "name": "Lane 1",
      "points": [{"x": 0.1, "y": 0.3}, {"x": 0.5, "y": 0.3}, {"x": 0.5, "y": 0.8}, {"x": 0.1, "y": 0.8}],
      "direction": "both"
    }],
    "roi": {
      "points": [{"x": 0.05, "y": 0.2}, {"x": 0.95, "y": 0.2}, {"x": 0.95, "y": 0.9}, {"x": 0.05, "y": 0.9}]
    }
  }'
```

### Trigger xử lý
```bash
curl -X POST http://localhost:8000/api/v1/tasks/process \
  -H "Content-Type: application/json" \
  -d '{"video_id": "<VIDEO_ID>"}'
```

### Kiểm tra trạng thái
```bash
curl http://localhost:8000/api/v1/tasks/status/<TASK_ID>
```

### Lấy kết quả
```bash
curl http://localhost:8000/api/v1/tasks/result/<TASK_ID>
```

### Xem dashboard
```bash
curl http://localhost:8000/api/v1/dashboard/stats
```

---

## ❓ Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân | Cách fix |
|-----|------------|----------|
| `ModuleNotFoundError: No module named 'trafficflow'` | Thiếu PYTHONPATH | Chạy `set PYTHONPATH=.` trước khi start |
| `Connection refused` khi upload | Server chưa chạy | Chạy `run_server.bat` trước |
| Progress bar không chạy sau khi trigger | Worker chưa chạy | Chạy `run_worker.bat` ở terminal thứ 2 |
| `Task is in status 'uploaded'` | Chưa configure lanes | Vẽ ROI + lanes trước khi trigger process |
| Preview ảnh không hiển thị | Thiếu OpenCV | Chạy `pip install opencv-python-headless` |
| `No module named 'magic'` | Thiếu python-magic | Chạy `pip install python-magic python-magic-bin` |
| Redis connection refused | Redis chưa chạy / URL sai | Kiểm tra `REDIS_URL` trong `.env` |
| MongoDB connection timeout | MongoDB URI sai / mạng | Kiểm tra `MONGODB_URI` trong `.env` |

---

## 📂 Cấu trúc thư mục

```
d:\Backend_traffic_flow\
├── .env                          # Biến môi trường
├── requirements.txt              # Python dependencies
├── run_server.bat                # Script chạy FastAPI server
├── run_worker.bat                # Script chạy Celery worker
├── sample.mp4                    # Video mẫu để test
│
├── trafficflow/                  # Backend Python package
│   ├── main.py                   # Entry point (uvicorn)
│   ├── config.py                 # Settings từ .env
│   ├── api/
│   │   ├── app.py                # FastAPI app factory
│   │   └── v1/
│   │       ├── router.py         # API router tổng
│   │       ├── upload.py         # POST /upload/video
│   │       ├── lanes.py          # POST /lanes/config
│   │       ├── tasks.py          # POST /tasks/process, GET /status, /result
│   │       └── dashboard.py      # GET /dashboard/stats
│   ├── core/
│   │   ├── database.py           # MongoDB connection (Motor)
│   │   ├── celery_app.py         # Celery config + mock worker
│   │   └── r2_client.py          # Cloudflare R2 / Local storage
│   ├── services/
│   │   ├── video_service.py      # Extract frame, crop video (OpenCV)
│   │   └── cleanup_service.py    # Auto-delete expired data
│   ├── schemas/                  # Pydantic models
│   └── middleware/
│       └── file_validator.py     # Validate upload (size, type, MIME)
│
├── storage/                      # Local file storage (R2 mock)
│   ├── index.html                # Test Dashboard HTML
│   ├── uploads/                  # Video files
│   ├── previews/                 # Preview frames (JPG)
│   └── results/                  # Processed results
│
└── Traffic-Flow_Frontend/        # React frontend (Vite)
    └── frontend/
        ├── src/App.jsx           # Main React component
        ├── dist/                 # Built production files
        └── package.json
```

---

## 🔄 Quy trình hoạt động tổng quan

```
[User Upload Video]
        │
        ▼
[Backend: Lưu video + Trích xuất preview frame]
        │
        ▼
[User: Vẽ ROI + Lanes trên preview]
        │
        ▼
[Backend: Lưu lane config vào MongoDB]
        │
        ▼
[User: Nhấn "Process"]
        │
        ▼
[Backend: Crop video theo ROI → Gửi Celery task]
        │
        ▼
[Celery Worker: Xử lý video → Callback progress về Backend]
        │
        ▼
[Frontend: Poll status mỗi 1.5-2s → Hiển thị progress]
        │
        ▼
[Worker hoàn tất → Status = "completed"]
        │
        ▼
[Frontend: Fetch kết quả → Hiển thị video + thống kê]
```
