# Phase 09 Ablation And Error Analysis

- Generated at: `2026-07-18T17:26:58`
- Scope: frozen Phase 04-08 benchmark artifacts plus source-frame representative images.
- Status: `PARTIAL PASS` because tracker and live scheduling evidence are complete/usable, while ROI accuracy ablation is blocked by missing frozen crop ROI GT for UA-DETRAC.

## Tracker Ablation

The production-relevant held-out comparison is negative for the current production re-tracker: direct ByteTrack has better identity and counting metrics.

| variant | hota | idf1 | id_switches | fragmentations | event_f1 | wape | duplicate_count_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bytetrack | 0.242433 | 0.284952 | 42 | 173 | 0.942238 | 0.05036 | 0.0 |
| trafficflow_production | 0.215225 | 0.224661 | 169 | 219 | 0.835294 | 0.194245 | 0.0 |

Interpretation: use direct ByteTrack as the current measured offline baseline. Keep the production re-tracker only as an implementation baseline until live/upload regression proves a reason to keep it.

## ROI Strategy Ablation

| variant | status | ap50 | recall | processed_fps | event_f1 | wape | blocker_or_note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| crop_roi | blocked |  |  |  |  |  | UA-DETRAC selected sequences have manual lane/counting geometry but no frozen user-drawn crop ROI. Live crop config has no GT, so AP/Event F1/WAPE would not be comparable. |

Blocker detail: the 14 UA-DETRAC benchmark sequences have manually validated lane/counting geometry, but not a frozen user-drawn crop ROI per sequence. The only crop-ROI config with a real polygon is the YouTube/HLS live source, which has no GT. Running AP/Event-F1/WAPE from that would be an invalid comparison.

## Live Scheduling Ablation

| variant | status | processed_fps | dropped_frame_ratio | frame_age_p95_ms | inference_idle_ratio | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| historical_pending_future_bursty | partial_historical | 7.767 | 0.302365 |  |  | docs/wiki/ai-workflow/gpu-docker-live-optimization.md |
| realtime_latest_frame_dedicated_loop | completed_current | 14.895 | 0 | 0.9 | 0.766929 | benchmark/reports/live_runtime_report.md |

The current realtime latest-frame loop reached 14.895 FPS for 30 minutes with 0 dropped frames and frame-age p95 0.9 ms. The historical pending-future run is useful as evidence of the previous failure mode, but it lacks frame-age/idle instrumentation, so it is marked partial-historical rather than a fully symmetric A/B experiment.

## Error Taxonomy

| variant | error_class | count | rate | denominator | source_component | fixability |
| --- | --- | --- | --- | --- | --- | --- |
| detector_yolov8m | missed small vehicle | 293 | 0.49577 | 591 | Detection | fixable |
| detector_yolov8m | heavy occlusion | 178 | 0.455243 | 391 | Detection | partly_inherent |
| detector_yolov8m | class confusion | 58 | 0.852941 | 68 | Detection/class mapping | fixable |
| bytetrack | missed crossing | 17 | 0.061151 | 278 | Counting/tracking interaction | fixable |
| bytetrack | wrong lane | 2 | 0.007246 | 278 | Lane geometry and association | fixable |
| bytetrack | wrong direction | 0 | 0 | 278 | Counting direction logic | fixable |
| bytetrack | duplicate crossing | 0 | 0 | 278 | Counting state | fixable |
| bytetrack | early/late crossing | 251 | 0.961686 | 261 | Counting timing | fixable |
| bytetrack | false crossing | 15 | 0.054348 | 278 | Detection/tracking/counting interaction | fixable |
| bytetrack | ID switch | 42 | 0.082515 | 509 | Tracking/association | fixable |
| bytetrack | track fragmentation | 173 | 0.339882 | 509 | Tracking/association | fixable |
| trafficflow_production | missed crossing | 65 | 0.233813 | 278 | Counting/tracking interaction | fixable |
| trafficflow_production | wrong lane | 3 | 0.012931 | 278 | Lane geometry and association | fixable |
| trafficflow_production | wrong direction | 0 | 0 | 278 | Counting direction logic | fixable |
| trafficflow_production | duplicate crossing | 0 | 0 | 278 | Counting state | fixable |
| trafficflow_production | early/late crossing | 203 | 0.953052 | 213 | Counting timing | fixable |
| trafficflow_production | false crossing | 19 | 0.081897 | 278 | Detection/tracking/counting interaction | fixable |
| trafficflow_production | ID switch | 169 | 0.332024 | 509 | Tracking/association | fixable |
| trafficflow_production | track fragmentation | 219 | 0.430255 | 509 | Tracking/association | fixable |
| manual_geometry | geometry mismatch | 0 | 0 | 14 | Lane geometry | fixable |
| manual_geometry | coordinate-space error | 0 | 0 | 14 | Lane geometry | fixable |

