# ROI Annotation

## Summary

TrafficFlow should support rectangular ROI cropping during lane drawing so users can zoom into the road area and draw lanes more accurately.

## Current State

- The ROI is rectangular, not perspective-based.
- The current MVP policy is `annotation crop: yes; processing crop: no`.
- `docs/contracts/annotation_roi.md` defines how displayed crop coordinates map back to source-frame coordinates.
- `trafficflow/geometry/roi.py` provides helper logic for converting displayed crop points to source-frame points.
- `trafficflow/cli/config_generator.py` supports `--annotation-roi x,y,width,height` and `--select-roi` for drawing on a cropped preview while saving source-frame lane coordinates.

## Decisions

- Use `x`, `y`, `width`, and `height` for ROI rather than four arbitrary points.
- Store optional `annotation_roi` metadata in lane config.
- Keep `counting_line`, `valid_zone`, and `direction` in original video coordinates before sending to backend/AI.
- Do not crop frames for AI inference in the MVP.

## Open Questions

- Should frontend allow resizing/moving ROI after drawing lanes?
- Should backend validate that converted lane points fall inside the source resolution?
- Should the OpenCV config generator include an edit mode for changing ROI after a lane has been added?

## Links

- [[Lane Config Contract]]
- [[Runtime Engine]]
- [[Decision Log]]
