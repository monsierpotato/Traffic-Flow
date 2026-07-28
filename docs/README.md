# Documentation

TrafficFlow has detailed engineering notes, but the recommended reading path is short. Start with the docs below and use the wiki/raw notes only when you need audit history.

## Recommended Reading

| Need | Start with | Why |
|---|---|---|
| Project overview | [portfolio/project-overview.md](portfolio/project-overview.md) | Short team summary, contribution areas, and measured results |
| Team scope | [portfolio/project-scope-and-ownership.md](portfolio/project-scope-and-ownership.md) | Separates team-owned product work from the AI/CV contribution area |
| AI pipeline details | [portfolio/ai-pipeline.md](portfolio/ai-pipeline.md) and [portfolio/benchmark-methodology.md](portfolio/benchmark-methodology.md) | Explains the pipeline, split policy, metrics, and leakage controls |
| Runtime details | [portfolio/runtime-optimization-case-study.md](portfolio/runtime-optimization-case-study.md) | Explains live/HLS scheduling and measured stability |
| Local setup | [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) | Native Node.js + Python setup |
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

- `docs/portfolio/`: curated project docs for general readers and technical reviewers.
- `docs/reports/`: concise public summaries of benchmark phases and final review.
- `docs/contracts/`: API and data contracts that should not change casually.
- `docs/wiki/`: detailed project memory and design history.
- `docs/raw/`: source notes and meeting/planning inputs; not first-read material.
