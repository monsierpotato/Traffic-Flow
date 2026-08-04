# Phase 04 Detection Benchmark Report

Run date: 2026-07-18.

## Scope

Phase 04 evaluates detector quality independently from tracking and counting. The run used the frozen UA-DETRAC v1 split and mapped classes:

- `car -> car`
- `bus -> bus`
- `van -> truck`
- `others -> ignored`

No motorcycle metric is reported because the local UA-DETRAC annotations do not include a motorcycle-compatible GT class.

## Runs

Development model comparison:

- `benchmark/predictions/detection/phase04-dev-model-comparison-docker-gpu-20260718/`

Held-out selected-model run:

- `benchmark/predictions/detection/phase04-heldout-yolov8m-docker-gpu-20260718/`

Summary CSV:

- `benchmark/reports/detection_summary.csv`

Model selection:

- `benchmark/reports/model_selection.md`

## Method

- Device: Docker GPU, `device=0`.
- Runtime: `trafficflow:latest` with the repo mounted at `/workspace`.
- GPU: NVIDIA GeForce RTX 5070 Ti visible from container PyTorch.
- Sampling: every 100th frame per sequence.
- Development sample: 131 frames.
- Held-out sample: 85 frames.
- Image size: 640.
- Confidence floor for AP: 0.001.
- Operating threshold: 0.4.
- Operating IoU threshold: 0.5.
- Latency: wall-clock model prediction time after warmup.
- Peak VRAM: measured from CUDA memory in the benchmark container.

The sampled GPU protocol is reproducible and separates development from held-out data. It is a sampled detector benchmark, not a full-video throughput benchmark.

## Development Comparison

| Model | Imgsz | Precision | Recall | F1 | AP50 | AP50-95 | FP/frame | FN/frame | Infer p95 ms | VRAM MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| yolo11m.pt | 640 | 0.6939 | 0.7583 | 0.7246 | 0.5680 | 0.4219 | 2.7786 | 2.0076 | 17.983 | 185 |
| yolov8n.pt | 640 | 0.6827 | 0.6507 | 0.6664 | 0.5147 | 0.3595 | 2.5115 | 2.9008 | 16.688 | 185 |
| yolov8s.pt | 640 | 0.5957 | 0.7693 | 0.6715 | 0.5500 | 0.4061 | 4.3359 | 1.9160 | 16.378 | 185 |
| yolov8m.pt | 640 | 0.6185 | 0.7987 | 0.6972 | 0.5950 | 0.4352 | 4.0916 | 1.6718 | 18.468 | 236 |

## Held-Out Result

Selected model: `models/yolov8m.pt`.

| Model | Imgsz | Precision | Recall | F1 | AP50 | AP50-95 | FP/frame | FN/frame | Infer p95 ms | VRAM MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| yolov8m.pt | 640 | 0.7067 | 0.6791 | 0.6926 | 0.5820 | 0.4463 | 3.6471 | 4.1529 | 17.918 | 160 |

## Per-Class Weakness

Held-out per-class operating metrics for `yolov8m.pt`:

| Class | AP50 | AP50-95 | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| car | 0.7511 | 0.5410 | 0.7225 | 0.6963 | 0.7092 |
| bus | 0.8988 | 0.7263 | 0.7288 | 0.8866 | 0.8000 |
| truck | 0.0962 | 0.0715 | 0.2632 | 0.1471 | 0.1887 |

The detector is weak on `truck`; this mostly reflects the UA-DETRAC `van -> truck` mapping and should be considered before interpreting downstream truck counts.

## Acceptance Criteria

- Development and held-out results are separated: PASS.
- Model selected from development only: PASS.
- Held-out run executed once with the selected model: PASS.
- Per-class weakness analyzed: PASS.
- No unsupported motorcycle metric claimed: PASS.
- Every result has a run ID: PASS.

## Limitations

- This is a sampled Docker GPU benchmark; it does not cover full-video throughput or live-pipeline FPS.
- The compose API/worker containers do not mount the benchmark source tree, so reruns should use `docker run --rm --gpus all -v "${PWD}:/workspace" -w /workspace trafficflow:latest ...`.
- Phase 04 does not evaluate tracking identity or final counting accuracy; those start in Phase 05+.
