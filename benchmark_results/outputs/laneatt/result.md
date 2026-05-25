# LaneATT Result

Date: 2026-05-25

## Setup

- Repo: `repos/LaneATT`
- Source repo: `https://github.com/lucastabelini/LaneATT`
- Weight zip: `weights/laneatt/laneatt_experiments.zip`
- Extracted experiment: `weights/laneatt/extracted/experiments/laneatt_r18_tusimple`
- Weight: `weights/laneatt/extracted/experiments/laneatt_r18_tusimple/models/model_0100.pt`
- Config: `weights/laneatt/extracted/experiments/laneatt_r18_tusimple/config.yaml`
- Backbone: ResNet18
- Dataset head: TuSimple
- Device: GPU, NVIDIA GeForce RTX 5070 Ti
- Script: `scripts/run_laneatt_video.py`

## Outputs

- `benchmark_results/outputs/laneatt/fps.csv`
- `benchmark_results/outputs/laneatt/lane_output.jsonl`
- `benchmark_results/outputs/laneatt/traffic_01_overlay_gpu.mp4`
- `benchmark_results/outputs/laneatt/traffic_02_overlay_gpu.mp4`
- `benchmark_results/outputs/laneatt/traffic_03_overlay_gpu.mp4`

## FPS

| Video | Frames measured | Avg latency | Avg inference | P95 latency | FPS |
|---|---:|---:|---:|---:|---:|
| `traffic_01_time_lapse.mp4` | 632 | 7.112 ms | 2.918 ms | 8.914 ms | 140.60 |
| `traffic_02_clouds_highway.mp4` | 587 | 6.413 ms | 2.770 ms | 7.446 ms | 155.94 |
| `traffic_03_night_time_lapse.mp4` | 308 | 6.720 ms | 2.818 ms | 8.811 ms | 148.80 |

Average FPS: 148.45.

## Lane Output Stats

| Video | Frames | Avg lanes / frame | Frames with lane |
|---|---:|---:|---:|
| `traffic_01_time_lapse.mp4` | 637 | 1.63 | 526 |
| `traffic_02_clouds_highway.mp4` | 592 | 0.64 | 335 |
| `traffic_03_night_time_lapse.mp4` | 313 | 1.14 | 203 |

## TuSimple Dataset Run

The model was also run locally on the TuSimple-format datasets available in `data/`.

| Dataset | Samples | Precision | Recall | F1 | Lane count MAE | Mean matched distance | FPS |
|---|---:|---:|---:|---:|---:|---:|---:|
| `data/tusimple_full_test` | 2782 | 0.8780 | 0.9614 | 0.9103 | 0.4806 | 7.99 px | 108.39 |
| `data/tusimple_real_smoke` | 3 | 0.8667 | 1.0000 | 0.9259 | 0.6667 | 8.03 px | 94.46 |
| `data/tusimple_smoke` | 1 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | inf | 149.40 |

TuSimple outputs:

- `benchmark_results/outputs/laneatt/tusimple_full_test/`
- `benchmark_results/outputs/laneatt/tusimple_real_smoke/`
- `benchmark_results/outputs/laneatt/tusimple_smoke/`

## Notes

- This is a real pretrained LaneATT run, not a dummy benchmark.
- CUDA NMS is running locally in `.venv-gpu`.
- LaneATT is faster than PolyLaneNet on these videos, but still slower than UFLD.
- Visual quality is more conservative than PolyLaneNet and usually avoids full-frame crossing lanes, but it still hallucinates lane lines on the sky/highway stock clip and misses lanes in night frames.
- Keep LaneATT as the third runnable benchmark method, but validate on Bellevue CCTV before choosing it for TrafficFlow.
