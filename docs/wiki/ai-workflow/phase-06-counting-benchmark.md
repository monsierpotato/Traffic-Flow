# Phase 06 Counting Benchmark

Status: PASS, STOP GATE reached on 2026-07-18.

Primary report:

- `docs/reports/phase-06-counting-benchmark.md`

Artifacts:

- `benchmark/counting_eval.py`
- `benchmark/predictions/counting/phase06-oracle-counting-manual-geometry-20260718/events.jsonl`
- `benchmark/reports/counting_report.md`
- `benchmark/reports/counting_summary.csv`
- `benchmark/reports/counting_event_matches.csv`
- `benchmark/reports/counting_errors.csv`

Protocol:

- Oracle counting benchmark using Phase 03 GT-backed prediction events.
- GT events from Phase 02 derived counting ground truth.
- One-to-one event matching by video, lane, class, direction, and 5-frame temporal tolerance.
- Aggregate unit is video x lane x class x direction.

Headline:

| Scope | Event P | Event R | Event F1 | WAPE | Bias | Duplicate rate | Miss rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| development | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| held_out_test | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

Traceability:

- Development: 1136 GT events, 1136 prediction events, 1136 TP, 0 FP, 0 FN.
- Held-out: 278 GT events, 278 prediction events, 278 TP, 0 FP, 0 FN.
- `counting_event_matches.csv` contains the per-event TP/FP/FN records.
- `counting_errors.csv` is header-only in this oracle run.

Limit:

- This is not an end-to-end YOLO + tracker + counting metric. It validates the counting evaluator and report structure before model-driven counting.

Stop gate:

- Phase 06 report is complete. Phase 07 uploaded-video runtime benchmark waits for user review or explicit continuation.

End-to-end follow-up:

- Production-facing counting comparison is now reported in [[End-to-End ByteTrack Production Comparison]].
- Held-out direct ByteTrack outperformed the current production re-tracker path: Event F1 0.942238 vs 0.835294, WAPE 0.050360 vs 0.194245.
