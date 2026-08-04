# Phase 00 Repository Audit

Status: PASS on 2026-07-17 after a scoped baseline-fix pass.

This wiki page mirrors the Phase 00 report requested from `docs/raw/plan (2).md`.

Primary report:

- `docs/reports/phase-00-repository-audit.md`

Artifacts:

- `docs/portfolio/project-scope-and-ownership.md`
- `benchmark/baseline/current_defaults.yaml`
- `benchmark/baseline/environment.json`
- `benchmark/baseline/model_inventory.json`

Key findings:

- Live path runs in FastAPI API process via `src/api/services/live_service.py`.
- Upload path runs in Celery worker via `src/worker/celery_app.py`.
- Current Docker live baseline uses `models/yolo11m.pt`, 640 image size, `ROI_MODE=crop_rect`, and 15 FPS FFmpeg pacing.
- Phase 00 validation now passes with the project `.venv`: 151 tests passed, `compileall` passed, `git diff --check` passed, and `docker compose config` passed.
- Scoped baseline fixes resolved the live local-client constructor mismatch, upload worker lane/crop-mode alignment, local class-id parsing, and stale config-default test expectations.
- Existing DETRAC numbers are historical until Phase 01+ freeze protocol/split/run manifests.

Stop gate:

- Await user review before Phase 01.
