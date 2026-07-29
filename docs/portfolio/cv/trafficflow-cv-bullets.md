# TrafficFlow CV Bullets

Project title:

```text
TrafficFlow - Computer Vision & AI Pipeline | Team of 5
```

## Four-Bullet Version

- Contributed to the computer-vision pipeline for lane-level traffic analytics in a five-member team project, covering ROI/crop coordinate semantics, YOLO-based detection, lane/class filtering, tracking evaluation, lane association, direction validation, and line-crossing counting.
- Helped build a reproducible UA-DETRAC benchmark protocol with sequence-level splits, manual lane geometry, derived counting ground truth, and Docker GPU evaluation; the benchmark selected `yolov8m.pt` with held-out AP50 `0.5820` and recall `0.6791`.
- Evaluated end-to-end tracking/counting branches and found direct ByteTrack stronger than the current production re-tracker on held-out sequences, reaching HOTA `0.242433`, IDF1 `0.284952`, Event F1 `0.942238`, and WAPE `0.050360`.
- Contributed to live AI-runtime bottleneck analysis and validation, sustaining `14.895` processed/published FPS with `0` dropped frames and `0.9 ms` p95 frame age during a `30-minute` YouTube/HLS soak test.

## Short Version

- Contributed to the AI/computer-vision pipeline for lane-level traffic counting in a five-member team project, from ROI/crop geometry through detection, tracking, lane association, direction checks, and counting events.
- Helped build reproducible benchmark reports across detection, tracking, counting, upload runtime, and live runtime, including held-out direct ByteTrack counting Event F1 `0.942238` and WAPE `0.050360`.
- Validated live YouTube/HLS AI runtime with a 30-minute soak at `14.895` FPS, `0` dropped frames, and `0.9 ms` p95 frame age.

## Notes

- Do not claim solo full-stack ownership.
- Do not claim motorcycle metrics from UA-DETRAC.
- Do not present live operational counts as accuracy metrics.
- If space is tight, keep the live-runtime bullet only if applying to AI/runtime/backend-adjacent roles.
