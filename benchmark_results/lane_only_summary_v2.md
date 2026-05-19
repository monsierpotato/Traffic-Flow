# Lane-only Benchmark Summary v2

## Environment

- OS: Windows 11
- Python: 3.10.9 (`.venv-gpu`)
- PyTorch: 2.12.0+cu130
- CUDA runtime: 13.0 via PyTorch
- CUDA Toolkit: 13.2 (`nvcc V13.2.78`)
- GPU: NVIDIA GeForce RTX 5070 Ti, 16 GB VRAM
- RAM: 31.4 GB

## Method Status

| Method | Status | Reason |
|---|---|---|
| UFLD | Passed | Ran on 3 local videos with GPU |
| PolyLaneNet | Passed / weak quality | Ran on 3 local videos with GPU; output is geometry-friendly but qualitatively unstable on current clips |
| ENet-SAD | Blocked | Official pretrained model is Torch7 `.t7`; PyTorch reimplementation has no matching pretrained checkpoint |
| LaneATT | Passed as replacement | Ran on 3 local videos with GPU after CUDA NMS build |
| CLRNet | Optional | Accuracy-oriented, timebox only |
| UFLDv2 | Optional / blocked | DALI/env friction on Windows native |

## FPS

| Method | Video 1 FPS | Video 2 FPS | Video 3 FPS | Avg FPS | Avg latency | Device |
|---|---:|---:|---:|---:|---:|---|
| UFLD ResNet18 / TuSimple | 313.92 | 309.98 | 303.40 | 309.10 | 3.24 ms | RTX 5070 Ti |
| PolyLaneNet ResNet50 / TuSimple | 106.17 | 102.61 | 107.21 | 105.33 | 9.50 ms | RTX 5070 Ti |
| LaneATT ResNet18 / TuSimple | 122.58 | 137.53 | 130.50 | 130.20 | 7.70 ms | RTX 5070 Ti |
| ENet-SAD |  |  |  |  |  | Blocked |

## UFLD Lane Output

| Video | Frames | Avg lanes / frame | Frames with lane |
|---|---:|---:|---:|
| `traffic_01_time_lapse.mp4` | 637 | 1.72 | 636 |
| `traffic_02_clouds_highway.mp4` | 592 | 0.71 | 379 |
| `traffic_03_night_time_lapse.mp4` | 313 | 2.01 | 313 |

Normalized output:

```text
benchmark_results/outputs/ufld/lane_output.jsonl
```

## PolyLaneNet Lane Output

| Video | Frames | Avg lanes / frame | Frames with lane |
|---|---:|---:|---:|
| `traffic_01_time_lapse.mp4` | 637 | 4.00 | 637 |
| `traffic_02_clouds_highway.mp4` | 592 | 3.28 | 592 |
| `traffic_03_night_time_lapse.mp4` | 313 | 3.13 | 313 |

Normalized output:

```text
benchmark_results/outputs/polylanenet/lane_output.jsonl
```

Qualitative note: PolyLaneNet runs and produces polynomial lanes, but visual overlays show frequent hallucinated or crossing lanes on these stock/time-lapse clips. This is likely TuSimple dashcam domain shift.

## LaneATT Lane Output

| Video | Frames | Avg lanes / frame | Frames with lane |
|---|---:|---:|---:|
| `traffic_01_time_lapse.mp4` | 637 | 1.63 | 526 |
| `traffic_02_clouds_highway.mp4` | 592 | 0.64 | 335 |
| `traffic_03_night_time_lapse.mp4` | 313 | 1.14 | 203 |

Normalized output:

```text
benchmark_results/outputs/laneatt/lane_output.jsonl
```

Qualitative note: LaneATT is more conservative than PolyLaneNet and avoids many full-frame crossing artifacts, but still hallucinates lane lines on the sky/highway stock clip and misses lanes in difficult night frames.

## Qualitative Score

| Method | Visibility | Stability | Occlusion | Night | CCTV suitability | Integration | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| UFLD | 3 | 3 | 2 | 2 | 2 | 3 | 15 |
| PolyLaneNet | 2 | 1 | 1 | 1 | 1 | 4 | 10 |
| LaneATT | 2 | 3 | 2 | 2 | 2 | 3 | 14 |
| ENet-SAD |  |  |  |  |  |  | Blocked |

## Final Decision

- Main lane-only model: UFLD for current smoke benchmark; re-evaluate UFLD vs LaneATT on Bellevue CCTV sample.
- Speed baseline: UFLD
- Optional accuracy model: LaneATT
- Fallback for production: Manual lane polygon + bottom-center point
- Reason: UFLD is fastest and visually more stable on the current smoke videos. LaneATT is the third runnable method after CUDA setup and is more usable than PolyLaneNet qualitatively. PolyLaneNet is easiest to express as geometry, but current pretrained output is not stable enough on these clips.

## Next Steps

1. Download a small Bellevue CCTV sample before final qualitative scoring.
2. Re-run UFLD and LaneATT on Bellevue.
3. Use manual lane polygons as production fallback for fixed CCTV cameras.
