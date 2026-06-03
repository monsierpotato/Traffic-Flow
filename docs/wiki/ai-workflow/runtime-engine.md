# Runtime Engine

## Summary

The runtime engine is the reusable orchestration layer for video counting. CLI, future API code, and future worker code should call the same engine instead of duplicating the AI workflow.

## Current State

- `trafficflow/runtime/engine.py` defines the reusable processing path.
- `trafficflow/cli/run_counting.py` parses command-line arguments and delegates to the runtime engine.
- Overlay drawing has been separated into `trafficflow/pipeline/overlay.py`.
- Result output is documented in `docs/contracts/video_counting_result.md` with a sample at `docs/contracts/result_sample.json`.
- `VideoCountingResult.to_dict()` returns status, processed frames, effective total frames, lane/class counts, total count, and output artifact paths.
- `progress_callback` is implemented on `VideoCountingRequest` and emits `started`, `processing`, `completed`, and `failed` progress payloads.
- A smoke-style runtime test exists in `tests/test_runtime_engine.py`; it uses a synthetic video and fake detector so it does not depend on YOLO weights.
- A real YOLO smoke run completed on 2026-06-02 using `data/raw/danang/Cầu Rồng.mp4`, `configs/danang/cau_rong_manual.json`, `models/yolov8n.pt`, and `--max-frames 5`.

## Decisions

- Keep CLI as an adapter, not the production engine.
- Use progress callback support before integrating the engine with a background worker.

## Open Questions

- Should progress updates stay frame-count based, or should later production runs also emit time-based heartbeat updates?
- Which real demo clip should become the canonical repeatable smoke fixture for future releases?

## Links

- [[Production Architecture]]
- [[Lane Config Contract]]
- [[Progress Callback Contract]]
- [[Video Counting Result Contract]]
