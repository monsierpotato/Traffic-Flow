# Processing ROI Contract

`processing_roi` defines the rectangular region used for inference, preview, counting, and output rendering. `annotation_roi` is kept only as a legacy alias for older configs. New configs should send `processing_roi`.

## Coordinate Rule

The frontend displays the cropped processing ROI for lane drawing. Lane geometry may be submitted in full-frame source coordinates for backward compatibility:

```text
source_x = roi.x + display_x * (roi.width / display_width)
source_y = roi.y + display_y * (roi.height / display_height)
```

At worker startup, source-frame lane geometry is normalized once into processing-frame coordinates:

```text
processing_x = source_x - processing_roi.x
processing_y = source_y - processing_roi.y
```

After that normalization, the runtime pipeline treats all detections, tracks, counting lines, zones, and rendered overlays as processing-frame / crop-local coordinates.

## Runtime Pipeline

```text
source frame -> crop processing_roi -> mask roi_polygon -> letterbox 640 -> inference
AI bbox -> processing coords -> tracking -> counting -> renderer -> cropped output video
```

This keeps model input, lane config, bounding boxes, counting, and overlay in the same coordinate system.

## Example

```text
source frame: 1920x1080
processing_roi: x=400, y=300, width=900, height=400
displayed crop: 900x400
drawn point: x=120, y=80
source point submitted by legacy frontend: x=520, y=380
runtime processing point: x=120, y=80
```

## Backward Compatibility

The worker reads `processing_roi` first and falls back to `annotation_roi` if needed:

```text
processing_roi = lane_config.processing_roi || lane_config.annotation_roi
```

Configs should migrate from `annotation_roi.purpose=frontend_annotation_only` to `processing_roi.purpose=inference_processing`.
