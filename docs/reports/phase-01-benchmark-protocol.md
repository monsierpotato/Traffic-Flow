# Phase 01 - Benchmark Protocol and Dataset Split

## Status

PASS

Phase 01 freezes the UA-DETRAC inventory, split, class mapping, metric definitions, and runtime protocol before model/counting tuning phases.

## Mục tiêu

Tạo benchmark protocol có thể dùng cho portfolio mà không rò rỉ test set hoặc dùng lại các kết quả DETRAC cũ thiếu split/manifest.

## Phạm vi đã hoàn thành

- Inventory toàn bộ UA-DETRAC XML sequences có image directories trong repo.
- Parse metadata theo sequence: frame count, image count, resolution, GT track count, raw/mapped class distribution, camera state, weather, official split.
- Freeze split v1 theo full sequence.
- Freeze class mapping từ nhãn thật trong annotations.
- Freeze metric definitions cho detection, tracking, counting, và runtime.
- Tạo methodology document cho portfolio.
- Mirror báo cáo vào wiki theo yêu cầu người dùng.

## Artifact tạo mới

- `benchmark/splits/ua_detrac_inventory_v1.json`
- `benchmark/splits/ua_detrac_split_v1.json`
- `benchmark/configs/class_mapping_v1.yaml`
- `benchmark/configs/benchmark_protocol_v1.yaml`
- `docs/portfolio/benchmark-methodology.md`
- `docs/reports/phase-01-benchmark-protocol.md`
- `docs/wiki/ai-workflow/phase-01-benchmark-protocol.md`

## Dataset Inventory

Source roots:

- XML train: `benchmark/detrac/ua-detrac-orig/DETRAC-Train-Annotations-XML/DETRAC-Train-Annotations-XML`
- XML test: `benchmark/detrac/ua-detrac-orig/DETRAC-Test-Annotations-XML/DETRAC-Test-Annotations-XML`
- Images: `benchmark/detrac/ua-detrac-orig/DETRAC-Images/DETRAC-Images`

Summary:

| Metric | Value |
|---|---:|
| Total XML sequences with images | 100 |
| Official train sequences | 60 |
| Official test sequences | 40 |
| Resolution distribution | 100 x 960x540 |
| XML FPS field | Not present |
| Nominal conversion FPS | 25 |
| Raw GT tracks | 8289 |
| Mapped GT tracks | 8215 |
| Ignored raw `others` tracks | 74 |

Weather distribution:

| Weather | Sequences |
|---|---:|
| cloudy | 30 |
| night | 28 |
| rainy | 19 |
| sunny | 23 |

Camera-state distribution:

| Camera state | Sequences |
|---|---:|
| stable | 53 |
| unstable | 47 |

## Frozen Split v1

Split file: `benchmark/splits/ua_detrac_split_v1.json`.

Rules:

- Split unit is `full_sequence`.
- Random frame split is forbidden.
- `held_out_test` must not be used for tuning.
- `reserve_only` cannot be moved into development or held-out scoring without a protocol bump.

Buckets:

| Bucket | Sequence count | Frames | Mapped GT tracks | Official split |
|---|---:|---:|---:|---|
| `smoke_test` | 1 | 664 | 52 | train |
| `development` | 8 | 12593 | 1357 | train |
| `held_out_test` | 5 | 8359 | 509 | test |
| `reserve_only` | 86 | 116636 | 6297 | train/test reserve |

Selected sequences:

| Bucket | Sequences |
|---|---|
| `smoke_test` | `MVI_20011` |
| `development` | `MVI_20012`, `MVI_20035`, `MVI_40241`, `MVI_40213`, `MVI_40752`, `MVI_40963`, `MVI_63553`, `MVI_41063` |
| `held_out_test` | `MVI_40892`, `MVI_39401`, `MVI_40793`, `MVI_40854`, `MVI_40761` |

Held-out v1 covers all weather labels present in the local UA-DETRAC extract and both stable/unstable camera states.

## Class Mapping

Class mapping file: `benchmark/configs/class_mapping_v1.yaml`.

Observed raw labels and policy:

| Raw label | Track count | TrafficFlow class | Policy |
|---|---:|---|---|
| `car` | 7167 | `car` | exact |
| `bus` | 311 | `bus` | exact |
| `van` | 737 | `truck` | nearest supported vehicle class |
| `others` | 74 | ignored | unknown vehicle type |

Important limitation: UA-DETRAC annotations in this repo do not contain a motorcycle-compatible raw label. Motorcycle metrics must not be claimed from this dataset.

## Metric Definitions

Protocol file: `benchmark/configs/benchmark_protocol_v1.yaml`.

Detection:

- AP50
- AP50:95
- precision
- recall
- F1

Tracking:

- HOTA
- DetA
- AssA
- IDF1
- IDSW
- Frag

Counting:

- Derived task-specific counting ground truth.
- Event metrics: event precision/recall/F1, missed crossing rate, false crossing rate, duplicate count rate, wrong lane/class/direction rates, median and p95 crossing-time error.
- Aggregate metrics: MAE, RMSE, WAPE, signed bias, exact-count accuracy, within-1 accuracy.
- Aggregate unit: `video x lane x class x direction`.
- Event match tolerance: 5 frames.
- Matching: one-to-one Hungarian preferred.

Runtime:

- Uploaded-video stages: decode, preprocess, inference, tracking, counting, rendering, encoding.
- Live metrics: processed/published FPS, frame interarrival, frame age, dropped/stale frame ratios, inference wall time, reconnects/stalls, peak VRAM, GPU utilization.
- Warmup frames: 30.
- Timing percentiles: p50, p95, p99.

## Decisions

- Use full-sequence split only; no frame-level random split.
- Use official train sequences for `smoke_test` and `development`.
- Use official test sequences for `held_out_test`.
- Keep the remaining 86 sequences as `reserve_only` to prevent accidental tuning drift.
- Treat old DETRAC benchmark numbers as historical until rerun under this protocol with run manifests.
- Use nominal 25 FPS only for image-sequence conversion because XML files do not encode FPS.
- Require every geometry, detection, track, event, and report artifact to declare coordinate space.

## Validation

Validation was run after writing the artifacts:

- `.venv\Scripts\python.exe -m pytest tests -q`
- `.venv\Scripts\python.exe -m compileall -q src benchmark`
- `git diff --check`
- Structured artifact validation for JSON parse, no split overlap, selected sequence existence, inventory count, held-out official split, class distribution, protocol sentinel fields, and secret scan.
- Wiki Obsidian link validation for `docs/wiki`.

Final validation result: PASS.

## Known limitations

- FPS is not encoded in the local UA-DETRAC XML files; actual FPS must be recorded per generated/evaluated video.
- The split is intentionally small for v1. It is designed for controlled portfolio benchmarking, not a full academic DETRAC benchmark.
- Counting ground truth still needs Phase 02 derivation and manual audit.
- No benchmark performance numbers were generated in Phase 01.
- Host `.venv` is CPU-only from Phase 00; final timing metrics should use Docker GPU or a CUDA validation environment.

## STOP GATE

Phase 01 is complete and frozen. Per `docs/raw/plan (2).md`, do not move to Phase 02 until the user reviews and confirms this stop gate.
