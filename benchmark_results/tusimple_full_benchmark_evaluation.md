# TuSimple Full Benchmark Evaluation

Date: 2026-05-25

## Dataset

- Dataset root: `data/tusimple_full_test`
- Label file: `data/tusimple_full_test/test_label.json`
- Test samples: 2782
- Image validation: 2782 / 2782 referenced images present
- Source: Kaggle `manideep1108/tusimple`, using `TUSimple/test_set` and `TUSimple/test_label.json`

## Validation

- Syntax check passed:
  - `scripts/run_tusimple_dataset.py`
  - `scripts/run_polylanenet_video.py`
  - `scripts/run_laneatt_video.py`
  - `scripts/lane_schema.py`
  - `scripts/visualize_overlay.py`
- Full benchmark completed for UFLD, PolyLaneNet, and LaneATT on CUDA.
- Google Sheet updated: `TuSimple Full 2026-05-25` tab.

## Results

| Model | Backbone | Samples | Precision | Recall | F1 | Lane count MAE | Mean matched distance | Inference ms | Total ms | FPS |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| UFLD | ResNet18 / TuSimple | 2782 | 0.9836 | 0.9261 | 0.9506 | 0.2886 | 8.40 px | 2.50 | 9.41 | 106.62 |
| PolyLaneNet | ResNet50 / TuSimple | 2782 | 0.8384 | 0.8496 | 0.8422 | 0.1600 | 15.21 px | 3.70 | 9.70 | 103.17 |
| LaneATT | ResNet18 / TuSimple | 2782 | 0.8780 | 0.9614 | 0.9103 | 0.4806 | 7.99 px | 3.21 | 9.27 | 108.39 |

## Output Files

UFLD:

- `benchmark_results/outputs/ufld/tusimple_full_test/ufld_tusimple_metrics.csv`
- `benchmark_results/outputs/ufld/tusimple_full_test/ufld_tusimple_predictions.jsonl`
- `benchmark_results/outputs/ufld/tusimple_full_test/ufld_tusimple_summary.md`
- `benchmark_results/outputs/ufld/tusimple_full_test/overlays/`

PolyLaneNet:

- `benchmark_results/outputs/polylanenet/tusimple_full_test/polylanenet_tusimple_metrics.csv`
- `benchmark_results/outputs/polylanenet/tusimple_full_test/polylanenet_tusimple_predictions.jsonl`
- `benchmark_results/outputs/polylanenet/tusimple_full_test/polylanenet_tusimple_summary.md`
- `benchmark_results/outputs/polylanenet/tusimple_full_test/overlays/`

LaneATT:

- `benchmark_results/outputs/laneatt/tusimple_full_test/laneatt_tusimple_metrics.csv`
- `benchmark_results/outputs/laneatt/tusimple_full_test/laneatt_tusimple_predictions.jsonl`
- `benchmark_results/outputs/laneatt/tusimple_full_test/laneatt_tusimple_summary.md`
- `benchmark_results/outputs/laneatt/tusimple_full_test/overlays/`

## Evaluation

UFLD is the strongest overall model on the full TuSimple test split in this local benchmark. It has the highest F1 and precision while staying close to LaneATT in total runtime.

LaneATT has the highest recall, lowest matched-lane distance, and highest FPS. PolyLaneNet has the lowest lane-count MAE but weaker F1 and geometry distance.

## Notes

- These metrics use the project evaluator in `scripts/run_tusimple_dataset.py` with a 40 px lane match threshold.
- This is not the official TuSimple server metric, but it is consistent across both models and useful for local comparison.
- UFLD was rerun on full TuSimple because the earlier UFLD notebook output only covered smoke samples and was not comparable.
