# Phase 06 Counting Benchmark Report

Run date: 2026-07-18.

## Scope

Phase 06 evaluates counting-event metric plumbing for lane/class/direction traffic counts.

This run is an oracle counting benchmark: prediction events come from the Phase 03 GT-backed raw counting events, and GT events come from the Phase 02 derived counting ground truth. It validates event matching, aggregate counting metrics, consistency checks, and report traceability. It is not an end-to-end YOLO + tracker + counting result.

## Inputs

- GT events: `benchmark/ground_truth/derived_events/`
- Prediction events: `benchmark/runs/phase03-smoke-manual-geometry-20260718/raw_counting_events/`
- Split: `benchmark/splits/ua_detrac_split_v1.json`
- Buckets: `development`, `held_out_test`
- Temporal tolerance: 5 frames at nominal 25 FPS
- Geometry: manual source-frame lane configs from `benchmark/configs/geometry_manual/`

## Artifacts

- `benchmark/predictions/counting/phase06-oracle-counting-manual-geometry-20260718/events.jsonl`
- `benchmark/predictions/counting/phase06-oracle-counting-manual-geometry-20260718/counting_summary.csv`
- `benchmark/predictions/counting/phase06-oracle-counting-manual-geometry-20260718/counting_event_matches.csv`
- `benchmark/predictions/counting/phase06-oracle-counting-manual-geometry-20260718/counting_errors.csv`
- `benchmark/predictions/counting/phase06-oracle-counting-manual-geometry-20260718/counting_aggregate_units.csv`
- `benchmark/reports/counting_summary.csv`
- `benchmark/reports/counting_event_matches.csv`
- `benchmark/reports/counting_errors.csv`

## Headline Metrics

| Scope | Event P | Event R | Event F1 | WAPE | Bias | Duplicate rate | Miss rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| development | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| held_out_test | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Development

- GT events: 1136
- Prediction events: 1136
- TP/FP/FN: 1136 / 0 / 0
- MAE/RMSE/WAPE: 0.0000 / 0.0000 / 0.0000
- Exact-count accuracy: 1.0000
- Within-1 accuracy: 1.0000
- Median/p95 crossing-time error: 0 / 0 frames
- Wrong lane/class/direction rates: 0.0000 / 0.0000 / 0.0000

## Held-Out

- GT events: 278
- Prediction events: 278
- TP/FP/FN: 278 / 0 / 0
- MAE/RMSE/WAPE: 0.0000 / 0.0000 / 0.0000
- Exact-count accuracy: 1.0000
- Within-1 accuracy: 1.0000
- Median/p95 crossing-time error: 0 / 0 frames
- Wrong lane/class/direction rates: 0.0000 / 0.0000 / 0.0000

## Consistency

| Bucket | Accepted prediction events | Sum aggregate prediction counts | Consistent |
|---|---:|---:|---|
| development | 1136 | 1136 | true |
| held_out_test | 278 | 278 | true |

The reported total count equals the aggregate lane/class/direction counts and the number of accepted prediction events.

## Traceability

- `counting_event_matches.csv` contains one row per TP/FP/FN match record and can be filtered by bucket, video, lane, class, and direction.
- `counting_errors.csv` is empty except for the header in this oracle run because no FP/FN records were produced.
- `counting_aggregate_units.csv` contains the evaluation units: video x lane x class x direction.

## Acceptance Criteria

- Event-level and aggregate metrics: PASS.
- Duplicate and missed events surfaced separately: PASS.
- Wrong-lane and wrong-direction separated: PASS.
- Summary traces back to event match CSV: PASS.
- Held-out metrics marked clearly: PASS.

## Limitations

- This is an oracle counting benchmark using derived GT-backed prediction events.
- It does not measure detector misses, tracker ID switches, or YOLO-driven counting errors.
- The end-to-end follow-up is now available in `benchmark/reports/end_to_end_report.md`.

## End-to-End Follow-Up

On held-out full sequences, direct ByteTrack outperformed the current production re-tracker path:

- ByteTrack: Event F1 0.942238, WAPE 0.050360.
- TrafficFlow production re-tracker: Event F1 0.835294, WAPE 0.194245.

The oracle counting result above remains useful for validating evaluator plumbing. Production-facing counting claims should cite the end-to-end report.
