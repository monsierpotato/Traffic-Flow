# Phase 04 Detection Benchmark

Status: PASS, STOP GATE reached on 2026-07-18.

Primary report:

- `docs/reports/phase-04-detection-benchmark.md`

Artifacts:

- `benchmark/detection_eval.py`
- `benchmark/predictions/detection/phase04-dev-model-comparison-docker-gpu-20260718/`
- `benchmark/predictions/detection/phase04-heldout-yolov8m-docker-gpu-20260718/`
- `benchmark/reports/detection_summary.csv`
- `benchmark/reports/detection_report.md`
- `benchmark/reports/model_selection.md`

Protocol:

- Development selection only used development split.
- Held-out test was run once with the selected model.
- Docker GPU sampled benchmark: `frame_stride=100`, `imgsz=640`, `device=0`.
- Runtime used `trafficflow:latest` with the repo mounted at `/workspace`; the compose API/worker containers do not mount the benchmark source tree.

Selected model:

- `models/yolov8m.pt`

Development:

| Model | Precision | Recall | AP50 | AP50-95 | p95 ms |
|---|---:|---:|---:|---:|---:|
| yolo11m.pt | 0.6939 | 0.7583 | 0.5680 | 0.4219 | 17.983 |
| yolov8n.pt | 0.6827 | 0.6507 | 0.5147 | 0.3595 | 16.688 |
| yolov8s.pt | 0.5957 | 0.7693 | 0.5500 | 0.4061 | 16.378 |
| yolov8m.pt | 0.6185 | 0.7987 | 0.5950 | 0.4352 | 18.468 |

Held-out selected model:

| Model | Precision | Recall | AP50 | AP50-95 | p95 ms |
|---|---:|---:|---:|---:|---:|
| yolov8m.pt | 0.7067 | 0.6791 | 0.5820 | 0.4463 | 17.918 |

Key weakness:

- `truck` is weak: held-out AP50 0.0962 and recall 0.1471.
- Do not claim motorcycle metrics because UA-DETRAC has no compatible motorcycle GT label in this benchmark.

Stop gate:

- Phase 04 report is complete. Phase 05 tracking benchmark waits for user review or explicit continuation.
