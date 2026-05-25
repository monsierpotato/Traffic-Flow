# UFLD / UFLDv2 Result

- Weight: `weights/ufld_tusimple_18.pth`
- Source: Hugging Face mirror `jkdxbns/autonomous-driving-carla/tusimple_18.pth`
- Variant: UFLD ResNet18, TuSimple head
- Device: RTX 5070 Ti GPU via `.venv-gpu` / PyTorch `2.12.0+cu130`

## FPS

| Video | Frames measured | Avg latency ms | P95 latency ms | FPS |
|---|---:|---:|---:|---:|
| `traffic_01_time_lapse.mp4` | 632 | 3.185 | 4.067 | 313.92 |
| `traffic_02_clouds_highway.mp4` | 587 | 3.226 | 4.146 | 309.98 |
| `traffic_03_night_time_lapse.mp4` | 308 | 3.296 | 4.497 | 303.40 |

## Lane Output

| Video | Frames | Avg lanes / frame | Frames with lane |
|---|---:|---:|---:|
| `traffic_01_time_lapse.mp4` | 637 | 1.72 | 636 |
| `traffic_02_clouds_highway.mp4` | 592 | 0.70 | 378 |
| `traffic_03_night_time_lapse.mp4` | 313 | 2.01 | 313 |

## Outputs

- `benchmark_results/outputs/ufld/traffic_01_overlay_gpu.mp4`
- `benchmark_results/outputs/ufld/traffic_02_overlay_gpu.mp4`
- `benchmark_results/outputs/ufld/traffic_03_overlay_gpu.mp4`
- `benchmark_results/outputs/ufld/traffic_01_lanes_gpu.jsonl`
- `benchmark_results/outputs/ufld/traffic_02_lanes_gpu.jsonl`
- `benchmark_results/outputs/ufld/traffic_03_lanes_gpu.jsonl`

## TuSimple Full Dataset Run

UFLD was rerun on the full TuSimple test split for fair comparison with PolyLaneNet and LaneATT.

| Dataset | Samples | Precision | Recall | F1 | Lane count MAE | Mean matched distance | FPS |
|---|---:|---:|---:|---:|---:|---:|---:|
| `data/tusimple_full_test` | 2782 | 0.9836 | 0.9261 | 0.9506 | 0.2886 | 8.40 px | 106.62 |

Full-test outputs:

- `benchmark_results/outputs/ufld/tusimple_full_test/`

## Notes

- This is a real pretrained UFLD run.
- FPS is inference-only and uses `torch.cuda.synchronize()` before/after model forward pass.
- Quality is only a smoke test because the videos are stock/time-lapse, not fixed CCTV.
