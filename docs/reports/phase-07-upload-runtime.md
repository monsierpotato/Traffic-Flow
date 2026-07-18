# Phase 07 Uploaded-Video Runtime Benchmark

- Run ID: `phase07-upload-runtime-bytetrack-production-docker-gpu-20260718-v2`
- Created: `2026-07-18T07:56:06`
- Model: `models/yolov8m.pt`
- Geometry: `benchmark/configs/geometry_manual`
- Variants: `bytetrack, trafficflow_production`
- Warmup policy: first `10` frames per result are marked `warmup`; latency p50/p95 below use steady-state rows.

## Results

| Workload | Variant | Input | Frames | FPS | RTF | Infer p95 ms | Total p95 ms | GPU avg/p95 % | VRAM peak MB | CPU avg/p95 % | RAM peak MB |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: |
| short_MVI_20035 | bytetrack | 960x540 @ 25.0 fps | 800 | 60.093 | 2.404 | 10.766 | 15.364 | 28.917/40.0 | 2558.0 | 5.275/6.4 | 2518.453 |
| short_MVI_20035 | trafficflow_production | 960x540 @ 25.0 fps | 800 | 70.446 | 2.818 | 10.169 | 15.23 | 34.4/39.55 | 2668.0 | 5.27/5.9 | 2638.105 |
| short_MVI_20012 | bytetrack | 960x540 @ 25.0 fps | 936 | 73.324 | 2.933 | 10.232 | 15.292 | 35.417/40.0 | 2668.0 | 5.2/5.68 | 2662.574 |
| short_MVI_20012 | trafficflow_production | 960x540 @ 25.0 fps | 936 | 72.498 | 2.9 | 10.308 | 15.5 | 36.667/39.45 | 2674.0 | 5.142/5.68 | 2667.492 |
| available_max_MVI_40241 | bytetrack | 960x540 @ 25.0 fps | 2320 | 75.829 | 3.033 | 10.326 | 14.782 | 38.222/41.0 | 2878.0 | 5.115/5.78 | 2658.008 |
| available_max_MVI_40241 | trafficflow_production | 960x540 @ 25.0 fps | 2320 | 75.846 | 3.034 | 9.945 | 15.018 | 37.481/41.0 | 2942.0 | 5.244/5.97 | 2673.852 |

## Scope Notes

- FPS is measured over the full local uploaded-video AI path: decode, full-frame resize/letterbox, YOLO/ByteTrack inference, lane/class filter, optional TrafficFlow `LocalTracker`, counting, overlay render, and output-video encode.
- UA-DETRAC local benchmark videos are 960x540. No benchmark-safe 1080p upload input or 3-5 minute/10+ minute source video was present in the frozen split, so this run reports available short/extended-short inputs only.
- `bytetrack` means Ultralytics YOLO `model.track(..., tracker="bytetrack.yaml")` plus lane filter/counting. `trafficflow_production` adds TrafficFlow `LocalTracker` after ByteTrack detections, matching the current upload path candidate measured earlier.

## Artifacts

- `benchmark/reports/batch_runtime_summary.csv`
- `benchmark/reports/stage_latency.csv`
- `benchmark/reports/resource_usage.csv`
- Run manifests: `benchmark/predictions/runtime/phase07-upload-runtime-bytetrack-production-docker-gpu-20260718-v2/manifests/`
- Overlay videos: `benchmark/predictions/runtime/phase07-upload-runtime-bytetrack-production-docker-gpu-20260718-v2/overlays/`

## Gate

Phase 07 report is complete. Per plan, stop before Phase 08 live/HLS soak unless the user confirms a stable live source and duration.
