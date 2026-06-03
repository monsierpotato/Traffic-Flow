# Annotation ROI Contract

`annotation_roi` is an optional frontend annotation helper. It records the crop used when drawing lanes, but all lane geometry sent to the backend must stay in full-frame source coordinates.

## Coordinate Rule

For a point drawn on a displayed crop:

```text
source_x = roi.x + display_x * (roi.width / display_width)
source_y = roi.y + display_y * (roi.height / display_height)
```

The AI engine should read `lanes[*].counting_line`, `lanes[*].valid_zone`, and `lanes[*].direction` as source-frame coordinates. It does not need to crop the processing video for this annotation feature.

## Example

```text
source frame: 1920x1080
roi: x=400, y=300, width=900, height=400
displayed crop: 900x400
drawn point: x=120, y=80
source point: x=520, y=380
```

If the frontend displays the same ROI at `450x200`, the same visual center point `(225, 100)` maps to `(850, 500)` in source coordinates.

## MVP Guidance

Use `annotation_roi` for drawing accuracy only:

```text
annotation crop: yes
processing crop: no
```

Processing ROI can be added later as a separate field if the team wants to optimize inference speed.

## CLI Config Generator

`trafficflow.cli.config_generator` supports rectangular annotation ROI in two ways:

```powershell
python -m trafficflow.cli.config_generator --video input.mp4 --output configs/camera.json --annotation-roi 400,300,900,400
```

or:

```powershell
python -m trafficflow.cli.config_generator --video input.mp4 --output configs/camera.json --select-roi
```

In both modes, the displayed drawing frame is cropped, but saved lane geometry remains in source-frame coordinates.
