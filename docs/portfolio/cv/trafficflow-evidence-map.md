# TrafficFlow CV Evidence Map

## Project Scope

| Claim | Evidence |
|---|---|
| Five-member team project | `docs/portfolio/project-scope-and-ownership.md` |
| Personal ownership is AI/computer-vision pipeline, not full-stack product | `docs/portfolio/project-scope-and-ownership.md` |
| Live runtime contribution is analysis/validation lead with shared platform integration | `docs/portfolio/project-scope-and-ownership.md`, `docs/reports/phase-08-live-runtime.md` |

## Metrics

| CV/README metric | Value | Run ID | Evidence |
|---|---:|---|---|
| Held-out detector AP50 | 0.582020 | `phase04-heldout-yolov8m-docker-gpu-20260718-held_out_test-yolov8m` | `docs/reports/phase-04-detection-benchmark.md` |
| Held-out detector recall | 0.679091 | `phase04-heldout-yolov8m-docker-gpu-20260718-held_out_test-yolov8m` | `docs/reports/phase-04-detection-benchmark.md` |
| Held-out direct ByteTrack HOTA | 0.242433 | `e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718` | `docs/reports/end-to-end-bytetrack-production-comparison.md` |
| Held-out direct ByteTrack IDF1 | 0.284952 | `e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718` | `docs/reports/end-to-end-bytetrack-production-comparison.md` |
| Held-out direct ByteTrack ID switches | 42 | `e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718` | `docs/reports/end-to-end-bytetrack-production-comparison.md` |
| Held-out direct ByteTrack Event F1 | 0.942238 | `e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718` | `docs/reports/end-to-end-bytetrack-production-comparison.md` |
| Held-out direct ByteTrack WAPE | 0.050360 | `e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718` | `docs/reports/end-to-end-bytetrack-production-comparison.md` |
| Uploaded-video best measured FPS | 75.829 | `phase07-upload-runtime-bytetrack-production-docker-gpu-20260718-v2` | `docs/reports/phase-07-upload-runtime.md` |
| Uploaded-video best measured RTF | 3.033x | `phase07-upload-runtime-bytetrack-production-docker-gpu-20260718-v2` | `docs/reports/phase-07-upload-runtime.md` |
| Uploaded-video VRAM peak for best ByteTrack workload | 2878 MB | `phase07-upload-runtime-bytetrack-production-docker-gpu-20260718-v2` | `docs/reports/phase-07-upload-runtime.md` |
| Live processed/published FPS | 14.895 | `phase08-live-hls-30min-20260718` | `docs/reports/phase-08-live-runtime.md` |
| Live dropped frames | 0 | `phase08-live-hls-30min-20260718` | `docs/reports/phase-08-live-runtime.md` |
| Live frame age p95 | 0.9 ms | `phase08-live-hls-30min-20260718` | `docs/reports/phase-08-live-runtime.md` |
| Live soak duration | 1803.284 s | `phase08-live-hls-30min-20260718` | `docs/reports/phase-08-live-runtime.md` |
| Phase 09 tracker/live ablation and error taxonomy | Partial pass; ROI accuracy blocked | `phase09_analysis` | `docs/reports/phase-09-ablation-error-analysis.md` |

## Metrics Not Safe To Claim

| Claim to avoid | Reason |
|---|---|
| Motorcycle AP/recall/counting accuracy on UA-DETRAC | UA-DETRAC labels in this repo have no motorcycle-compatible class. |
| Live count accuracy | The YouTube/HLS source has no GT. |
| Full-stack solo ownership | Team project; personal ownership is AI/computer-vision pipeline. |
| Production re-tracker as best measured tracker | Direct ByteTrack performed better in held-out end-to-end metrics. |
| ROI accuracy improvement | Full-frame vs crop-ROI AP/Event F1/WAPE is blocked until crop ROI GT exists for the benchmark sequences. |
