# TuSimple Full 3-Model Comparison

Date: 2026-05-25

## Fairness Check

The previous UFLD outputs under `benchmark_results/trafficflow_notebooks/outputs/ufld/` were not comparable with the latest PolyLaneNet and LaneATT full-test runs. That notebook output contains 3 TuSimple smoke samples, while PolyLaneNet and LaneATT were rerun on the full `data/tusimple_full_test` split with 2782 samples.

UFLD was therefore rerun using the same dataset runner and evaluator:

- Dataset: `data/tusimple_full_test`
- Label file: `data/tusimple_full_test/test_label.json`
- Samples: 2782
- Referenced images present: 2782 / 2782
- Device: NVIDIA GeForce RTX 5070 Ti / CUDA
- Evaluator: `scripts/run_tusimple_dataset.py`
- Match threshold: 40 px

## Results

| Model | Backbone | Samples | Precision | Recall | F1 | Lane count MAE | Mean matched distance | Preprocess ms | Inference ms | Postprocess ms | Total ms | FPS |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| UFLD | ResNet18 / TuSimple | 2782 | 0.9836 | 0.9261 | 0.9506 | 0.2886 | 8.40 px | 6.52 | 2.50 | 0.39 | 9.41 | 106.62 |
| LaneATT | ResNet18 / TuSimple | 2782 | 0.8780 | 0.9614 | 0.9103 | 0.4806 | 7.99 px | 3.25 | 3.21 | 2.81 | 9.27 | 108.39 |
| PolyLaneNet | ResNet50 / TuSimple | 2782 | 0.8384 | 0.8496 | 0.8422 | 0.1600 | 15.21 px | 5.65 | 3.70 | 0.35 | 9.70 | 103.17 |

## Output Files

UFLD:

- `benchmark_results/outputs/ufld/tusimple_full_test/ufld_tusimple_metrics.csv`
- `benchmark_results/outputs/ufld/tusimple_full_test/ufld_tusimple_predictions.jsonl`
- `benchmark_results/outputs/ufld/tusimple_full_test/ufld_tusimple_summary.md`
- `benchmark_results/outputs/ufld/tusimple_full_test/overlays/`

LaneATT:

- `benchmark_results/outputs/laneatt/tusimple_full_test/laneatt_tusimple_metrics.csv`
- `benchmark_results/outputs/laneatt/tusimple_full_test/laneatt_tusimple_predictions.jsonl`
- `benchmark_results/outputs/laneatt/tusimple_full_test/laneatt_tusimple_summary.md`
- `benchmark_results/outputs/laneatt/tusimple_full_test/overlays/`

PolyLaneNet:

- `benchmark_results/outputs/polylanenet/tusimple_full_test/polylanenet_tusimple_metrics.csv`
- `benchmark_results/outputs/polylanenet/tusimple_full_test/polylanenet_tusimple_predictions.jsonl`
- `benchmark_results/outputs/polylanenet/tusimple_full_test/polylanenet_tusimple_summary.md`
- `benchmark_results/outputs/polylanenet/tusimple_full_test/overlays/`

## Evaluation

UFLD is the best overall full TuSimple result in this local benchmark. It has the highest precision and F1 while remaining essentially as fast as the other two models under the same dataset runner.

LaneATT has the highest recall, the lowest matched-lane distance, and the highest FPS. It is a strong second choice when recall and lane geometry smoothness matter more than false positives or lane count stability.

PolyLaneNet has the best lane-count MAE, but its F1 and matched-lane distance are weaker. Its polynomial output is useful for geometry experiments, but it is not the strongest full-test model here.

## Recommendation

For TrafficFlow's current lane-only benchmark, keep UFLD as the strongest baseline and practical default from the full TuSimple comparison. Keep LaneATT as the higher-recall candidate. Use PolyLaneNet only when explicit polynomial geometry is required or for ablation/comparison.

## Notes

- Metrics are from the local project evaluator, not the official TuSimple server.
- The evaluator is consistent across all three models and uses a 40 px lane match threshold.
- UFLD timing now includes preprocessing, inference, and postprocessing for fairer comparison with PolyLaneNet and LaneATT.
