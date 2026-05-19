# PolyLaneNet Result

Date: 2026-05-19

## Setup

- Repo: `repos/PolyLaneNet`
- Source repo: `https://github.com/lucastabelini/PolyLaneNet`
- Weight: `weights/polylanenet/tusimple/models/model_2695.pt`
- Config used: `repos/PolyLaneNet/cfgs/tusimple_resnet50.yaml`
- Backbone: ResNet50
- Dataset head: TuSimple
- Device: GPU, NVIDIA GeForce RTX 5070 Ti
- Script: `scripts/run_polylanenet_video.py`

The downloaded checkpoint is a ResNet50 checkpoint. It loads cleanly into
`PolyRegression(num_outputs=35, backbone="resnet50")`.

## Outputs

- `benchmark_results/outputs/polylanenet/fps.csv`
- `benchmark_results/outputs/polylanenet/lane_output.jsonl`
- `benchmark_results/outputs/polylanenet/traffic_01_overlay_gpu.mp4`
- `benchmark_results/outputs/polylanenet/traffic_02_overlay_gpu.mp4`
- `benchmark_results/outputs/polylanenet/traffic_03_overlay_gpu.mp4`

## FPS

| Video | Frames measured | Avg latency | Avg inference | P95 latency | FPS |
|---|---:|---:|---:|---:|---:|
| `traffic_01_time_lapse.mp4` | 632 | 9.419 ms | 4.897 ms | 9.903 ms | 106.17 |
| `traffic_02_clouds_highway.mp4` | 587 | 9.746 ms | 5.087 ms | 10.659 ms | 102.61 |
| `traffic_03_night_time_lapse.mp4` | 308 | 9.327 ms | 4.819 ms | 9.792 ms | 107.21 |

Average FPS: 105.33.

## Lane Output Stats

| Video | Frames | Avg lanes / frame | Frames with lane |
|---|---:|---:|---:|
| `traffic_01_time_lapse.mp4` | 637 | 4.00 | 637 |
| `traffic_02_clouds_highway.mp4` | 592 | 3.28 | 592 |
| `traffic_03_night_time_lapse.mp4` | 313 | 3.13 | 313 |

## Notes

- This is a real pretrained PolyLaneNet run, not a dummy benchmark.
- Output is converted from polynomial coefficients to the shared polyline schema.
- The model is fast enough for benchmark use, but qualitative quality is weak on the current stock/time-lapse videos.
- Visual inspection shows frequent hallucinated lanes and crossing lane lines, especially on the sky/highway clip and night clip.
- This is likely domain shift: the pretrained head is TuSimple dashcam-oriented, while the local clips are stock/time-lapse and not CCTV benchmark samples.

## Current Decision

PolyLaneNet remains useful for demonstrating a geometry-friendly lane-only method, but should not be selected as the TrafficFlow production lane source from these three videos alone. Keep UFLD as the stronger speed baseline for now, and continue with ENet-SAD before final selection.
