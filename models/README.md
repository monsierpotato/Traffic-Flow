# Legacy model path

Model weights are now colocated with the inference service under
`inference/models/` and remain ignored by git by default. This branch
intentionally tracks two legacy fallback weights:

- `models/yolov8m.pt`
- `models/vietnamese_vehicle_detection/my_finetuned_yolov8.pt`

Put the default inference-service weight here:

```text
inference/models/yolov8n.pt
```

The runtime still accepts an older `models/<file>` configuration and resolves
it to the canonical bundle first, then falls back to this legacy directory.
