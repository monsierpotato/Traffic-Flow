# TrafficFlow AI Pipeline

## Pipeline

```text
Input frame
-> ROI crop or full-frame preprocessing
-> 640x640 letterbox
-> YOLO detector
-> ByteTrack track IDs
-> lane/class filter
-> optional TrafficFlow LocalTracker
-> lane lock
-> direction validation
-> counting-line crossing
-> event/count aggregation
-> overlay render
```

## ROI And Coordinate Spaces

TrafficFlow supports explicit coordinate spaces:

- `source_frame`: geometry points are in original video coordinates.
- `crop_local`: geometry points are already relative to the processing crop.

For live crop mode, the config can include:

- `roi_polygon`: free-form user-selected ROI.
- `crop_rect_padded`: rectangle around the ROI polygon with context padding.
- `processing_roi`: rectangle used for inference crop.
- `processing_width` and `processing_height`: crop output size.

Runtime normalizes source-frame geometry into crop-local coordinates once before tracking/counting.

## Lane Semantics

Each lane contains:

- `valid_zone`: polygon where a vehicle anchor is considered relevant.
- `counting_line`: two-point line segment used as the crossing gate.
- `direction`: two-point vector used to reject wrong-way motion.
- `class_allowed`: vehicle class filter.

Counting uses the bottom-center anchor of the vehicle box because it is closer to the road contact point than the bbox center.

## Tracking And Counting

The benchmark compared:

- Direct ByteTrack: Ultralytics `model.track(..., tracker="bytetrack.yaml")` output used directly for filtering/counting.
- TrafficFlow production path: YOLO/ByteTrack detections passed into `LocalTracker` before counting.

Held-out end-to-end evidence currently favors direct ByteTrack:

| Variant | HOTA | IDF1 | IDSW | Event F1 | WAPE |
|---|---:|---:|---:|---:|---:|
| Direct ByteTrack | 0.242433 | 0.284952 | 42 | 0.942238 | 0.050360 |
| Production re-tracker | 0.215225 | 0.224661 | 169 | 0.835294 | 0.194245 |

## Runtime Design

Uploaded videos are processed through the Celery worker. Live YouTube/HLS sessions run inside the FastAPI API process.

The stable live path uses:

- FFmpeg latest-frame reader.
- Crop in FFmpeg when valid ROI metadata exists.
- Realtime HLS pacing.
- Latest-frame scheduling to avoid latency buildup.
- Timestamp-aware tracking state and bounded reset on input gaps.

Phase 08 validated this with a 30-minute YouTube HLS soak: 14.895 FPS overall, frame age p95 0.9 ms, 0 dropped frames, 0 reconnects, 0 stalls, and 0 session errors.