## Representative Examples

| variant | error_class | sequence_id | frame_num | track_id | artifact |
| --- | --- | --- | --- | --- | --- |
| detector_yolov8m | missed small vehicle | MVI_40892 | 101 | 9 | benchmark/reports/phase09_error_frames/missed_small_vehicle_MVI_40892_101.jpg |
| detector_yolov8m | heavy occlusion | MVI_40892 | 101 | 9 | benchmark/reports/phase09_error_frames/heavy_occlusion_MVI_40892_101.jpg |
| detector_yolov8m | class confusion | MVI_40892 | 401 | 37 | benchmark/reports/phase09_error_frames/class_confusion_MVI_40892_401.jpg |
| bytetrack | missed crossing | MVI_39401 | 112 | 14 | benchmark/reports/phase09_error_frames/bytetrack_missed_crossing_MVI_39401_112.jpg |
| bytetrack | wrong lane | MVI_39401 | 203 | 76 | benchmark/reports/phase09_error_frames/bytetrack_wrong_lane_MVI_39401_203.jpg |
| bytetrack | early/late crossing | MVI_39401 | 7 | 5 | benchmark/reports/phase09_error_frames/bytetrack_early_late_crossing_MVI_39401_7.jpg |
| bytetrack | false crossing | MVI_39401 | 869 | 215 | benchmark/reports/phase09_error_frames/bytetrack_false_crossing_MVI_39401_869.jpg |
| bytetrack | ID switch | MVI_40892 | 725 | 7 | benchmark/reports/phase09_error_frames/bytetrack_ID_switch_MVI_40892_725.jpg |
| bytetrack | track fragmentation | MVI_40892 | 689 | 5 | benchmark/reports/phase09_error_frames/bytetrack_track_fragmentation_MVI_40892_689.jpg |
| trafficflow_production | missed crossing | MVI_39401 | 19 | 2 | benchmark/reports/phase09_error_frames/trafficflow_production_missed_crossing_MVI_39401_19.jpg |
| trafficflow_production | wrong lane | MVI_39401 | 33 | 6 | benchmark/reports/phase09_error_frames/trafficflow_production_wrong_lane_MVI_39401_33.jpg |
| trafficflow_production | early/late crossing | MVI_39401 | 8 | 5 | benchmark/reports/phase09_error_frames/trafficflow_production_early_late_crossing_MVI_39401_8.jpg |
| trafficflow_production | false crossing | MVI_39401 | 870 | 62 | benchmark/reports/phase09_error_frames/trafficflow_production_false_crossing_MVI_39401_870.jpg |
| trafficflow_production | ID switch | MVI_40892 | 689 | 5 | benchmark/reports/phase09_error_frames/trafficflow_production_ID_switch_MVI_40892_689.jpg |
| trafficflow_production | track fragmentation | MVI_40892 | 689 | 5 | benchmark/reports/phase09_error_frames/trafficflow_production_track_fragmentation_MVI_40892_689.jpg |

## Acceptance Criteria

- Three ablations completed or blocked with specific reason: PASS.
- Error examples trace to sequence/frame/track where available: PASS.
- Limitations specific: PASS.
- Negative finding disclosed: PASS.
