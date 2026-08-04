# Phase 04 Model Selection

Selection date: 2026-07-18.

## Candidate Set

Only local models already present on disk were used:

- `models/yolo11m.pt`
- `models/yolov8n.pt`
- `models/yolov8s.pt`
- `models/yolov8m.pt`

No model was downloaded during Phase 04.

## Protocol

- Split used for selection: `development`.
- Held-out split was not used until after the model was selected.
- Device: Docker GPU, `device=0`.
- Runtime: `trafficflow:latest` with the repo mounted at `/workspace`.
- Sampling: `frame_stride=100`.
- Image size: 640.
- Confidence floor for AP: 0.001.
- Operating threshold for precision/recall/F1: 0.4.
- IoU threshold for operating metrics: 0.5.

This is a sampled Docker GPU benchmark. It is valid for a reproducible detector quality comparison under the sampled protocol, but it is not a full-video throughput claim.

## Development Results

| Model | Imgsz | Precision | Recall | F1 | AP50 | AP50-95 | Infer p95 ms | VRAM MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| yolo11m.pt | 640 | 0.6939 | 0.7583 | 0.7246 | 0.5680 | 0.4219 | 17.983 | 185 |
| yolov8n.pt | 640 | 0.6827 | 0.6507 | 0.6664 | 0.5147 | 0.3595 | 16.688 | 185 |
| yolov8s.pt | 640 | 0.5957 | 0.7693 | 0.6715 | 0.5500 | 0.4061 | 16.378 | 185 |
| yolov8m.pt | 640 | 0.6185 | 0.7987 | 0.6972 | 0.5950 | 0.4352 | 18.468 | 236 |

## Selection

Selected model: `models/yolov8m.pt`.

Reason:

- Highest development AP50: 0.5950.
- Highest development AP50-95: 0.4352.
- Highest development recall: 0.7987.
- Docker GPU p95 latency is close to the other medium-sized candidates at 18.468 ms.

`yolo11m.pt` had the best development F1 and precision, so it remains a credible runtime baseline. For Phase 04 detector selection, AP and recall are weighted higher because missed vehicles are more damaging for downstream tracking/counting than duplicate detections that tracking can sometimes absorb.

## Held-Out Result

Held-out was run once with the selected model only:

| Model | Imgsz | Precision | Recall | F1 | AP50 | AP50-95 | Infer p95 ms | VRAM MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| yolov8m.pt | 640 | 0.7067 | 0.6791 | 0.6926 | 0.5820 | 0.4463 | 17.918 | 160 |

## Weakness

The weakest mapped class is `truck`, which includes UA-DETRAC `van` mapped into TrafficFlow `truck`.

Development `yolov8m.pt`:

- car AP50: 0.8075, recall: 0.8778
- bus AP50: 0.8847, recall: 0.8824
- truck AP50: 0.0929, recall: 0.1653

Held-out `yolov8m.pt`:

- car AP50: 0.7511, recall: 0.6963
- bus AP50: 0.8988, recall: 0.8866
- truck AP50: 0.0962, recall: 0.1471

Do not claim motorcycle metrics for this benchmark because the UA-DETRAC annotations available here do not provide a motorcycle-compatible GT label.
