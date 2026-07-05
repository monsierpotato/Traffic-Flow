# Decision Log

## Accepted Decisions

- Use `trafficflow.runtime.engine` as the reusable AI workflow entrypoint.
- Keep `trafficflow.cli.run_counting` as a thin wrapper.
- Add production boundaries for API, worker, queue, storage, and observability before implementing each layer.
- Use rectangular ROI for lane drawing support.
- Use `annotation crop: yes; processing crop: no` for the MVP.
- Store lane geometry in source-frame coordinates.
- Support rectangular annotation ROI in the OpenCV config generator before building the web canvas flow.
- **Package separation**: Name backend app `backend/` and AI core library `ai-core/` to resolve namespace collision.
- **Modal HTTP API**: Keep Modal GPU HTTP API for YOLO detection (no local GPU); counting logic runs locally.
- **Task status state machine**: Reject re-processing of completed/failed/archived tasks; reject concurrent processing with 409 Conflict.
- **Pipeline refactoring**: Split monolithic `celery_app.py` (499 lines) into 4 single-responsibility `pipeline/` modules — `processor.py`, `ai_client.py`, `tracker.py`, `renderer.py` — for testability and maintainability.
- **Local Kalman tracking (approach B)**: Worker runs `LocalTracker` with 8-state Kalman filter (cx,cy,w,h,vx,vy,vw,vh) instead of center-dead-reckoning velocity. Provides smooth velocity (converges in 2-3 frames) and lost-track prediction up to 30 frames. Strips Modal ByteTrack track IDs and re-tracks locally.
- **DirectionFilter with cosine similarity**: Replace raw dot-product direction check with `cos_sim >= 0.3` threshold to reject perpendicular movement (e.g. RIGHT-moving car on UP lane → cos_sim=0 → rejected).

## Proposed / Under Review

- Geometry config scaling: industrialize manual config first (web annotation behind `api/`), then automate geometry inference with confidence-routed human review; build a config-scoring harness before any inference. Do not change the counting paradigm unless count granularity is explicitly relaxed. See [[Geometry Config Scaling]].

## Deferred Decisions

- Whether to crop frames during AI processing.
- Whether to add ONNX/OpenVINO optimization before or after local end-to-end MVP.
- Whether MVP database starts with SQLite or PostgreSQL.
- Whether the OpenCV config generator needs ROI editing after lanes have already been added.

## Links

- [[Production Architecture]]
- [[ROI Annotation]]
- [[Project Backlog]]
- [[Geometry Config Scaling]]
