# Video Counting Result Contract

## Summary

The runtime result contract defines the JSON shape returned by `TrafficFlowEngine.process_video(...)` through `VideoCountingResult.to_dict()`.

## Current State

- Source contract: `docs/contracts/video_counting_result.md`.
- Sample JSON: `docs/contracts/result_sample.json`.
- `trafficflow/runtime/engine.py` includes `status`, `frames`, `total_frames`, `counts`, `total_count`, and output artifact paths.
- Event JSONL output remains one counted crossing per line when `output_jsonl_path` is provided.

## Decisions

- Keep local filesystem paths in the runtime result; API code can translate them to public URLs later.
- Keep failures as exceptions, with `failed` emitted through the progress callback before re-raising.

## Open Questions

- Should the backend persist raw JSONL events, aggregate statistics only, or both?

## Links

- [[Runtime Engine]]
- [[Progress Callback Contract]]
- [[Project Backlog]]
