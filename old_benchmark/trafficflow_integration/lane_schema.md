# Lane Output Schema

Mọi method lane detection cần convert về schema chung này trước khi dùng cho overlay, gán xe vào làn, hoặc benchmark.

```json
{
  "video_id": "traffic_01",
  "frame_id": 120,
  "method": "LaneATT",
  "lanes": [
    {
      "lane_id": 1,
      "confidence": 0.91,
      "points": [[420, 720], [430, 680], [445, 640], [465, 600]],
      "type": "polyline"
    }
  ],
  "runtime": {
    "preprocess_ms": 3.2,
    "inference_ms": 8.7,
    "postprocess_ms": 2.1,
    "total_ms": 14.0,
    "fps": 71.4
  },
  "meta": {}
}
```

## Quy ước

- `points` dùng tọa độ pixel ảnh gốc theo thứ tự từ gần camera tới xa camera, nếu method hỗ trợ.
- `confidence` có thể `null` nếu repo không trả score.
- `type` mặc định là `polyline`.
- Nếu cần gán xe vào lane, ưu tiên dùng điểm đáy bounding box của vehicle: `((x1 + x2) / 2, y2)`.
