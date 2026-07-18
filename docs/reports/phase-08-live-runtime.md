# Phase 08 Live/HLS Runtime Benchmark

- Run ID: `phase08-live-hls-30min-20260718`
- Source type: `youtube_hls`
- Source: `1920x1080 @ 30.0 FPS`
- Duration: `1803.284` seconds, warmup `60.0` seconds
- Model/runtime: `models/yolo11m.pt`, imgsz `640`, ROI mode `crop_rect`

## Scope

This phase measures live runtime and stability only. No live GT was available, so count totals are operational outputs, not accuracy metrics.

Ownership wording: the candidate led bottleneck analysis and AI-runtime validation; live-platform integration remains shared team work.

## Summary Metrics

| Metric | Value |
| --- | ---: |
| Processed FPS overall | 14.895 |
| Published FPS overall | 14.895 |
| Processed FPS p50/p95/p99 | 15.0 / 15.2 / 15.2 |
| Published FPS p50/p95/p99 | 15.0 / 15.2 / 15.2 |
| Frame interarrival p50/p95/p99 ms | 66.7 / 66.8 / 66.8 |
| Frame age p50/p95/p99 ms | 0.8 / 0.9 / 1.0 |
| Inference wall p50/p95/p99 ms | 14.8 / 24.03 / 26.553 |
| Dropped-frame ratio | 0.0 |
| Stale-frame sample ratio | 0.0 |
| Time to first inferred frame s | 13.164 |
| Reconnect count from logs | 0 |
| Stall count/hour | 0.0 |
| Total stall duration s | 0.0 |
| Session error count | 0 |
| Unexpected tracker reset count from logs | 0 |
| GPU util avg/p95 % | 15.442 / 24.1 |
| VRAM peak MB | 2525.0 |
| API container RAM start/end/peak MB | 1815.552 / 2132.992 / 2137.088 |
| Operational lane volume total | 43 |

## Artifacts

- `benchmark/reports/live_runtime_timeseries.csv`
- `benchmark/reports/live_resource_timeseries.csv`
- Run manifest: `benchmark/predictions/live_runtime/phase08-live-hls-30min-20260718/manifest.json`
- Run summary: `benchmark/predictions/live_runtime/phase08-live-hls-30min-20260718/live_runtime_summary.json`
- API log signal extract: `benchmark/predictions/live_runtime/phase08-live-hls-30min-20260718/api_log_signals.txt`

## Gate

Phase 08 report is complete. Per plan, stop before Phase 09 ablations.
