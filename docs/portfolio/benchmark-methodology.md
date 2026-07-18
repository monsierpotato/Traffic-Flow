# Benchmark Methodology

Status: frozen v1 on 2026-07-17.

This document defines the benchmark method for TrafficFlow portfolio results before any new tuning or test-set scoring. Detailed Phase 01 audit evidence is in `docs/reports/phase-01-benchmark-protocol.md`.

## Dataset

Primary dataset: UA-DETRAC local extract under `benchmark/detrac/ua-detrac-orig`.

Inventory file:

- `benchmark/splits/ua_detrac_inventory_v1.json`

Local inventory summary:

| Item | Value |
|---|---:|
| XML sequences with image directories | 100 |
| Official train sequences | 60 |
| Official test sequences | 40 |
| Resolution | 960x540 for all sequences |
| XML FPS field | Not present |
| Nominal FPS for image-sequence conversion | 25 |

The nominal 25 FPS value is used only when converting UA-DETRAC image sequences into videos without a source FPS field. Every benchmark run manifest must still record the actual FPS of the evaluated video artifact.

## Frozen Split

Split file:

- `benchmark/splits/ua_detrac_split_v1.json`

Rules:

- Split unit is the full sequence.
- Random frame split is forbidden.
- A sequence can appear in only one split bucket.
- `held_out_test` cannot be used to tune models, thresholds, tracking parameters, counting rules, or lane geometry.
- Any movement from `reserve_only` into a scored bucket requires a split-version bump and report update.

Frozen v1 buckets:

| Bucket | Sequences | Purpose |
|---|---:|---|
| `smoke_test` | 1 | Pipeline sanity checks only |
| `development` | 8 | Tuning and implementation checks |
| `held_out_test` | 5 | Final scoring only |
| `reserve_only` | 86 | Not used for v1 tuning/scoring |

## Class Mapping

Class mapping file:

- `benchmark/configs/class_mapping_v1.yaml`

Observed UA-DETRAC raw track labels:

| Raw label | Track count | Benchmark policy |
|---|---:|---|
| `car` | 7167 | map to `car` |
| `bus` | 311 | map to `bus` |
| `van` | 737 | map to `truck` |
| `others` | 74 | ignore |

UA-DETRAC annotations in this repo do not contain a motorcycle-compatible label. Do not report motorcycle detection, tracking, or counting metrics from UA-DETRAC.

## Metrics

Protocol file:

- `benchmark/configs/benchmark_protocol_v1.yaml`

Detection metrics:

- AP50
- AP50:95
- precision
- recall
- F1

Tracking metrics:

- HOTA
- DetA
- AssA
- IDF1
- ID switches
- fragmentation

Counting metrics use derived task-specific counting ground truth and are evaluated per `video x lane x class x direction`:

- event precision, recall, F1
- missed crossing rate
- false crossing rate
- duplicate count rate
- wrong lane/class/direction rates
- median and p95 crossing-time error
- MAE, RMSE, WAPE, signed bias
- exact-count and within-1 accuracy

Counting-event matching is one-to-one, same video, same lane, same direction, and exact class or documented mapping. The frozen temporal tolerance is 5 frames.

## Runtime Protocol

Each benchmark run must record:

- git commit
- config snapshot
- model SHA256
- raw predictions
- environment snapshot
- run manifest with actual FPS and coordinate-space declarations

Runtime reporting must separate uploaded-video stages:

- decode
- preprocess
- inference
- tracking
- counting
- rendering
- encoding

Live reporting must include processed FPS, published FPS, frame interarrival percentiles, frame age percentiles, dropped/stale frame ratios, inference wall-time percentiles, reconnect/stall counts, peak VRAM, and GPU utilization.

## Anti-Leakage Policy

After Phase 01:

- `held_out_test` is frozen.
- Development/tuning work must use only `smoke_test`, `development`, and explicitly documented synthetic/local diagnostic inputs.
- Held-out results are generated once the implementation and configs are frozen for the relevant phase.
- If the held-out test result reveals a weakness, the fix must be developed without reusing held-out labels for tuning, or the protocol version must be bumped.
