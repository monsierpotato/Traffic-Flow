# AI Core Integration Guide

## Summary

The TrafficFlow AI core is shipped as an **installable Python library**. The
Backend-owned worker imports it and calls the runtime engine directly — there is
no separate AI service, no Celery, and no HTTP API inside the AI core. Queue
(Redis/Celery), DB, storage, and the worker process all live on the Backend side
and are shared infrastructure.

```text
Backend (FastAPI + DB + storage + redis/celery + worker)
  └─ import trafficflow.runtime
       └─ TrafficFlowEngine.process_video(...)   <-- the AI core (this library)
```

The AI core runs YOLOv8 + ByteTrack, so the worker process that imports it must
run on the GPU server.

## Install

The package ships only the reusable engine modules
(`runtime`, `core_ai`, `counting`, `geometry`, `pipeline`). Backend boundaries
and the CLI are not part of the distribution.

```bash
# 1. PyTorch CUDA wheels first (must come from the official CUDA index)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130

# 2. The AI core with its inference stack
pip install "trafficflow[gpu]"
```

Model weights are NOT bundled. The worker supplies the weights path via
`VideoCountingRequest.model_path`.

## Public API

Import everything from `trafficflow.runtime`:

```python
from trafficflow.runtime import (
    TrafficFlowEngine,
    VideoCountingRequest,
    VideoCountingResult,
)
```

The worker only needs three things: build a request, call `process_video`, read
the result. Internals (YOLO, ByteTrack, OpenCV) are encapsulated.

## Worker usage example

```python
from pathlib import Path
from trafficflow.runtime import TrafficFlowEngine, VideoCountingRequest

def process_video_task(task_id: str) -> dict:
    task = db.get_task(task_id)                 # Backend DB access

    def on_progress(payload: dict) -> None:
        # payload: {status, frame_index, frames_processed, total_frames, progress}
        # Persist status/frames_processed/progress to the Task row.
        db.update_task_progress(task_id, payload)

    request = VideoCountingRequest(
        video_path=Path(task.video_path),
        config_path=Path(task.lane_config_path),
        model_path=settings.model_path,         # e.g. "models/yolov8n.pt"
        device=settings.gpu_device,             # e.g. "0"
        output_video_path=Path(task.output_video_path),
        output_jsonl_path=Path(task.output_events_path),
        progress_callback=on_progress,
    )

    try:
        result = TrafficFlowEngine().process_video(request)
    except Exception:
        # Engine already emitted a `failed` progress payload before re-raising,
        # so the Task row is already marked failed. Re-raise for Celery retry.
        raise

    payload = result.to_dict()                  # counts, total_count, output paths
    db.save_task_result(task_id, payload)
    return payload
```

## Contracts

- Progress callback payload: [[Progress Callback Contract]] —
  `docs/contracts/progress_callback.md`.
- Result shape returned by `to_dict()`: [[Video Counting Result Contract]] —
  `docs/contracts/video_counting_result.md`.
- Lane config (with optional `annotation_roi`): [[Lane Config Contract]].

## Notes

- The engine returns **local filesystem paths** in the result. Backend/API code
  translates them to public URLs.
- Failures surface as exceptions; `failed` is emitted through the progress
  callback before the exception is re-raised, so DB state stays consistent.
- The engine reports `processing` progress every `progress_interval_percent`
  (default 5%). `total_frames`/`progress` can be `null` if OpenCV cannot read
  frame count and no `max_frames` is set.

## Links

- [[Runtime Engine]]
- [[Production Architecture]]
- [[Progress Callback Contract]]
- [[Video Counting Result Contract]]
