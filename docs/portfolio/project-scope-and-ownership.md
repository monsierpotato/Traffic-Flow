# TrafficFlow Project Scope and Contributions

## Status

Phase 00 audit artifact. This page defines team responsibilities and claim boundaries before portfolio and CV work.

## Project Framing

TrafficFlow is a five-member team project for uploaded-video and live traffic-stream vehicle counting. The product includes API/backend services, Celery worker processing, storage, frontend annotation/dashboard UI, and the AI counting pipeline.

Public project wording should lead with the team system. Individual wording should be scoped to AI Pipeline Engineer / Computer Vision contributor, not full-stack product owner.

## Contribution Matrix

| Module | AI/CV contribution area | Team/shared responsibility | Evidence |
|---|---|---|---|
| ROI processing | AI-side crop/coordinate semantics | Frontend editor and integration shared | `src/worker/pipeline/processor.py`, `src/api/services/live_service.py`, `docs/contracts/annotation_roi.md` |
| Lane geometry | AI-side lane/counting semantics | UI annotation flow and integration shared | `src/worker/services/counting_service.py`, `src/api/routes/live.py`, `docs/wiki/ai-workflow/roi-annotation.md` |
| Detection integration | Model integration and evaluation path | Deployment/runtime integration shared | `src/tfengine/core_ai/detector.py`, `src/worker/pipeline/local_client.py`, `benchmark/run_benchmark.py` |
| Pre-tracker filtering | Class/lane filtering behavior | Integration shared | `src/worker/pipeline/detection_filter.py`, `src/api/services/live_service.py` |
| Tracking | Tracker evaluation and AI-side behavior | Review/integration shared | `src/worker/pipeline/tracker.py`, `tests/test_live_stream_hardening.py` |
| Counting | Counting semantics and evaluator behavior | QA/review shared | `src/worker/services/counting_service.py`, `tests/test_counting_methods.py` |
| Evaluation/benchmark | AI benchmark design and report generation | QA support | `benchmark/`, `docs/reports/phase-00-repository-audit.md` |
| Live profiling/runtime validation | AI-runtime analysis and validation | Live platform integration shared | `src/api/services/live_service.py`, `docs/wiki/ai-workflow/gpu-docker-live-optimization.md` |
| Frontend | Integration consumer of AI/API results | Team responsibility | `frontend/`, `docs/wiki/frontend-deploy-readiness.md` |
| General backend platform | API/runtime integration surface | Team responsibility | `src/api/`, `src/shared/`, `src/worker/celery_app.py` |
| Storage/auth/general DevOps | Runtime dependency surface | Team responsibility | `src/shared/r2_client.py`, `docker-compose.yml` |

## Team-First Wording

- "Built by a five-member team across frontend, backend, worker/runtime, storage, and AI/CV pipeline."
- "Contributed to the AI/CV pipeline for lane-level traffic analytics..."
- "Worked on ROI, detection, tracking, lane association, direction validation, counting logic, and evaluation..."
- "Contributed AI-runtime analysis and validation while live platform integration remained shared team work..."

## Wording To Avoid

- "Built the entire full-stack product alone."
- "Owned all backend, frontend, storage, and deployment."
- "Achieved X accuracy/FPS" unless the value maps to a benchmark report, run ID, and raw source.

## Current Evidence Gaps

- No frozen sequence split yet.
- No final benchmark protocol yet.
- Existing DETRAC numbers are historical and should not be used as final CV claims.
- Live 15 FPS observation is useful historical evidence, but CV wording needs a formal soak test from Phase 08.

