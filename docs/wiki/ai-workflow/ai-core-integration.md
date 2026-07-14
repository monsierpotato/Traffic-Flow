# AI Core Integration Guide

## Summary

The TrafficFlow AI core (`tfengine`) ships as a local library. The worker imports
it and calls the runtime engine directly — no separate AI service, no HTTP API to
Modal GPU. Queue (Redis/Celery), DB, storage, and the worker process all live in Docker.

```text
Docker Compose
  ├─ redis (broker)
  ├─ api (FastAPI + React)
  └─ worker (Celery) ── import tfengine.runtime ── YOLO GPU local
```

The worker runs YOLOv8 + ByteTrack via `LocalInferenceClient`, which auto-detects
CUDA GPU and falls back to CPU.

## Public API

```python
from tfengine.runtime import (
    TrafficFlowEngine,
    VideoCountingRequest,
    VideoCountingResult,
)
```

The worker only needs three things: build a request, call `process_video`, read
the result. Internals (YOLO, ByteTrack, OpenCV) are encapsulated.

## Worker usage (current pipeline)

```python
from worker.pipeline.local_client import LocalInferenceClient

ai_client = LocalInferenceClient()  # reads config from settings:
#   AI_MODEL_PATH (default: models/yolov8n.pt)
#   AI_DEVICE (default: 0 = cuda:0)
#   AI_IMGSZ (default: 640)
#   AI_HALF (default: true — FP16 on CUDA)
#   AI_CLASS_IDS (default: 2,3,5,7 — COCO vehicle)
#   AI_CONFIDENCE (default: 0.1)
```

## GPU Config

| Env | Default | Note |
|-----|---------|------|
| `AI_DEVICE` | `0` | `0` = cuda:0, `cpu` = CPU |
| `AI_HALF` | `true` | FP16; auto-disabled on CPU |
| `AI_IMGSZ` | `640` | Input resize for YOLO |
| `AI_CLASS_IDS` | `2,3,5,7` | COCO: car,motorcycle,bus,truck |
| `AI_MODEL_PATH` | `models/yolov8n.pt` | YOLO weights |

## Contracts

- Progress callback payload: [[Progress Callback Contract]].
- Result shape returned by `to_dict()`: [[Video Counting Result Contract]].
- Lane config (with optional `annotation_roi`): [[Lane Config Contract]].

## Notes

- 1 GPU = 1 Celery worker process (`--concurrency=1`). Two processes sharing GPU cause contention.
- Engine reports `processing` progress every `progress_interval_percent` (default 5%).
- COCO class filter happens inside `YOLO.track(classes=[2,3,5,7])` — earlier and faster than post-processing filter.

## Links

- [[Runtime Engine]]
- [[Production Architecture]]
- [[Progress Callback Contract]]
- [[Video Counting Result Contract]]
