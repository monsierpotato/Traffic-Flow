# TrafficFlow Benchmark

This directory contains the frozen benchmark protocol and reproducible runner artifacts for the portfolio benchmark phases.

## Frozen Inputs

- Protocol: `benchmark/configs/benchmark_protocol_v1.yaml`
- Split: `benchmark/splits/ua_detrac_split_v1.json`
- Class mapping: `benchmark/configs/class_mapping_v1.yaml`
- Geometry: `benchmark/configs/geometry_manual/<sequence>.json`
- Derived counting GT: `benchmark/ground_truth/derived_events/<sequence>.jsonl`

## Phase 03 Smoke Run

The Phase 03 runner validates run manifest and artifact plumbing without using the frontend:

```bash
python -m benchmark.run \
  --protocol benchmark/configs/benchmark_protocol_v1.yaml \
  --model models/yolo11m.pt \
  --config benchmark/configs/runs/yolo11m_640.yaml \
  --geometry-dir benchmark/configs/geometry_manual \
  --derived-events-dir benchmark/ground_truth/derived_events \
  --output benchmark/runs/phase03-smoke-manual-geometry
```

The current smoke backend is `derived_gt_smoke`. It writes raw detection, track, and counting-event artifacts from UA-DETRAC GT so that manifest/output handling is testable before Phase 04 model scoring.

Real model detection, tracking, counting, and runtime scoring should use the same protocol, split, manual geometry directory, run config, manifest schema, and output layout.

## Phase 06 Counting Evaluator

Oracle counting evaluator:

```powershell
.venv\Scripts\python.exe -m benchmark.counting_eval `
  --buckets development,held_out_test `
  --pred-events-dir benchmark\runs\phase03-smoke-manual-geometry-20260718\raw_counting_events `
  --output-dir benchmark\predictions\counting\phase06-oracle-counting-manual-geometry-20260718
```

This evaluates event matching and aggregate count metrics from GT-backed prediction events. It is not an end-to-end YOLO + tracker + counting score.

## End-to-End Tracker Comparison

Production-relevance benchmark:

```powershell
docker run --rm --gpus all -e PYTHONPATH=/workspace/src `
  -v "${PWD}:/workspace" -w /workspace trafficflow:latest `
  python -m benchmark.end_to_end_eval `
  --bucket held_out_test `
  --model models/yolov8m.pt `
  --imgsz 640 `
  --device 0 `
  --output-dir benchmark/predictions/end_to_end/e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718
```

This compares direct ByteTrack against the current TrafficFlow production path: ByteTrack detections re-tracked by `LocalTracker` before counting. Docker generates predictions; host `.venv` currently runs TrackEval because the Docker image does not include `trackeval`.

## Phase 07 Upload Runtime Benchmark

Full uploaded-video AI-path runtime benchmark:

```powershell
docker run --rm --gpus all -e PYTHONPATH=/workspace/src `
  -v "${PWD}:/workspace" -w /workspace trafficflow:latest `
  python -m benchmark.batch_runtime_eval `
  --workloads short:development:MVI_20035,short:development:MVI_20012,available_max:development:MVI_40241 `
  --variants bytetrack,trafficflow_production `
  --model models/yolov8m.pt `
  --imgsz 640 `
  --device 0 `
  --warmup-frames 10 `
  --output-dir benchmark/predictions/runtime/phase07-upload-runtime-bytetrack-production-docker-gpu-20260718-v2
```

This measures decode, full-frame resize/letterbox, YOLO/ByteTrack inference, tracking, counting, overlay rendering, output-video encoding, and resource samples. Reports are written to `benchmark/reports/batch_runtime_report.md`, `benchmark/reports/batch_runtime_summary.csv`, `benchmark/reports/stage_latency.csv`, and `benchmark/reports/resource_usage.csv`.

## Phase 08 Live/HLS Runtime Benchmark

Minimum 30-minute YouTube HLS soak benchmark:

```powershell
.venv\Scripts\python.exe -m benchmark.live_runtime_eval `
  --source-url https://youtu.be/sJvEFrG0wq0 `
  --config-file benchmark\configs\geometry_live\YT_sJvEFrG0wq0_live.json `
  --duration-s 1800 `
  --warmup-s 60 `
  --sample-interval-s 5 `
  --frame-skip 1 `
  --output-dir benchmark\predictions\live_runtime\phase08-live-hls-30min-20260718
```

The runner resolves YouTube through the API, validates live geometry, starts a live session, samples runtime status/frame/resource metrics, removes the session at the end, and writes `benchmark/reports/live_runtime_report.md`, `benchmark/reports/live_runtime_timeseries.csv`, and `benchmark/reports/live_resource_timeseries.csv`.

## Phase 09 Ablation And Error Analysis

Generate tracker/live ablation summary, ROI blocker row, taxonomy counts, and representative error frames from frozen Phase 04-08 artifacts:

```powershell
.venv\Scripts\python.exe -m benchmark.phase09_analysis --print-summary
```

Outputs are written to `benchmark/reports/ablation_report.md`, `benchmark/reports/ablation_summary.csv`, `benchmark/reports/error_taxonomy.csv`, `benchmark/reports/phase09_error_examples.csv`, and `benchmark/reports/phase09_error_frames/`.

## Required Run Artifacts

Each run directory must keep:

- `manifest.json`
- `summary.json`
- `summary.csv`
- `summary.md`
- `raw_detections/*.jsonl`
- `raw_tracks/*.jsonl`
- `raw_counting_events/*.jsonl`
- `stage_timings.csv`
- `resource_samples.csv`
- `config_snapshot/`

The runner refuses to write into a non-empty output directory so run IDs are not overwritten accidentally.
