# TrafficFlow Interview Answers

## Project Problem

TrafficFlow counts vehicles by lane from uploaded videos and live traffic streams. The difficult part is not just detecting vehicles; it is converting frame-level detections into stable lane-level crossing events with direction validation and reproducible evidence.

## Team Size And Ownership

This was a five-member team project. My scope was the AI/computer-vision pipeline and runtime validation: ROI/crop semantics, detection integration, lane/class filtering, tracking/counting evaluation, derived GT, and benchmark reporting. I should not describe myself as owning the full frontend/backend/storage product.

## Input-To-Count Pipeline

```text
Frame -> ROI -> Detector -> Filter -> Tracker -> Lane association -> Direction validation -> Crossing event -> Count
```

YOLO gives boxes and classes. TrafficFlow still needs lane filtering, stable IDs, bottom-center anchors, lane lock, direction checks, and duplicate prevention before a count can be trusted.

## ROI Coordinate Spaces

Configs declare `geometry_space` as either `source_frame` or `crop_local`. If a live config is source-frame and crop mode is active, the runtime subtracts the processing ROI offset once so lane geometry, detections, tracks, and rendered overlays live in the same crop-local coordinate system.

## Lane Semantics

Each lane has a `valid_zone`, `counting_line`, `direction`, and allowed classes. The bottom-center anchor is used because it approximates where the vehicle touches the road. A crossing is counted only after the track is associated with a lane and moves across the counting line in the configured direction.

## Duplicate Prevention

The counter stores track IDs already counted per lane/class. A track cannot repeatedly count on the same lane. Multi-lane diagnostics are kept separately so duplicates can be detected instead of hidden.

## Tracking

The project evaluated both oracle tracking and end-to-end tracking. Oracle tracking isolates association with GT detections; end-to-end tracking measures the actual YOLO + tracker + counting path. The end-to-end result is more relevant for production claims.

Held-out end-to-end direct ByteTrack:

- HOTA: `0.242433`
- IDF1: `0.284952`
- ID switches: `42`
- Event F1: `0.942238`
- WAPE: `0.050360`

The current production re-tracker had more ID switches and worse counting WAPE on held-out sequences, so direct ByteTrack is the current measured offline baseline.

## Derived Ground Truth

UA-DETRAC provides object tracks, not lane-crossing events. I generated derived counting GT by combining frozen UA-DETRAC tracks with manual source-frame lane geometry and bottom-center crossing logic. This was audited with sampled event frames/contact sheets before scoring.

## Sequence Split

The benchmark uses full-sequence splits, never random frame splits:

- 1 smoke sequence
- 8 development sequences
- 5 held-out test sequences
- 86 reserve-only sequences

Held-out test is not used for tuning.

## Model Selection

The detector comparison was run on development data in Docker GPU. `yolov8m.pt` was selected because it gave the best AP50/AP50-95/recall trade-off among the tested candidates. Held-out detection AP50 was `0.582020` with recall `0.679091`.

## Runtime Profiling

Uploaded-video runtime measures full AI path, not just YOLO:

```text
decode -> preprocess -> inference -> tracking/filtering -> counting -> render -> encode
```

The best measured uploaded-video workload reached `75.829 FPS` and `3.033x` real time.

## Live Scheduling Problem

The live HLS bottleneck was not only model latency. HLS can arrive in bursts and stalls, so a pending-future scheduling loop can either build latency or leave the GPU idle. The stable path uses FFmpeg realtime pacing, latest-frame scheduling, stale-frame dropping, and a synchronous inference loop over the newest frame.

Formal Phase 08 soak result:

- Duration: `1803.284 s`
- Processed/published FPS: `14.895`
- Dropped frames: `0`
- Frame age p95: `0.9 ms`
- Session errors: `0`

## Failure Cases

Known issues:

- Truck metric is weak because UA-DETRAC `van` is mapped to TrafficFlow `truck`.
- Production re-tracker is weaker than direct ByteTrack in held-out end-to-end scoring.
- Live HLS count totals are operational only because no GT exists.
- Phase 09 ROI accuracy ablation is blocked until crop ROI GT exists.

## AI-Assisted Development

If asked directly:

> AI was used to support error analysis, option discussion, review, and to accelerate parts of implementation. I was responsible for defining the problem, choosing the solution, checking source code, writing/running tests, running benchmarks, integrating the changes, and keeping only changes I can explain.

Do not include this in the CV unless explicitly asked.

## Next Improvements

- Collect crop ROI GT and rerun full-frame vs crop-ROI accuracy ablation.
- Evaluate a model/class strategy for van/truck confusion.
- Revisit the production re-tracker or switch the offline product candidate to direct ByteTrack after regression testing.
- Add broader live-source soak coverage beyond one YouTube HLS stream.
