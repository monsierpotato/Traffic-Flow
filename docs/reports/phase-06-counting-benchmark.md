# Phase 06 - Counting Benchmark

## Status

PASS, STOP GATE reached on 2026-07-18.

Phase 06 added a counting-specific evaluator and ran an oracle counting benchmark on the frozen UA-DETRAC v1 split with manual geometry. Development and held-out metrics are reported separately.

## Outputs

- `benchmark/counting_eval.py`
- `tests/test_counting_eval.py`
- `benchmark/predictions/counting/phase06-oracle-counting-manual-geometry-20260718/`
- `benchmark/reports/counting_report.md`
- `benchmark/reports/counting_summary.csv`
- `benchmark/reports/counting_event_matches.csv`
- `benchmark/reports/counting_errors.csv`
- `docs/reports/phase-06-counting-benchmark.md`
- `docs/wiki/ai-workflow/phase-06-counting-benchmark.md`

## Method

- GT events: `benchmark/ground_truth/derived_events/`
- Prediction events: `benchmark/runs/phase03-smoke-manual-geometry-20260718/raw_counting_events/`
- Matching: one-to-one event matching by video, lane, class, direction, and temporal tolerance.
- Temporal tolerance: 5 frames.
- Aggregate unit: video x lane x class x direction.
- Input source: `phase03_derived_gt_smoke_oracle_counting_events`.

This is an oracle counting benchmark, not an end-to-end YOLO + tracker + counting result.

## Headline Metrics

| Scope | Event P | Event R | Event F1 | WAPE | Bias | Duplicate rate | Miss rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| development | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| held_out_test | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Details

| Bucket | GT events | Pred events | TP | FP | FN | Exact-count acc | Within-1 acc |
|---|---:|---:|---:|---:|---:|---:|---:|
| development | 1136 | 1136 | 1136 | 0 | 0 | 1.0000 | 1.0000 |
| held_out_test | 278 | 278 | 278 | 0 | 0 | 1.0000 | 1.0000 |

Consistency check:

| Bucket | Accepted prediction events | Sum aggregate prediction counts | Consistent |
|---|---:|---:|---|
| development | 1136 | 1136 | true |
| held_out_test | 278 | 278 | true |

## Validation

- `python -m pytest tests\test_counting_eval.py -q`: PASS, 3 passed.
- `python -m pytest tests\test_detection_eval.py tests\test_tracking_eval.py tests\test_counting_eval.py -q`: PASS, 8 passed.
- `python -m compileall -q src benchmark`: PASS.
- `git diff --check`: PASS, with Windows line-ending warnings only.

## Stop Gate

Per plan, Phase 06 stops here after report creation. Phase 07 uploaded-video runtime benchmark should start only after user review or explicit continuation.

## End-to-End Follow-Up

Production-facing counting comparison is now reported in `docs/reports/end-to-end-bytetrack-production-comparison.md`.

Held-out direct ByteTrack outperformed the current production re-tracker path: Event F1 0.942238 vs 0.835294, WAPE 0.050360 vs 0.194245.
