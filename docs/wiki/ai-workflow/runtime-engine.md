# Runtime Engine

## Summary

The runtime engine is the reusable orchestration layer for video counting. CLI, future API code, and future worker code should call the same engine instead of duplicating the AI workflow.

## Current State

- `trafficflow/runtime/engine.py` defines the reusable processing path.
- `trafficflow/cli/run_counting.py` parses command-line arguments and delegates to the runtime engine.
- Overlay drawing has been separated into `trafficflow/pipeline/overlay.py`.
- Current result object covers processed frame count and counts. API-ready result contract and event summary are not finalized.
- `progress_callback` is implemented on `VideoCountingRequest` and emits `started`, `processing`, `completed`, and `failed` progress payloads.

## Decisions

- Keep CLI as an adapter, not the production engine.
- Use progress callback support before integrating the engine with a background worker.

## Open Questions

- What exact result JSON should the engine return for API persistence?
- Should progress updates stay frame-count based, or should later production runs also emit time-based heartbeat updates?

## Links

- [[Production Architecture]]
- [[Lane Config Contract]]
- [[Progress Callback Contract]]
