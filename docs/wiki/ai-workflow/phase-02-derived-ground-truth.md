# Phase 02 Derived Ground Truth

Status: PASS, refreshed on 2026-07-18 with manual per-sequence geometry.

Primary report:

- `docs/reports/phase-02-derived-ground-truth.md`

Artifacts:

- `benchmark/configs/geometry_manual/<sequence>.json`
- `benchmark/annotation/manual_geometry_validation_report.md`
- `benchmark/annotation/manual_geometry_contact_sheet.jpg`
- `benchmark/annotation/manual_overlays/<sequence>.jpg`
- `benchmark/ground_truth/derived_events/<sequence>.jsonl`
- `benchmark/ground_truth/counts/<sequence>.csv`
- `benchmark/ground_truth/counts/counts_summary_v1.csv`
- `benchmark/ground_truth/audit/audit_sample.csv`
- `benchmark/ground_truth/audit/phase02_manifest.json`
- `docs/portfolio/lane-geometry-and-counting.md`

Summary:

- Audited 14 manual geometry files and 28 lane polygons.
- Fixed only mechanical polygon closure/intersection issues; counting lines were preserved.
- Derived 1458 counting events from UA-DETRAC GT tracks.
- Aggregated 69 count rows.
- Audited 50 sampled events.

Class totals:

| Class | Events |
|---|---:|
| car | 1269 |
| truck | 145 |
| bus | 44 |

Important note:

- The previous auto full-frame geometry is no longer the active Phase 2 baseline.
- Active geometry is `benchmark/configs/geometry_manual/`.
- Any future lane redraw must rerun Phase 2 and Phase 3 before model scoring.
