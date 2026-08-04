# Phase 05 Tracking Benchmark

Status: PASS, STOP GATE reached on 2026-07-18.

Primary report:

- `docs/reports/phase-05-tracking-benchmark.md`

Artifacts:

- `benchmark/tracking_eval.py`
- `benchmark/predictions/tracking/phase05-dev-trackeval-oracle-20260718/`
- `benchmark/predictions/tracking/phase05-heldout-iou-frame-oracle-20260718/`
- `benchmark/reports/tracking_report.md`
- `benchmark/reports/tracking_summary.csv`
- `benchmark/reports/tracking_ablation.csv`
- `benchmark/reports/tracking_error_examples.csv`
- `docs/portfolio/tracking-design.md`

Evaluator:

- `TrackEval 1.3.0 MotChallenge2DBox`

Development:

| Tracker | HOTA | DetA | AssA | IDF1 | IDSW | Frag |
|---|---:|---:|---:|---:|---:|---:|
| iou_frame | 0.999936 | 0.999991 | 0.999882 | 0.999949 | 5 | 0 |
| trafficflow_kalman | 0.807351 | 0.831976 | 0.789103 | 0.892666 | 104 | 206 |

Held-out selected tracker:

| Tracker | HOTA | DetA | AssA | IDF1 | IDSW | Frag |
|---|---:|---:|---:|---:|---:|---:|
| iou_frame | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0 | 0 |

Notes:

- Input source is oracle UA-DETRAC GT detections, so Phase 05 isolates association behavior from detector error.
- All vehicles are encoded as TrackEval class id `1` because MotChallenge2DBox only evaluates `pedestrian`.
- Phase 06 counting benchmark waits for user review or explicit continuation.

End-to-end follow-up:

- Production-facing tracker comparison is now reported in [[End-to-End ByteTrack Production Comparison]].
- Held-out direct ByteTrack outperformed the current production re-tracker path: HOTA 0.242433 vs 0.215225, IDF1 0.284952 vs 0.224661, IDSW 42 vs 169.
