# Video Counting Result Contract

`TrafficFlowEngine.process_video(...)` returns a `VideoCountingResult`. CLI prints `result.to_dict()` as JSON, and future API/worker code should persist the same shape.

## Result JSON

```json
{
  "status": "completed",
  "frames": 300,
  "total_frames": 300,
  "counts": {
    "lane_1": {
      "car": 12,
      "bus": 1,
      "truck": 2,
      "motorcycle": 4
    }
  },
  "total_count": 19,
  "outputs": {
    "video_path": "outputs/demo_counted.mp4",
    "events_jsonl_path": "outputs/demo_events.jsonl"
  }
}
```

## Fields

- `status`: currently `completed` for successful engine returns. Failures are reported through `progress_callback` before the exception is re-raised.
- `frames`: number of frames actually processed.
- `total_frames`: effective frame count after applying `max_frames`; can be `null` if OpenCV cannot determine it.
- `counts`: nested map of `lane_id -> class_name -> count`.
- `total_count`: sum of all lane/class counts in `counts`.
- `outputs.video_path`: output overlay video path when requested, otherwise `null`.
- `outputs.events_jsonl_path`: JSONL event stream path when requested, otherwise `null`.

## Event JSONL

When `output_jsonl_path` is provided, each counted crossing is written as one JSON object per line:

```json
{"frame_index":149,"track_id":42,"lane_id":"lane_1","class_name":"car","point":[620.0,520.0]}
```

## Notes

- Paths are local filesystem paths in the worker/runtime environment. API code can translate them to public URLs later.
- `counts` can contain empty per-lane maps when no objects are counted.
