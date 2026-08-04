# Phase 03 Benchmark Runner

Status: PASS, refreshed on 2026-07-18 with manual Phase 02 geometry.

Primary report:

- `docs/reports/phase-03-benchmark-runner.md`

Artifacts:

- `benchmark/run.py`
- `benchmark/configs/runs/yolo11m_640.yaml`
- `benchmark/schemas/benchmark_manifest.schema.json`
- `benchmark/schemas/run_summary.schema.json`
- `benchmark/README.md`
- `benchmark/runs/phase03-smoke-manual-geometry-20260718/`

Smoke run:

- Run ID: `phase03-smoke-manual-geometry-20260718`
- Backend: `derived_gt_smoke`
- Sequences: 14
- Raw detections: 214311
- Raw tracks: 214311
- Raw counting events: 1458
- Geometry source: `benchmark/configs/geometry_manual/`

Notes:

- The runner refuses non-empty output directories to avoid overwriting run IDs.
- The Phase 03 smoke backend validates manifest and artifact plumbing only.
- Model scoring starts in Phase 04.
