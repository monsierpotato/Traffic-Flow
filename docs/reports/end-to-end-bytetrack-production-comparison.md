# End-to-End ByteTrack vs Production Comparison

## Status

PASS on 2026-07-18.

This report adds the production-relevance benchmark requested after Phase 04-06: compare direct ByteTrack against the current TrafficFlow production path.

## Compared Branches

- `bytetrack`: YOLOv8m + Ultralytics ByteTrack + lane/class filter + counting.
- `trafficflow_production`: YOLOv8m + Ultralytics ByteTrack + lane/class filter + TrafficFlow `LocalTracker` Kalman re-tracker + counting.

## Artifacts

- `benchmark/end_to_end_eval.py`
- `tests/test_end_to_end_eval.py`
- `benchmark/predictions/end_to_end/e2e-dev-bytetrack-vs-production-full-docker-gpu-20260718/`
- `benchmark/predictions/end_to_end/e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718/`
- `benchmark/reports/end_to_end_report.md`
- `benchmark/reports/end_to_end_summary.csv`
- `docs/reports/end-to-end-bytetrack-production-comparison.md`
- `docs/wiki/ai-workflow/end-to-end-bytetrack-production-comparison.md`

## Headline

| Bucket | Variant | HOTA | IDF1 | Event F1 | WAPE | IDSW |
|---|---|---:|---:|---:|---:|---:|
| development | bytetrack | 0.249929 | 0.403836 | 0.849005 | 0.202465 | 34 |
| development | trafficflow_production | 0.201410 | 0.306618 | 0.734821 | 0.305458 | 284 |
| held_out_test | bytetrack | 0.242433 | 0.284952 | 0.942238 | 0.050360 | 42 |
| held_out_test | trafficflow_production | 0.215225 | 0.224661 | 0.835294 | 0.194245 | 169 |

## Conclusion

Direct ByteTrack is the stronger measured end-to-end baseline on UA-DETRAC:

- Held-out Event F1 improves from `0.835294` to `0.942238`.
- Held-out WAPE improves from `0.194245` to `0.050360`.
- Held-out ID switches drop from `169` to `42`.

The current production branch remains documented, but the benchmark result supports making direct ByteTrack the next production candidate after a live/upload regression pass.
