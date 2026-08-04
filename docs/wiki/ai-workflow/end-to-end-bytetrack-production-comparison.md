# End-to-End ByteTrack Production Comparison

Status: PASS on 2026-07-18.

Primary report:

- `docs/reports/end-to-end-bytetrack-production-comparison.md`

Compared branches:

- `bytetrack`: YOLOv8m + Ultralytics ByteTrack + lane/class filter + counting.
- `trafficflow_production`: YOLOv8m + Ultralytics ByteTrack + lane/class filter + TrafficFlow `LocalTracker` Kalman re-tracker + counting.

Held-out result:

| Variant | HOTA | IDF1 | Event F1 | WAPE | IDSW | Frag |
|---|---:|---:|---:|---:|---:|---:|
| bytetrack | 0.242433 | 0.284952 | 0.942238 | 0.050360 | 42 | 173 |
| trafficflow_production | 0.215225 | 0.224661 | 0.835294 | 0.194245 | 169 | 219 |

Decision:

- Direct ByteTrack is the stronger measured end-to-end benchmark path.
- Keep current production Kalman re-tracker documented, but do not present it as the best measured pipeline.
- Before changing runtime defaults, run a live/upload regression pass because the Kalman re-tracker was added for low-FPS live gaps and stale-track cleanup.
