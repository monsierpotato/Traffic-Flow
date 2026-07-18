# Phase 04 - Detection Benchmark and Model Selection

## Status

PASS, STOP GATE reached on 2026-07-18.

Phase 04 ran a detector-only benchmark on the frozen UA-DETRAC v1 split. Development and held-out results are separated. The held-out split was used once after selecting the model on development.

## Outputs

- `benchmark/detection_eval.py`
- `benchmark/predictions/detection/phase04-dev-model-comparison-docker-gpu-20260718/`
- `benchmark/predictions/detection/phase04-heldout-yolov8m-docker-gpu-20260718/`
- `benchmark/reports/detection_summary.csv`
- `benchmark/reports/detection_report.md`
- `benchmark/reports/model_selection.md`
- `docs/reports/phase-04-detection-benchmark.md`
- `docs/wiki/ai-workflow/phase-04-detection-benchmark.md`

## Environment

- Device: Docker GPU, `device=0`.
- Runtime: `trafficflow:latest` with the repo mounted at `/workspace`.
- GPU: NVIDIA GeForce RTX 5070 Ti visible from container PyTorch.
- Sampling: `frame_stride=100`.
- Image size: 640.
- Confidence floor for AP: 0.001.
- Operating threshold: 0.4.
- Operating IoU threshold: 0.5.

This is a reproducible sampled Docker GPU benchmark. It is not a full-video throughput claim.

## Development Model Comparison

| Model | Imgsz | Precision | Recall | F1 | AP50 | AP50-95 | Infer p95 ms | VRAM MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| yolo11m.pt | 640 | 0.6939 | 0.7583 | 0.7246 | 0.5680 | 0.4219 | 17.983 | 185 |
| yolov8n.pt | 640 | 0.6827 | 0.6507 | 0.6664 | 0.5147 | 0.3595 | 16.688 | 185 |
| yolov8s.pt | 640 | 0.5957 | 0.7693 | 0.6715 | 0.5500 | 0.4061 | 16.378 | 185 |
| yolov8m.pt | 640 | 0.6185 | 0.7987 | 0.6972 | 0.5950 | 0.4352 | 18.468 | 236 |

## Selected Model

Selected model: `models/yolov8m.pt`.

Reason:

- Highest development AP50 and AP50-95.
- Highest development recall.
- Docker GPU p95 latency is 18.468 ms on the sampled development run.

## Held-Out Result

| Model | Imgsz | Precision | Recall | F1 | AP50 | AP50-95 | Infer p95 ms | VRAM MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| yolov8m.pt | 640 | 0.7067 | 0.6791 | 0.6926 | 0.5820 | 0.4463 | 17.918 | 160 |

## Weakness

The weakest class is `truck`:

- Development truck AP50: 0.0929, recall: 0.1653.
- Held-out truck AP50: 0.0962, recall: 0.1471.

This is important because UA-DETRAC `van` is mapped to TrafficFlow `truck`. Downstream truck counting should be interpreted with this detector weakness in mind.

## Validation

- Phase 04 smoke run: PASS.
- Development model comparison: PASS.
- Held-out selected-model run: PASS.
- Docker GPU verification: PASS, container PyTorch sees NVIDIA GeForce RTX 5070 Ti.
- `python -m pytest tests -q`: PASS, 162 passed, 1 existing warning after Phase 05 additions.
- `python -m compileall -q src benchmark`: PASS.
- `git diff --check`: PASS, with Windows line-ending warnings only.

## Stop Gate

Per plan, Phase 04 stops here after report creation. Phase 05 tracking benchmark should start only after user review or explicit continuation.
