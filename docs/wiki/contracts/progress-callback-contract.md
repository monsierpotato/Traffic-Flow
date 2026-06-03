# Progress Callback Contract

## Summary

The runtime engine can report video processing progress to worker/backend code through an optional callback.

## Current State

- `trafficflow/runtime/engine.py` defines `progress_callback` on `VideoCountingRequest`.
- The callback receives dictionaries with `status`, `frame_index`, `frames_processed`, `total_frames`, and `progress`.
- Contract details live in `docs/contracts/progress_callback.md`.

## Status Values

- `started`
- `processing`
- `completed`
- `failed`

## Links

- [[Runtime Engine]]
- [[Project Backlog]]
