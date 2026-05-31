# Lane Detection Benchmark Summary

## Hardware

- CPU:
- GPU:
- RAM:
- PyTorch:
- CUDA:

## FPS Result

| Method | Backbone / Variant | Video 1 FPS | Video 2 FPS | Video 3 FPS | Avg FPS | Avg latency | VRAM |
|---|---|---:|---:|---:|---:|---:|---:|
| UFLD | ResNet18 / TuSimple | 313.92 | 309.98 | 303.40 | 309.10 | 3.24 ms | 16 GB |
| PolyLaneNet | ResNet50 / TuSimple | 106.17 | 102.61 | 107.21 | 105.33 | 9.50 ms | 16 GB |
| LaneATT | ResNet18 / TuSimple | 122.58 | 137.53 | 130.50 | 130.20 | 7.70 ms | 16 GB |
| ENet-SAD | Torch7 official / PyTorch reimpl no checkpoint |  |  |  |  | Blocked |  |
| UFLDv2 | ResNet18 |  |  |  |  |  |  |
| LaneATT | ResNet18 |  |  |  |  |  |  |
| CondLaneNet | Small |  |  |  |  |  |  |

## Qualitative Result

| Method | Lane visibility | Stability | Occlusion | Curve/Merge | Integration readiness | Total |
|---|---:|---:|---:|---:|---:|---:|
| UFLD | 3 | 3 | 2 | 2 | 3 | 13 |
| PolyLaneNet | 2 | 1 | 1 | 1 | 4 | 9 |
| LaneATT | 2 | 3 | 2 | 2 | 3 | 12 |
| ENet-SAD |  |  |  |  | Blocked |  |

## TrafficFlow Integration Result

| Method | Easy to convert to polyline | Easy to assign lane | Stable for counting | Needs fine-tuning | Recommended role |
|---|---|---|---|---|---|
| UFLD | Medium | Medium | Medium | Yes for CCTV | Speed baseline / fallback |
| PolyLaneNet | High | High in schema, low in current quality | Low on current clips | Yes for CCTV/domain | Geometry-friendly benchmark candidate |
| LaneATT | Medium | Medium | Medium | Yes for CCTV/domain | Third runnable benchmark method |
| ENet-SAD | High if mask available | Medium | Not tested | Requires usable PyTorch weights or Torch7 env | Blocked lightweight segmentation candidate |

## Final Decision

- Main method:
- Fallback method:
- Upgrade method:
- Lý do chọn:
- Rủi ro còn lại:
- Việc cần làm tiếp theo:
