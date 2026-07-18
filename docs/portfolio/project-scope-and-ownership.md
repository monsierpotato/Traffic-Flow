# TrafficFlow Project Scope and Ownership

## Status

Phase 00 audit artifact. This page defines claim boundaries before portfolio and CV work.

## Project Framing

TrafficFlow is a five-member team project for uploaded-video and live traffic-stream vehicle counting. The product includes API/backend services, Celery worker processing, storage, frontend annotation/dashboard UI, and the AI counting pipeline.

Personal ownership should be stated as AI Pipeline Engineer / Computer Vision contributor, not full-stack product owner.

## Ownership Matrix

| Module | Personal role | Team role | Evidence |
|---|---|---|---|
| ROI processing | Primary owner for AI-side crop/coordinate semantics | Frontend editor and integration shared | `src/worker/pipeline/processor.py`, `src/api/services/live_service.py`, `docs/contracts/annotation_roi.md` |
| Lane geometry | Primary owner for AI-side lane/counting semantics | UI annotation flow shared | `src/worker/services/counting_service.py`, `src/api/routes/live.py`, `docs/wiki/ai-workflow/roi-annotation.md` |
| Detection integration | Primary owner for model integration/evaluation path | Deployment/runtime integration shared | `src/tfengine/core_ai/detector.py`, `src/worker/pipeline/local_client.py`, `benchmark/run_benchmark.py` |
| Pre-tracker filtering | Primary owner | Integration shared | `src/worker/pipeline/detection_filter.py`, `src/api/services/live_service.py` |
| Tracking | Primary owner | Review/integration shared | `src/worker/pipeline/tracker.py`, `tests/test_live_stream_hardening.py` |
| Counting | Primary owner | QA/review shared | `src/worker/services/counting_service.py`, `tests/test_counting_methods.py` |
| Evaluation/benchmark | Primary owner for AI benchmark design and report | QA support | `benchmark/`, `docs/reports/phase-00-repository-audit.md` |
| Live profiling/runtime validation | Analysis and validation lead | Live platform integration shared | `src/api/services/live_service.py`, `docs/wiki/ai-workflow/gpu-docker-live-optimization.md` |
| Frontend | Not primary owner | Team owned | `frontend/`, `docs/wiki/frontend-deploy-readiness.md` |
| General backend platform | Not primary owner | Team owned | `src/api/`, `src/shared/`, `src/worker/celery_app.py` |
| Storage/auth/general DevOps | Not primary owner | Team owned | `src/shared/r2_client.py`, `docker-compose.yml` |

## Allowed Wording

- "Owned the computer-vision pipeline for lane-level traffic analytics..."
- "Designed and evaluated ROI, detection, tracking, lane association, direction validation, and counting logic..."
- "Led analysis and validation of live AI-runtime bottlenecks..."
- "Contributed to live platform integration with the team..."

## Disallowed Wording

- "Built the entire full-stack product alone."
- "Owned all backend, frontend, storage, and deployment."
- "Achieved X accuracy/FPS" unless the value maps to a benchmark report, run ID, and raw source.

## Current Evidence Gaps

- No frozen sequence split yet.
- No final benchmark protocol yet.
- Existing DETRAC numbers are historical and should not be used as final CV claims.
- Live 15 FPS observation is useful historical evidence, but CV wording needs a formal soak test from Phase 08.

