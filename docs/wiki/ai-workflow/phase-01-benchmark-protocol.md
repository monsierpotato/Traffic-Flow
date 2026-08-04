# Phase 01 Benchmark Protocol

Status: PASS on 2026-07-17.

This wiki page mirrors the Phase 01 report requested from `docs/raw/plan (2).md`.

Primary report:

- `docs/reports/phase-01-benchmark-protocol.md`

Artifacts:

- `benchmark/splits/ua_detrac_inventory_v1.json`
- `benchmark/splits/ua_detrac_split_v1.json`
- `benchmark/configs/class_mapping_v1.yaml`
- `benchmark/configs/benchmark_protocol_v1.yaml`
- `docs/portfolio/benchmark-methodology.md`

Key decisions:

- UA-DETRAC v1 split unit is full sequence; random frame split is forbidden.
- Frozen buckets: 1 smoke sequence, 8 development sequences, 5 held-out test sequences, 86 reserve-only sequences.
- Held-out test uses official test sequences only and must not be used for tuning.
- Class mapping is based on observed raw labels: `car -> car`, `bus -> bus`, `van -> truck`, `others -> ignored`.
- UA-DETRAC in this repo has no motorcycle-compatible annotation label, so motorcycle metrics must not be reported from this dataset.
- XML files do not encode FPS; protocol uses nominal 25 FPS only when converting image sequences and requires actual FPS in run manifests.
- Existing DETRAC benchmark numbers are historical until rerun under this protocol.

Validation:

- `pytest`: PASS, 151 passed, 1 existing warning.
- `compileall`: PASS for `src` and `benchmark`.
- `git diff --check`: PASS.
- Structured split/config validation: PASS.
- Wiki Obsidian link validation: PASS.

Stop gate:

- Await user review before Phase 02.
