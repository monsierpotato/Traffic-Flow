# Documentation

TrafficFlow has detailed engineering notes, but the recommended public reading path is short. Start with the docs below and use the wiki/raw notes only when you need audit history.

## Recommended Reading

| Reader | Start with | Why |
|---|---|---|
| Recruiter | [portfolio/recruiter-overview.md](portfolio/recruiter-overview.md) | One-minute summary, role scope, and measured results |
| Hiring manager | [portfolio/project-scope-and-ownership.md](portfolio/project-scope-and-ownership.md) | Separates personal AI/CV ownership from team-owned product work |
| ML/CV interviewer | [portfolio/ai-pipeline.md](portfolio/ai-pipeline.md) and [portfolio/benchmark-methodology.md](portfolio/benchmark-methodology.md) | Explains the pipeline, split policy, metrics, and leakage controls |
| Runtime reviewer | [portfolio/runtime-optimization-case-study.md](portfolio/runtime-optimization-case-study.md) | Explains live/HLS scheduling and measured stability |
| Local evaluator | [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) | Native Node.js + Python setup |
| API integrator | [API_INTEGRATION.md](API_INTEGRATION.md) and [contracts/](contracts/) | Endpoint, callback, lane config, and result contracts |

## Evidence Reports

| Report | Covers |
|---|---|
| [reports/phase-04-detection-benchmark.md](reports/phase-04-detection-benchmark.md) | Detector comparison and selected YOLOv8m result |
| [reports/end-to-end-bytetrack-production-comparison.md](reports/end-to-end-bytetrack-production-comparison.md) | Final direct ByteTrack vs production re-tracker comparison |
| [reports/phase-07-upload-runtime.md](reports/phase-07-upload-runtime.md) | Uploaded-video runtime throughput |
| [reports/phase-08-live-runtime.md](reports/phase-08-live-runtime.md) | Live/HLS 30-minute soak |
| [reports/phase-09-ablation-error-analysis.md](reports/phase-09-ablation-error-analysis.md) | Error taxonomy and known evidence gaps |

## Repository Layout

```text
src/api/        FastAPI routes, schemas, and services
src/worker/     Celery tasks and video pipeline
src/tfengine/   Shared AI/runtime engine
frontend/       React + Vite application
benchmark/      Benchmark parsers, runners, metrics, and configuration
scripts/        Local orchestration, preflight, and utility scripts
```

## Documentation Classification

- `docs/portfolio/`: curated public-facing docs for recruiters and technical interviewers.
- `docs/reports/`: concise public summaries of benchmark phases and final review.
- `docs/contracts/`: API and data contracts that should not change casually.
- `docs/wiki/`: detailed project memory and design history.
- `docs/raw/`: source notes and meeting/planning inputs; not first-read material.
