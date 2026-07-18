# TrafficFlow Error Analysis

## Status

Phase 09 completed as `PARTIAL PASS`.

This page summarizes the formal Phase 09 taxonomy generated from frozen Phase 04-08 artifacts. Tracker and live scheduling ablations are evidenced; ROI accuracy ablation is blocked until the UA-DETRAC benchmark has frozen crop ROI GT per sequence.

Primary artifacts:

- `benchmark/reports/ablation_report.md`
- `benchmark/reports/ablation_summary.csv`
- `benchmark/reports/error_taxonomy.csv`
- `benchmark/reports/phase09_error_examples.csv`
- `benchmark/reports/phase09_error_frames/`

## Ablation Summary

| Ablation | Result | Interpretation |
|---|---|---|
| Tracker, held-out E2E | Direct ByteTrack: HOTA 0.242433, IDF1 0.284952, Event F1 0.942238, WAPE 0.050360. Production re-tracker: HOTA 0.215225, IDF1 0.224661, Event F1 0.835294, WAPE 0.194245. | Direct ByteTrack is the stronger measured offline baseline. |
| ROI strategy | Blocked for AP/Event F1/WAPE. | The selected UA-DETRAC sequences have lane/counting geometry, not frozen crop ROI GT; the live crop source has no GT. |
| Live scheduling | Historical pending-future smoke: 7.767 FPS, drop ratio 0.302365. Current realtime latest-frame 30-minute soak: 14.895 FPS, drop ratio 0.0, frame-age p95 0.9 ms. | The current scheduler fixes the measured live HLS throughput/staleness failure mode, but the old run lacks frame-age/idle instrumentation. |

## Error Taxonomy

| Error class | Variant/source | Count/rate | Likely source | Fixability |
|---|---|---:|---|---|
| Missed small vehicle | Detector held-out sample | 293 / 0.495770 | Detection | Fixable with data/model tuning |
| Heavy occlusion | Detector held-out sample | 178 / 0.455243 | Detection + scene difficulty | Partly inherent |
| Class confusion | Detector truck/van mapping | 58 / 0.852941 miss rate for mapped truck GT | Detection/class mapping | Fixable with class policy or data |
| Missed crossing | Direct ByteTrack | 17 / 0.061151 | Detection/tracking/counting interaction | Fixable |
| Missed crossing | Production re-tracker | 65 / 0.233813 | Tracking/association | Fixable |
| Wrong lane | Direct ByteTrack | 2 / 0.007246 | Lane geometry and association | Fixable |
| Wrong lane | Production re-tracker | 3 / 0.012931 | Lane geometry and association | Fixable |
| ID switch | Direct ByteTrack | 42 / 0.082515 per held-out GT track | Tracking/association | Fixable |
| ID switch | Production re-tracker | 169 / 0.332024 per held-out GT track | Tracking/association | Fixable |
| Track fragmentation | Direct ByteTrack | 173 / 0.339882 per held-out GT track | Tracking/association | Fixable |
| Track fragmentation | Production re-tracker | 219 / 0.430255 per held-out GT track | Tracking/association | Fixable |
| Wrong direction | Both E2E variants | 0 | Counting direction logic | No current issue in held-out evidence |
| Duplicate crossing | Both E2E variants | 0 | Counting state | No current issue in held-out evidence |
| Geometry mismatch | Manual geometry audit | 0 / 14 configs | Lane geometry | No current issue after manual fixes |
| Coordinate-space error | Manual/live config contract | 0 / 14 configs | Geometry coordinate contract | No current issue in Phase 09 evidence |

## Representative Examples

Representative frames are generated under `benchmark/reports/phase09_error_frames/`, with trace rows in `benchmark/reports/phase09_error_examples.csv`.

Examples include:

- `MVI_40892`, frame 101: missed small/occluded detector GT.
- `MVI_40892`, frame 401: mapped truck/van weakness.
- `MVI_39401`, frame 112: direct ByteTrack missed crossing.
- `MVI_39401`, frame 203: direct ByteTrack wrong-lane event.
- `MVI_40892`, frame 725: direct ByteTrack ID-switch example.
- `MVI_40892`, frame 689: production re-tracker ID-switch/fragmentation examples.

## Do Not Overclaim

Use end-to-end direct ByteTrack results for offline tracking/counting claims. Use oracle tracking/counting results only to explain evaluator isolation and scoring sanity. Do not claim ROI accuracy improvement until a formal full-frame vs crop-ROI GT-backed ablation exists.
