# TrafficFlow Wiki Index

## Architecture
- [[Production Architecture]] - Planned system boundaries for API, worker, queue, storage, observability, and the reusable AI runtime.
- [[Backend Refactor Plan]] - Historical package-structure audit and refactor plan leading to the current `src/` layout.
- [[Geometry Config Scaling]] - Phased plan for removing the manual per-camera geometry bottleneck (industrialize manual config, then automate inference).
- [[Local DB Fallback]] - Development fallback when MongoDB Atlas TLS/connectivity fails during local E2E.
- [[Frontend Deploy Readiness]] - Frontend/API readiness notes for deployable user workflows.

## AI Workflow
- [[Runtime Engine]] - The reusable counting workflow shared by CLI now and future API/worker code.
- [[AI Core Integration Guide]] - How the Backend worker installs and calls the AI core as a library (install, public API, worker example).
- [[GPU Docker + Live Streaming Optimization]] - Local GPU Docker queue, smooth stage progress, and live camera anti-lag workflow.
- [[Live Source Annotation Workflow]] - Resolve YouTube/HLS/RTSP/MJPEG sources, capture preview, annotate geometry, then start live counting.
- [[ROI Annotation]] - Rectangular crop workflow for more accurate lane drawing while keeping source-frame coordinates.

## Contracts
- [[Lane Config Contract]] - Lane configuration shape, including optional `annotation_roi`.
- [[Progress Callback Contract]] - Runtime progress payload for worker/API task status updates.
- [[Video Counting Result Contract]] - Engine result JSON shape and event JSONL output for API/worker persistence.

## Sprints
- [[Project Backlog]] - Current progress, sprint structure, and work split for a five-person team.

## Decisions
- [[Decision Log]] - Accepted architecture and workflow decisions.

## Sources
- [[Deploy AI Traffic Work Plan Source]] - Google Doc source for team ownership, sprint plan, progress, and MVP backlog.
