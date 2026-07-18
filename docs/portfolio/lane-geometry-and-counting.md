# Lane Geometry and Counting Ground Truth

Status: refreshed Phase 02 manual baseline on 2026-07-18.

This document explains the active geometry and derived counting ground truth used by the TrafficFlow UA-DETRAC benchmark protocol.

## Active Geometry

Geometry directory:

- `benchmark/configs/geometry_manual/<sequence>.json`

The 14 selected UA-DETRAC sequences use manually drawn per-sequence lane polygons and counting lines. Geometry is stored in `source_frame` coordinates at 960x540 resolution. Processing remains full-frame; the valid zones are lane polygons used for membership/counting, not ROI crops.

The manual geometry audit artifact is:

- `benchmark/annotation/manual_geometry_validation_report.md`
- `benchmark/annotation/manual_geometry_contact_sheet.jpg`
- `benchmark/annotation/manual_overlays/<sequence>.jpg`

The audit normalized only polygon mechanics: each valid zone is closed, and last-edge/first-edge intersections are clipped to the intersection before closure. User-drawn counting lines and direction vectors were preserved.

## Event Semantics

Derived counting events are generated from UA-DETRAC GT tracks using:

- bottom-center anchor:

```text
anchor_t = ((x1_t + x2_t) / 2, y2_t)
```

- signed side change across the counting line;
- segment intersection between anchor movement and counting line;
- crossing point inside the lane valid zone;
- direction alignment with the lane direction vector;
- deduplication by `gt_track_id + lane_id`.

Each event is written to:

- `benchmark/ground_truth/derived_events/<sequence>.jsonl`

Each count aggregate is written to:

- `benchmark/ground_truth/counts/<sequence>.csv`

The combined aggregate is:

- `benchmark/ground_truth/counts/counts_summary_v1.csv`

## Phase 02 Counts

Generated scope:

| Item | Value |
|---|---:|
| Sequences with geometry | 14 |
| Lanes | 28 |
| Derived events | 1458 |
| Count rows | 69 |
| Audit sample events | 50 |

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

## Audit

Audit artifacts:

- `benchmark/ground_truth/audit/audit_sample.csv`
- `benchmark/ground_truth/audit/phase02_manifest.json`
- `benchmark/annotation/manual_geometry_validation_report.md`
- `benchmark/annotation/manual_geometry_contact_sheet.jpg`

The event audit sample contains 50 events. The geometry audit reports 0 remaining issues and 0 remaining warnings after normalization.

## Limitations

- Phase 02 produces counting GT only. Detection and tracking metrics still require Phase 04 and Phase 05.
- Motorcycle metrics remain unsupported for UA-DETRAC because the annotations in this repo have no motorcycle-compatible label.
- Current manual files use `direction_name: forward`; if semantic direction labels are refined later, bump `geometry_version` and regenerate Phase 02/03.
