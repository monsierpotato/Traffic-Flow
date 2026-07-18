# Phase 03 - Unified Benchmark Runner and Run Manifest

## Status

PASS, refreshed on 2026-07-18.

Phase 03 now has a refreshed smoke run over all 14 selected sequences using the manual Phase 02 geometry and derived events.

## Outputs

- `benchmark/run.py`
- `benchmark/configs/runs/yolo11m_640.yaml`
- `benchmark/schemas/benchmark_manifest.schema.json`
- `benchmark/schemas/run_summary.schema.json`
- `benchmark/README.md`
- `benchmark/runs/phase03-smoke-manual-geometry-20260718/`
- `docs/reports/phase-03-benchmark-runner.md`
- `docs/wiki/ai-workflow/phase-03-benchmark-runner.md`

## Command

```bash
python -m benchmark.run \
  --model models/yolo11m.pt \
  --config benchmark/configs/runs/yolo11m_640.yaml \
  --geometry-dir benchmark/configs/geometry_manual \
  --derived-events-dir benchmark/ground_truth/derived_events \
  --output benchmark/runs/phase03-smoke-manual-geometry-20260718 \
  --sequences MVI_20011,MVI_20012,MVI_20035,MVI_40241,MVI_40213,MVI_40752,MVI_40963,MVI_63553,MVI_41063,MVI_40892,MVI_39401,MVI_40793,MVI_40854,MVI_40761 \
  --backend derived_gt_smoke
```

## Smoke Run Result

Run ID:

- `phase03-smoke-manual-geometry-20260718`

Backend:

- `derived_gt_smoke`

Result:

| Metric | Value |
|---|---:|
| Sequences | 14 |
| Raw detection rows | 214311 |
| Raw track rows | 214311 |
| Raw counting events | 1458 |
| Elapsed | 3083.817 ms |

The smoke backend writes GT-backed raw detections/tracks/counting events to validate runner, manifest, config snapshot, and artifact layout. It does not claim model accuracy or runtime performance. Real detection/tracking/counting benchmark scoring starts in Phase 04.

## Per-Sequence Events

| Sequence | Geometry | Raw events |
|---|---|---:|
| MVI_20011 | MVI_20011-manual-v1 | 44 |
| MVI_20012 | MVI_20012-manual-v1 | 35 |
| MVI_20035 | MVI_20035-manual-v1 | 56 |
| MVI_40241 | MVI_40241-manual-v1 | 281 |
| MVI_40213 | MVI_40213-manual-v1 | 164 |
| MVI_40752 | MVI_40752-manual-v1 | 140 |
| MVI_40963 | MVI_40963-manual-v1 | 138 |
| MVI_63553 | MVI_63553-manual-v1 | 163 |
| MVI_41063 | MVI_41063-manual-v1 | 159 |
| MVI_40892 | MVI_40892-manual-v1 | 4 |
| MVI_39401 | MVI_39401-manual-v1 | 110 |
| MVI_40793 | MVI_40793-manual-v1 | 84 |
| MVI_40854 | MVI_40854-manual-v1 | 69 |
| MVI_40761 | MVI_40761-manual-v1 | 11 |

## Run Artifacts

Smoke run directory:

- `benchmark/runs/phase03-smoke-manual-geometry-20260718/`

Files written:

- `manifest.json`
- `summary.json`
- `summary.csv`
- `summary.md`
- `raw_detections/*.jsonl`
- `raw_tracks/*.jsonl`
- `raw_counting_events/*.jsonl`
- `stage_timings.csv`
- `resource_samples.csv`
- `config_snapshot/`

## Acceptance Criteria

- All 14 selected sequences ran end-to-end: PASS.
- Raw outputs are retained: PASS.
- Run is reproducible from manifest/config snapshot: PASS.
- Non-empty output directory is rejected to avoid run ID overwrite: PASS.
- No frontend is required: PASS.

## Tests

New and updated tests:

- `tests/test_benchmark_runner.py`
- `tests/test_derived_gt.py`

Validation:

- Phase 03 smoke run with manual geometry: PASS.
- `python -m pytest tests -q`: PASS, 157 passed, 1 existing warning.
- `python -m compileall -q src benchmark`: PASS.
- `git diff --check`: PASS, with Windows line-ending warnings only.

## Known Limitations

- Phase 03 smoke backend is GT-backed and does not run YOLO inference.
- `resource_samples.csv` uses placeholder resource values in smoke mode.
- Model-scoring backend and full runtime benchmarking are intentionally deferred to Phase 04+.
