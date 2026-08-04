# Phase 05 Tracking Benchmark Report

Run date: 2026-07-18.

## Scope

Phase 05 evaluates identity stability independently from counting. This run uses oracle UA-DETRAC GT detections as tracker input so the result isolates association behavior from detector recall/precision errors.

## Evaluator

- Evaluator: `TrackEval 1.3.0`
- Dataset adapter: `MotChallenge2DBox`
- Metrics: HOTA, DetA, AssA, LocA, IDF1, MOTA, MOTP, ID switches, fragmentations, mostly tracked, mostly lost.
- Vehicle class encoding: all mapped UA-DETRAC vehicles are encoded as TrackEval `pedestrian` class id `1`, because MotChallenge2DBox only evaluates that class.

## Runs

Development ablation:

- `benchmark/predictions/tracking/phase05-dev-trackeval-oracle-20260718/`

Held-out selected tracker:

- `benchmark/predictions/tracking/phase05-heldout-iou-frame-oracle-20260718/`

Summary artifacts:

- `benchmark/reports/tracking_summary.csv`
- `benchmark/reports/tracking_ablation.csv`
- `benchmark/reports/tracking_error_examples.csv`

## Development Ablation

| Tracker | HOTA | DetA | AssA | IDF1 | MOTA | MOTP | IDSW | Frag | MT | ML |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| iou_frame | 0.999936 | 0.999991 | 0.999882 | 0.999949 | 0.999949 | 0.999994 | 5 | 0 | 1357 | 0 |
| trafficflow_kalman | 0.807351 | 0.831976 | 0.789103 | 0.892666 | 0.956087 | 0.874967 | 104 | 206 | 1299 | 3 |

Selected tracker on development:

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

Held-out was run once after development selection:

| Tracker | HOTA | DetA | AssA | IDF1 | MOTA | MOTP | IDSW | Frag | MT | ML |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| iou_frame | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0 | 0 | 509 | 0 |

## Error Examples

Examples recorded in `benchmark/reports/tracking_error_examples.csv`:

- `iou_frame`: `MVI_40752`, frame 272, GT track 28 changed predicted ID 25 -> 26.
- `trafficflow_kalman`: `MVI_20012`, frame 469, GT track 3 changed predicted ID 2 -> 15 at IoU 0.717.
- `trafficflow_kalman`: `MVI_20012`, frame 375, GT track 30 had a fragmentation event.

## Detection vs Association

This Phase 05 run uses oracle detections, so detector false positives and false negatives are intentionally removed. The ablation therefore measures association and output-box behavior. Phase 04 already identified the main detector weakness: `truck` AP/recall is low because UA-DETRAC `van` is mapped to TrafficFlow `truck`.

The production-style Kalman tracker is useful for live low-FPS detector gaps, but under exact GT detections its predicted/smoothed output is less aligned with GT boxes than a direct IoU tracker. This explains lower LocA/MOTP, higher ID switches, and fragmentations in the oracle setting.

## Acceptance Criteria

- Evaluator/version recorded: PASS.
- Conversion checked by TrackEval MOTChallenge input and `conversion_audit.csv`: PASS.
- Held-out test was not used for tuning: PASS.
- ID switch/fragmentation examples recorded: PASS.
- Detection error vs association error analyzed: PASS.

## Limitations

- This is not an end-to-end detector+tracker benchmark.
- Class-specific tracking is not claimed because MotChallenge2DBox was used as an all-vehicle adapter.
- The end-to-end follow-up is now available in `benchmark/reports/end_to_end_report.md`.

## End-to-End Follow-Up

On held-out full sequences, direct ByteTrack outperformed the current production re-tracker path:

- ByteTrack: HOTA 0.242433, IDF1 0.284952, IDSW 42.
- TrafficFlow production re-tracker: HOTA 0.215225, IDF1 0.224661, IDSW 169.

The oracle-detection result above remains useful for isolating association behavior with perfect detections, but production-facing tracker claims should cite the end-to-end report.
