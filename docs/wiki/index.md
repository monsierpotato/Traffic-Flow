# TrafficFlow Wiki Index

## Architecture
- [[Production Architecture]] - Planned system boundaries for API, worker, queue, storage, observability, and the reusable AI runtime.
- [[Backend Refactor Plan]] - Historical package-structure audit and refactor plan leading to the current `src/` layout.
- [[Geometry Config Scaling]] - Phased plan for removing the manual per-camera geometry bottleneck (industrialize manual config, then automate inference).
- [[Local DB Fallback]] - Development fallback when MongoDB Atlas TLS/connectivity fails during local E2E.
- [[Frontend Deploy Readiness]] - Frontend/API readiness notes for deployable user workflows.

## AI Workflow
- [[Runtime Engine]] - The reusable counting workflow shared by CLI now and future API/worker code.
- [[ai-core-integration|AI Core Integration Guide]] - How the Backend worker installs and calls the AI core as a library (install, public API, worker example).
- [[gpu-docker-live-optimization|GPU Docker + Live Streaming Optimization]] - Local GPU Docker queue, smooth stage progress, and live camera anti-lag workflow.
- [[Phase 00 Repository Audit]] - Baseline freeze, ownership matrix, model inventory, and validation status before portfolio benchmark phases.
- [[Phase 01 Benchmark Protocol]] - Frozen UA-DETRAC inventory, sequence split, class mapping, metric definitions, and anti-leakage benchmark protocol.
- [[Phase 02 Derived Ground Truth]] - Manual per-sequence source-frame geometry, derived counting events/counts, and audit sample for UA-DETRAC selected sequences.
- [[Phase 03 Benchmark Runner]] - Unified benchmark entry point, manifest schemas, run config, and frontend-free smoke run using manual geometry.
- [[Phase 04 Detection Benchmark]] - Detector-only model comparison, selected model, held-out result, and per-class weakness analysis.
- [[Phase 05 Tracking Benchmark]] - TrackEval identity benchmark, tracker ablation, selected tracker, and held-out result.
- [[Phase 06 Counting Benchmark]] - Oracle counting-event matching, aggregate lane/class/direction metrics, and held-out counting report.
- [[End-to-End ByteTrack Production Comparison]] - Full YOLOv8m + tracker + counting comparison between direct ByteTrack and current production re-tracker.
- [[phase-07-upload-runtime|Phase 07 Uploaded-Video Runtime Benchmark]] - Full upload AI-path runtime benchmark covering decode, preprocess, inference, tracking, counting, render, encode, and resource usage.
- [[phase-08-live-runtime|Phase 08 Live Runtime Benchmark]] - 30-minute YouTube HLS soak test with live FPS, frame age, inference latency, drop/stall/error, and resource timeseries.
- [[phase-09-ablation-error-analysis|Phase 09 Ablation And Error Analysis]] - Tracker/live ablations, ROI accuracy blocker, error taxonomy, and representative frame artifacts.
- [[Live Source Annotation Workflow]] - Resolve YouTube/HLS/RTSP/MJPEG sources, capture preview, annotate geometry, then start live counting.
- [[ROI Annotation]] - Rectangular crop workflow for more accurate lane drawing while keeping source-frame coordinates.

## Portfolio Package
- [Recruiter Overview](../portfolio/recruiter-overview.md) - One-minute project summary, scoped contribution, and key measured results.
- [AI Pipeline](../portfolio/ai-pipeline.md) - Frame-to-count pipeline, ROI coordinate spaces, lane semantics, and runtime design.
- [Error Analysis](../portfolio/error-analysis.md) - Phase 09 error taxonomy, negative tracker finding, ROI blocker, and representative examples.
- [Limitations](../portfolio/limitations.md) - Dataset, benchmark, runtime, and ownership limitations.
- [CV Bullets](../portfolio/cv/trafficflow-cv-bullets.md) - Resume-ready TrafficFlow bullets.
- [Interview Answers](../portfolio/cv/trafficflow-interview-answers.md) - Technical interview preparation notes.
- [Evidence Map](../portfolio/cv/trafficflow-evidence-map.md) - Metric-to-report/run-ID mapping.
- [Release Checklist](../portfolio/release-checklist.md) - Final readiness gate and public-release blockers.

## Contracts
- [[Lane Config Contract]] - Lane configuration shape, including optional `annotation_roi`.
- [[Progress Callback Contract]] - Runtime progress payload for worker/API task status updates.
- [[Video Counting Result Contract]] - Engine result JSON shape and event JSONL output for API/worker persistence.

## Sprints
- [[Project Backlog]] - Current progress, sprint structure, and work split for a five-person team.

## Decisions
- [[Decision Log]] - Accepted architecture and workflow decisions.

## Sources
- [[deploy-ai-traffic-work-plan|Deploy AI Traffic Work Plan Source]] - Google Doc source for team ownership, sprint plan, progress, and MVP backlog.
