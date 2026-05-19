# Qualitative Lane Benchmark

Chấm mỗi tiêu chí từ 1 đến 5.

| Video | Method | Lane visibility | Stability | Occlusion robustness | Curve / merge / split | Integration readiness | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| traffic_01 | UFLD | 3 | 3 | 2 | 2 | 3 | Detects visible lanes but misses/shortens some lines in time-lapse view. |
| traffic_01 | PolyLaneNet | 2 | 1 | 1 | 1 | 4 | Produces polynomial output, but several predicted lanes cross or hallucinate. |
| traffic_01 | LaneATT | 3 | 3 | 2 | 2 | 3 | More conservative than PolyLaneNet; detects a plausible lane but misses some visible markings. |
| traffic_01 | ENet-SAD |  |  |  |  |  | Blocked: official weight is Torch7 `.t7`; no PyTorch pretrained checkpoint. |
| traffic_02 | UFLD | 1 | 2 | 1 | 1 | 2 | Few usable lane cues in this stock clip. |
| traffic_02 | PolyLaneNet | 1 | 1 | 1 | 1 | 4 | Strong hallucination on sky/road-horizon scene. |
| traffic_02 | LaneATT | 1 | 2 | 1 | 1 | 3 | Also hallucinates a lane in the sky/road-horizon scene, but less cluttered than PolyLaneNet. |
| traffic_02 | ENet-SAD |  |  |  |  |  | Blocked: official weight is Torch7 `.t7`; no PyTorch pretrained checkpoint. |
| traffic_03 | UFLD | 3 | 3 | 2 | 2 | 3 | Detects some night lanes but quality is limited by blur/light streaks. |
| traffic_03 | PolyLaneNet | 2 | 1 | 1 | 1 | 4 | Predicts multiple crossing lanes; not stable enough for counting. |
| traffic_03 | LaneATT | 2 | 3 | 2 | 2 | 3 | Conservative detection; fewer artifacts but misses several night lane markings. |
| traffic_03 | ENet-SAD |  |  |  |  |  | Blocked: official weight is Torch7 `.t7`; no PyTorch pretrained checkpoint. |
