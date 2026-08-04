# End-to-End ByteTrack vs TrafficFlow Production Comparison

Run date: 2026-07-18.

## Scope

This benchmark compares two end-to-end branches using the selected detector `models/yolov8m.pt` on full UA-DETRAC selected sequences with manual geometry:

- `bytetrack`: Ultralytics YOLO `model.track(..., tracker="bytetrack.yaml")` outputs used directly for lane filtering and counting.
- `trafficflow_production`: current product path, Ultralytics YOLO + ByteTrack detections, lane/class filter, then TrafficFlow `LocalTracker` Kalman re-tracker, then counting.

This is the production-relevance layer missing from the earlier oracle benchmarks. Phase 04 isolated detection, Phase 05 isolated tracking using GT detections, and Phase 06 isolated counting scoring. This report measures the connected YOLO + tracker + counting path.

## Runs

- Smoke: `benchmark/predictions/end_to_end/e2e-smoke-bytetrack-vs-production-full-docker-gpu-20260718/`
- Development: `benchmark/predictions/end_to_end/e2e-dev-bytetrack-vs-production-full-docker-gpu-20260718/`
- Held-out: `benchmark/predictions/end_to_end/e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718/`

Docker GPU generated YOLO/ByteTrack artifacts. Host `.venv` ran TrackEval on the generated MOT files because the Docker image does not currently include `trackeval`.

## Tracking Metrics

| Bucket | Variant | HOTA | IDF1 | MOTA | IDSW | Frag |
|---|---|---:|---:|---:|---:|---:|
| development | bytetrack | 0.249929 | 0.403836 | 0.239511 | 34 | 193 |
| development | trafficflow_production | 0.201410 | 0.306618 | 0.175529 | 284 | 419 |
| held_out_test | bytetrack | 0.242433 | 0.284952 | 0.179535 | 42 | 173 |
| held_out_test | trafficflow_production | 0.215225 | 0.224661 | 0.166052 | 169 | 219 |

## Counting Metrics

| Bucket | Variant | Event P | Event R | Event F1 | WAPE | Miss rate | False rate |
|---|---|---:|---:|---:|---:|---:|---:|
| development | bytetrack | 0.872677 | 0.826585 | 0.849005 | 0.202465 | 0.173415 | 0.127323 |
| development | trafficflow_production | 0.895070 | 0.623239 | 0.734821 | 0.305458 | 0.376761 | 0.104930 |
| held_out_test | bytetrack | 0.945652 | 0.938849 | 0.942238 | 0.050360 | 0.061151 | 0.054348 |
| held_out_test | trafficflow_production | 0.918103 | 0.766187 | 0.835294 | 0.194245 | 0.233813 | 0.081897 |

## Interpretation

ByteTrack direct is stronger in this end-to-end benchmark:

- Better held-out counting: Event F1 `0.942238` vs `0.835294`, WAPE `0.050360` vs `0.194245`.
- Better held-out tracking: HOTA `0.242433` vs `0.215225`, IDF1 `0.284952` vs `0.224661`.
- Fewer held-out ID switches: `42` vs `169`.
- Lower held-out fragmentation: `173` vs `219`.

The production Kalman re-tracker improves neither end-to-end tracking nor counting on this benchmark. It also misses more crossing events, which lowers recall and increases WAPE.

## Recommendation

For portfolio reporting and the next production candidate, treat direct ByteTrack as the current end-to-end baseline. Keep `trafficflow_production` as the current implementation baseline, but do not present it as the best measured tracker/counting path.

Before changing runtime defaults, run one live/upload regression pass because the Kalman re-tracker was originally added for live low-FPS gaps and stale/lost-track cleanup. The benchmark evidence now says that, on full UA-DETRAC offline sequences, direct ByteTrack is the better measured path.

## Limitations

- UA-DETRAC has no motorcycle-compatible GT label, so motorcycle counting is not scored.
- Tracking metrics use TrackEval MotChallenge2DBox with all mapped vehicles encoded as class id 1.
- The benchmark uses full-frame source-frame manual geometry, not ROI crop inference.
- Docker image generated predictions but does not include `trackeval`; TrackEval was run from host `.venv` on generated MOT artifacts.
