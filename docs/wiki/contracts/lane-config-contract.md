# Lane Config Contract

## Summary

Lane config describes video resolution, counting settings, lane geometry, and optional annotation metadata used by the frontend.

## Current State

- Example manual configs live in `configs/examples/` and `configs/danang/`.
- ROI annotation examples live in `docs/contracts/lane_config_with_annotation_roi.json`.
- `annotation_roi` is frontend annotation metadata only.

## Required Coordinate Rule

Lane geometry consumed by the AI engine must be in source-frame coordinates:

```text
source_x = roi.x + display_x * (roi.width / display_width)
source_y = roi.y + display_y * (roi.height / display_height)
```

## Open Questions

- Should config validation use Pydantic models in backend/API code?
- Should `annotation_roi` include frontend display metadata or only source-frame ROI metadata?

## Links

- [[ROI Annotation]]
- [[Runtime Engine]]
