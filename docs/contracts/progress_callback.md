# Progress Callback Contract

`TrafficFlowEngine` accepts an optional `progress_callback` on `VideoCountingRequest`.

The callback receives a dictionary:

```json
{
  "status": "processing",
  "frame_index": 149,
  "frames_processed": 150,
  "total_frames": 300,
  "progress": 50.0
}
```

## Status Values

- `started`: emitted before frame processing begins.
- `processing`: emitted every `progress_interval_percent` while processing.
- `completed`: emitted after successful processing.
- `failed`: emitted before re-raising an exception if processing fails.

## Notes

- `total_frames` can be `null` if OpenCV cannot read frame count and no `max_frames` is set.
- `progress` can be `null` when `total_frames` is unknown.
- Worker code should persist `status`, `frames_processed`, and `progress` to the task table.
