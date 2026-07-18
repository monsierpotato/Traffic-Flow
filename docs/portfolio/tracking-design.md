# Tracking Design

Status: Phase 05 benchmark baseline on 2026-07-18.

## Purpose

The tracking layer turns per-frame vehicle detections into stable identities. Stable identity is required before lane counting can deduplicate crossings by `track_id + lane_id`.

## Evaluator

Phase 05 uses:

- `TrackEval 1.3.0`
- Dataset adapter: `MotChallenge2DBox`
- Metrics: HOTA, DetA, AssA, IDF1, CLEAR MOT, LocA/MOTP, ID switches, fragmentations, mostly tracked, mostly lost

UA-DETRAC mapped vehicles are encoded as TrackEval class id `1` because the MOTChallenge adapter only evaluates the `pedestrian` class. This is an all-vehicle tracking benchmark; no class-specific tracking score is claimed here.

## Development Ablation

Input source:

- `ua_detrac_gt_oracle_detections`

This isolates association and tracker output behavior from detector miss/false-positive errors.

| Tracker | State model | Association | HOTA | IDF1 | IDSW | Frag |
|---|---|---|---:|---:|---:|---:|
| iou_frame | frame-based bbox memory | IoU only | 0.999936 | 0.999949 | 5 | 0 |
| trafficflow_kalman | 8-state Kalman | IoU + center distance gate | 0.807351 | 0.892666 | 104 | 206 |

Selected tracker under this isolated oracle-detection benchmark:

- `iou_frame`

## Frozen Tracker Config

Selected Phase 05 config:

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

Held-out result:

| Tracker | HOTA | DetA | AssA | IDF1 | IDSW | Frag |
|---|---:|---:|---:|---:|---:|---:|
| iou_frame | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0 | 0 |

## Interpretation

With perfect GT detections, IoU-only association is nearly perfect because adjacent UA-DETRAC boxes overlap strongly and the GT detector has no missed frames. The production-style Kalman tracker is designed for live detector gaps and low-FPS jumps, but in this oracle setting its smoothed/predicted bbox output lowers localization and association scores.

Detection error is still a separate risk: Phase 04 found weak `truck` detection because UA-DETRAC `van` is mapped to TrafficFlow `truck`.

## Limitation

This benchmark does not yet measure detector+tracker end-to-end identity under YOLO misses/false positives. That should be refreshed when Docker/GPU is available or with a dedicated CPU windowed detector-tracker run.
