# TrafficFlow Recruiter Overview

## One-Minute Summary

TrafficFlow is a five-member team project for lane-level vehicle counting from uploaded videos and live traffic streams. My contribution focused on the computer-vision pipeline: ROI/crop semantics, YOLO detection integration, lane filtering, tracker/counting evaluation, derived counting ground truth, and runtime benchmark reporting.

## Key Results

| Area | Result | Evidence |
|---|---:|---|
| Held-out detection | AP50 0.5820, recall 0.6791 | `benchmark/reports/detection_report.md` |
| Held-out E2E counting, direct ByteTrack | Event F1 0.942238, WAPE 0.050360 | `benchmark/reports/end_to_end_report.md` |
| Held-out E2E tracking, direct ByteTrack | HOTA 0.242433, IDF1 0.284952, IDSW 42 | `benchmark/reports/end_to_end_report.md` |
| Uploaded-video runtime | 75.829 FPS, 3.033x real time | `benchmark/reports/batch_runtime_report.md` |
| Live/HLS runtime | 14.895 FPS, frame age p95 0.9 ms, 0 dropped frames | `benchmark/reports/live_runtime_report.md` |

## My Role

Personal ownership:

- Designed and validated the AI-side ROI/crop and coordinate-space behavior.
- Integrated YOLO/ByteTrack and evaluated model/runtime trade-offs.
- Built lane/class filtering, lane association, direction validation, and line-crossing counting semantics.
- Built benchmark runners and reports for detection, tracking, counting, upload runtime, and live runtime.
- Led live AI-runtime bottleneck analysis and validation.

Shared/team-owned areas:

- Product UX and frontend annotation flow.
- General backend APIs, database/storage integration, and deployment.
- Live platform integration around the AI runtime.

## Why This Is More Than YOLO

YOLO only produces boxes. TrafficFlow needs the full path from frame to count:

```text
Frame -> ROI -> Detector -> Filter -> Tracker -> Lane association -> Direction check -> Crossing event -> Count
```

The benchmark evidence shows that tracker choice and runtime scheduling materially affect final counting behavior, not just model AP.

## Current Release Readiness

- CV package: ready from measured evidence.
- GitHub README: ready with limitations.
- Technical interview prep: ready for core pipeline and benchmark discussion.
- Phase 09 ablation/error taxonomy: partial pass. Tracker and live scheduling are evidenced; ROI accuracy ablation remains blocked until crop ROI GT exists.
