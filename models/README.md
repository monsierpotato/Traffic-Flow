# Legacy model path

Model weights are now colocated with the inference service under
`inference/models/` and remain ignored by git. Put the default weight here:

```text
inference/models/yolov8n.pt
```

The runtime still accepts an older `models/<file>` configuration and resolves
it to the canonical bundle first, then falls back to this legacy directory.
