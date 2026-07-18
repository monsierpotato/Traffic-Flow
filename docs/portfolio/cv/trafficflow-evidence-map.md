# TrafficFlow CV Evidence Map

## Project Scope

| Claim | Evidence |
|---|---|
| Five-member team project | `docs/portfolio/project-scope-and-ownership.md` |
| Personal ownership is AI/computer-vision pipeline, not full-stack product | `docs/portfolio/project-scope-and-ownership.md` |
| Live runtime contribution is analysis/validation lead with shared platform integration | `docs/portfolio/project-scope-and-ownership.md`, `benchmark/reports/live_runtime_report.md` |

## Metrics

| CV/README metric | Value | Run ID | Evidence |
|---|---:|---|---|
| Held-out detector AP50 | 0.582020 | `phase04-heldout-yolov8m-docker-gpu-20260718-held_out_test-yolov8m` | `benchmark/reports/detection_summary.csv`, `benchmark/reports/detection_report.md` |
| Held-out detector recall | 0.679091 | `phase04-heldout-yolov8m-docker-gpu-20260718-held_out_test-yolov8m` | `benchmark/reports/detection_summary.csv`, `benchmark/reports/detection_report.md` |
| Held-out direct ByteTrack HOTA | 0.242433 | `e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718` | `benchmark/reports/end_to_end_summary.csv`, `benchmark/reports/end_to_end_report.md` |
| Held-out direct ByteTrack IDF1 | 0.284952 | `e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718` | `benchmark/reports/end_to_end_summary.csv`, `benchmark/reports/end_to_end_report.md` |
| Held-out direct ByteTrack ID switches | 42 | `e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718` | `benchmark/reports/end_to_end_summary.csv`, `benchmark/reports/end_to_end_report.md` |
| Held-out direct ByteTrack Event F1 | 0.942238 | `e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718` | `benchmark/reports/end_to_end_summary.csv`, `benchmark/reports/end_to_end_report.md` |
| Held-out direct ByteTrack WAPE | 0.050360 | `e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718` | `benchmark/reports/end_to_end_summary.csv`, `benchmark/reports/end_to_end_report.md` |
| Uploaded-video best measured FPS | 75.829 | `phase07-upload-runtime-bytetrack-production-docker-gpu-20260718-v2` | `benchmark/reports/batch_runtime_summary.csv`, `benchmark/reports/batch_runtime_report.md` |
| Uploaded-video best measured RTF | 3.033x | `phase07-upload-runtime-bytetrack-production-docker-gpu-20260718-v2` | `benchmark/reports/batch_runtime_summary.csv`, `benchmark/reports/batch_runtime_report.md` |
| Uploaded-video VRAM peak for best ByteTrack workload | 2878 MB | `phase07-upload-runtime-bytetrack-production-docker-gpu-20260718-v2` | `benchmark/reports/batch_runtime_summary.csv`, `benchmark/reports/batch_runtime_report.md` |
| Live processed/published FPS | 14.895 | `phase08-live-hls-30min-20260718` | `benchmark/reports/live_runtime_report.md`, `benchmark/predictions/live_runtime/phase08-live-hls-30min-20260718/live_runtime_summary.json` |
| Live dropped frames | 0 | `phase08-live-hls-30min-20260718` | `benchmark/reports/live_runtime_report.md`, `benchmark/reports/live_runtime_timeseries.csv` |
| Live frame age p95 | 0.9 ms | `phase08-live-hls-30min-20260718` | `benchmark/reports/live_runtime_report.md` |
| Live soak duration | 1803.284 s | `phase08-live-hls-30min-20260718` | `benchmark/reports/live_runtime_report.md` |
| Phase 09 tracker/live ablation and error taxonomy | Partial pass; ROI accuracy blocked | `phase09_analysis` | `benchmark/reports/ablation_report.md`, `benchmark/reports/error_taxonomy.csv` |

## Metrics Not Safe To Claim

| Claim to avoid | Reason |
|---|---|
| Motorcycle AP/recall/counting accuracy on UA-DETRAC | UA-DETRAC labels in this repo have no motorcycle-compatible class. |
| Live count accuracy | The YouTube/HLS source has no GT. |
| Full-stack solo ownership | Team project; personal ownership is AI/computer-vision pipeline. |
| Production re-tracker as best measured tracker | Direct ByteTrack performed better in held-out end-to-end metrics. |
| ROI accuracy improvement | Full-frame vs crop-ROI AP/Event F1/WAPE is blocked until crop ROI GT exists for the benchmark sequences. |
