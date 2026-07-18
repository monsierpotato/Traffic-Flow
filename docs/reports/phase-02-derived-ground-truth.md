# Phase 02 - Manual Geometry and Derived Counting Ground Truth

## Status

PASS, refreshed on 2026-07-18.

Phase 02 now uses manual per-sequence lane geometry from `benchmark/configs/geometry_manual/` instead of the earlier auto full-frame geometry baseline.

## Outputs

- `benchmark/configs/geometry_manual/<sequence>.json`
- `benchmark/annotation/audit_manual_geometry.py`
- `benchmark/annotation/manual_geometry_validation_report.md`
- `benchmark/annotation/manual_geometry_validation.json`
- `benchmark/annotation/manual_geometry_contact_sheet.jpg`
- `benchmark/annotation/manual_overlays/<sequence>.jpg`
- `benchmark/ground_truth/derived_events/<sequence>.jsonl`
- `benchmark/ground_truth/counts/<sequence>.csv`
- `benchmark/ground_truth/counts/counts_summary_v1.csv`
- `benchmark/ground_truth/audit/audit_sample.csv`
- `benchmark/ground_truth/audit/phase02_manifest.json`
- `docs/portfolio/lane-geometry-and-counting.md`
- `docs/wiki/ai-workflow/phase-02-derived-ground-truth.md`

## Manual Geometry Audit

The manual geometry audit checked all 14 selected sequences:

| Metric | Value |
|---|---:|
| Geometry files | 14 |
| Lanes | 28 |
| Issues after fix | 0 |
| Warnings after fix | 0 |
| Mechanical fixes applied | 38 |

Fixes were limited to safe polygon mechanics:

- close every `valid_zone` by connecting the last point to the first point;
- when the last edge crossed the first edge, replace the last point with that intersection before closing;
- preserve user-drawn counting lines and direction vectors.

Backup before normalization:

- `benchmark/configs/geometry_manual_backup_20260718-040911/`

## Derived GT Refresh

Command:

```bash
python -m benchmark.derived_gt \
  --geometry-source manual \
  --geometry-dir benchmark/configs/geometry_manual \
  --events-dir benchmark/ground_truth/derived_events \
  --counts-dir benchmark/ground_truth/counts \
  --audit-dir benchmark/ground_truth/audit
```

Generated scope:

| Metric | Value |
|---|---:|
| Sequences | 14 |
| Derived event JSONL files | 14 |
| Per-sequence count CSV files | 14 |
| Derived events | 1458 |
| Count rows | 69 |
| Audit sample size | 50 |

Class totals:

| Class | Events |
|---|---:|
| car | 1269 |
| truck | 145 |
| bus | 44 |

Sequence totals:

| Sequence | Events |
|---|---:|
| MVI_20011 | 44 |
| MVI_20012 | 35 |
| MVI_20035 | 56 |
| MVI_39401 | 110 |
| MVI_40213 | 164 |
| MVI_40241 | 281 |
| MVI_40752 | 140 |
| MVI_40761 | 11 |
| MVI_40793 | 84 |
| MVI_40854 | 69 |
| MVI_40892 | 4 |
| MVI_40963 | 138 |
| MVI_41063 | 159 |
| MVI_63553 | 163 |

## Event Semantics

The generator uses:

- bottom-center bbox anchor;
- previous/current anchor signed side change against the lane counting line;
- segment intersection;
- lane membership at crossing point;
- direction-vector alignment;
- deduplication by `gt_track_id + lane_id`.

The current manual JSON files use `direction_name: forward`, so the aggregate direction total is 1458 `forward` events. If lane names or direction labels are semantically changed later, bump `geometry_version` and regenerate Phase 02/03 again.

## Validation

- Manual geometry audit: PASS, 0 issues and 0 warnings after fix.
- Phase 02 regeneration with `--geometry-source manual`: PASS.
- Phase 03 smoke refresh on all 14 sequences consumed the same 1458 derived events.
- `python -m pytest tests -q`: PASS, 157 passed, 1 existing warning.
- `python -m compileall -q src benchmark`: PASS.
- `git diff --check`: PASS, with Windows line-ending warnings only.
