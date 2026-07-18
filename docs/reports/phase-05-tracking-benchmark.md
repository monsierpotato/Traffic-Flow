# Phase 05 - Tracking Benchmark

## Status

PASS, STOP GATE reached on 2026-07-18.

Phase 05 ran an identity-tracking benchmark with TrackEval over UA-DETRAC selected sequences. The benchmark uses oracle GT detections to isolate association behavior from detector errors.

## Outputs

- `benchmark/tracking_eval.py`
- `benchmark/predictions/tracking/phase05-smoke-trackeval-20260718/`
- `benchmark/predictions/tracking/phase05-dev-trackeval-oracle-20260718/`
- `benchmark/predictions/tracking/phase05-heldout-iou-frame-oracle-20260718/`
- `benchmark/reports/tracking_report.md`
- `benchmark/reports/tracking_summary.csv`
- `benchmark/reports/tracking_ablation.csv`
- `benchmark/reports/tracking_error_examples.csv`
- `docs/portfolio/tracking-design.md`
- `docs/reports/phase-05-tracking-benchmark.md`
- `docs/wiki/ai-workflow/phase-05-tracking-benchmark.md`

## Evaluator

- `TrackEval 1.3.0`
- Adapter: `MotChallenge2DBox`
- Metrics: HOTA, DetA, AssA, LocA, IDF1, MOTA, MOTP, ID switches, fragmentations, mostly tracked, mostly lost.

All mapped UA-DETRAC vehicle classes are encoded as TrackEval class id `1` because MotChallenge2DBox only evaluates the `pedestrian` class. This is an all-vehicle identity benchmark.

## Development Ablation

| Tracker | HOTA | DetA | AssA | IDF1 | MOTA | MOTP | IDSW | Frag |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| iou_frame | 0.999936 | 0.999991 | 0.999882 | 0.999949 | 0.999949 | 0.999994 | 5 | 0 |
| trafficflow_kalman | 0.807351 | 0.831976 | 0.789103 | 0.892666 | 0.956087 | 0.874967 | 104 | 206 |

Selected tracker from development:

- `iou_frame`

## Frozen Tracker Config

| Field | Value |
|---|---|
| state model | frame-based bbox memory |
| association cost weights | IoU only |
| IoU gate | 0.3 |
| center-distance gate | disabled |
| class consistency | true |
| min_hits | 1 |
| track_buffer | 8 |
| max_lost_seconds | disabled |
| reset_gap_seconds | disabled |

## Held-Out Result

Held-out was run once with the selected tracker:

| Tracker | HOTA | DetA | AssA | IDF1 | MOTA | MOTP | IDSW | Frag |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| iou_frame | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0 | 0 |

## Examples

- `iou_frame`: `MVI_40752`, frame 272, GT track 28 changed predicted ID 25 -> 26.
- `trafficflow_kalman`: `MVI_20012`, frame 469, GT track 3 changed predicted ID 2 -> 15.
- `trafficflow_kalman`: `MVI_20012`, frame 375, GT track 30 had a fragmentation event.

## Interpretation

With oracle GT detections, IoU-only association is almost perfect. The production-style Kalman tracker is designed for live low-FPS detector gaps, but its predicted/smoothed output lowers localization and association metrics when exact GT boxes are available every frame.

Detection error is not measured here. Phase 04 identified detector weakness separately, especially for `truck`.

## Validation

- Phase 05 smoke TrackEval run: PASS.
- Development ablation: PASS.
- Held-out selected tracker run: PASS.
- `python -m pytest tests -q`: PASS, 162 passed, 1 existing warning.
- `python -m compileall -q src benchmark`: PASS.
- `git diff --check`: PASS, with Windows line-ending warnings only.

## Stop Gate

Per plan, Phase 05 stops here after report creation. Phase 06 counting benchmark should start only after user review or explicit continuation.

## End-to-End Follow-Up

Production-facing tracker comparison is now reported in `docs/reports/end-to-end-bytetrack-production-comparison.md`.

Held-out direct ByteTrack outperformed the current production re-tracker path: HOTA 0.242433 vs 0.215225, IDF1 0.284952 vs 0.224661, IDSW 42 vs 169.
