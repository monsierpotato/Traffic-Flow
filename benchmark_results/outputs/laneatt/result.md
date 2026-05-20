# LaneATT Result

Date: 2026-05-19

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
| `traffic_01_time_lapse.mp4` | 632 | 8.158 ms | 3.932 ms | 10.388 ms | 122.58 |
| `traffic_02_clouds_highway.mp4` | 587 | 7.271 ms | 3.871 ms | 8.707 ms | 137.53 |
| `traffic_03_night_time_lapse.mp4` | 308 | 7.663 ms | 3.964 ms | 10.449 ms | 130.50 |

Average FPS: 130.20.

## Lane Output Stats

| Video | Frames | Avg lanes / frame | Frames with lane |
|---|---:|---:|---:|
| `traffic_01_time_lapse.mp4` | 637 | 1.63 | 526 |
| `traffic_02_clouds_highway.mp4` | 592 | 0.64 | 335 |
| `traffic_03_night_time_lapse.mp4` | 313 | 1.14 | 203 |

## Notes

- This is a real pretrained LaneATT run, not a dummy benchmark.
- CUDA NMS is running locally in `.venv-gpu`.
- LaneATT is faster than PolyLaneNet on these videos, but still slower than UFLD.
- Visual quality is more conservative than PolyLaneNet and usually avoids full-frame crossing lanes, but it still hallucinates lane lines on the sky/highway stock clip and misses lanes in night frames.
- Keep LaneATT as the third runnable benchmark method, but validate on Bellevue CCTV before choosing it for TrafficFlow.
