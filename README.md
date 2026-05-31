# TrafficFlow Manual Counting

TrafficFlow dùng manual geometry cho lane/counting configuration:

- Phase A: `trafficflow.cli.config_generator` lấy một frame từ video và cho người dùng vẽ line/zone/gate bằng chuột.
- Phase B: `trafficflow.cli.run_counting` chạy YOLOv8 + ByteTrack, lấy bottom-center của bbox, kiểm tra giao cắt hình học và đếm xe.

Benchmark lane detection cũ được giữ trong `old_benchmark/` để tham khảo.

## Quick Start

Tạo config thủ công cho một camera/video:

```powershell
.\.venv-gpu\Scripts\python.exe -m trafficflow.cli.config_generator --video "data\raw\danang\Cầu Rồng.mp4" --output configs\danang\cau_rong_manual.json --camera-id danang_cau_rong --frame-index 150 --display-max-size 1280
```

Tạo config bằng rectangular annotation ROI để vẽ lane trên vùng crop:

```powershell
.\.venv-gpu\Scripts\python.exe -m trafficflow.cli.config_generator --video "data\raw\danang\Cầu Rồng.mp4" --output configs\danang\cau_rong_manual.json --camera-id danang_cau_rong --frame-index 150 --select-roi
```

Chạy Phase B:

```powershell
.\.venv-gpu\Scripts\python.exe -m trafficflow.cli.run_counting --video "data\raw\danang\Cầu Rồng.mp4" --config configs\danang\cau_rong_manual.json --model models\yolov8n.pt --device 0 --output-video outputs\danang\cau_rong\counted.mp4 --output-jsonl outputs\danang\cau_rong\events.jsonl
```

Test nhanh một đoạn ngắn:

```powershell
.\.venv-gpu\Scripts\python.exe -m trafficflow.cli.run_counting --video "data\raw\danang\Cầu Rồng.mp4" --config configs\danang\cau_rong_manual.json --model models\yolov8n.pt --device 0 --max-frames 300 --output-video outputs\danang\cau_rong\test.mp4 --output-jsonl outputs\danang\cau_rong\test_events.jsonl
```

## Configurator Controls

- `1`: Counting line per lane, click 2 điểm cho mỗi lane.
- `2`: Global segment, click 2 điểm toàn mặt đường rồi nhập số lane.
- `3`: Short lane zone, click 4 điểm polygon rồi 2 điểm counting line.
- `4`: Counting gate, click 4 điểm polygon, 2 điểm counting line, 2 điểm direction arrow.
- `Enter`: lưu JSON.
- `R`: xóa các điểm đang click dở.
- `Esc`: thoát không lưu.

## Project Layout

```text
trafficflow/
  core_ai/        YOLO/ByteTrack detector and AI model adapters
  geometry/       Geometry primitives and spatial checks
  counting/       Lane filtering, direction logic, and count aggregation
  pipeline/       Reusable video-processing helpers
  runtime/        Reusable workflow engine shared by CLI/API/worker
  cli/            Local/demo command-line entrypoints
  api/            Future FastAPI boundary
  worker/         Future background worker boundary
  queue/          Future task queue boundary
  storage/        Future file/database persistence boundary
  observability/  Future logging, metrics, and health boundary
configs/          Manual geometry configs grouped by dataset/camera
data/             Local raw videos and samples (ignored by git)
outputs/          Generated videos, JSONL events, debug frames (ignored by git)
models/           Local YOLO weights (ignored by git)
scripts/          Batch/debug helper scripts
tests/            Focused unit tests for counting and geometry
old_benchmark/    Archived lane-detection benchmark work
```

`trafficflow.cli.run_counting` is intentionally a thin wrapper. The reusable AI workflow now lives in
`trafficflow.runtime.engine`, so future API and worker code can call the same processing path without
depending on CLI argument parsing.

Lane drawing can use an optional frontend-only annotation crop. See
`docs/contracts/annotation_roi.md` and `docs/contracts/lane_config_with_annotation_roi.json`.

## Useful Scripts

```powershell
.\.venv-gpu\Scripts\python.exe scripts\smoke_test_manual_counting.py
.\.venv-gpu\Scripts\python.exe scripts\extract_preview_frames.py --data-dir data\raw\danang --output-dir outputs\debug\preview_frames
.\.venv-gpu\Scripts\python.exe scripts\batch_danang_smoke.py --config configs\danang\cau_rong_manual.json
```

## GPU Environment

This project has a local GPU venv at `.venv-gpu` using Python 3.10 and PyTorch CUDA 13.0 wheels.

```powershell
py -3.10 -m venv .venv-gpu
.\.venv-gpu\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv-gpu\Scripts\python.exe -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
.\.venv-gpu\Scripts\python.exe -m pip install -r requirements-gpu.txt
.\.venv-gpu\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```
