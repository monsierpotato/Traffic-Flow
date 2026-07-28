# Documentation

Documentation is organized into three groups: current operations, integration contracts, and historical/benchmark reports. The currently supported path is `src/` plus the React frontend.

## Start Here

| Document | Use it when |
|---|---|
| [current/architecture.md](current/architecture.md) | Understanding the current modules and data flow |
| [current/operations.md](current/operations.md) | Running locally, checking readiness, and resolving blockers |
| [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) | Running the native Node.js + Python stack |
| [USER_GUIDE.md](USER_GUIDE.md) | Following the detailed usage and operations guide |
| [VERCEL_FRONTEND_DEPLOYMENT.md](VERCEL_FRONTEND_DEPLOYMENT.md) | Deploying only the React frontend to Vercel |
| [API_INTEGRATION.md](API_INTEGRATION.md) | Reviewing endpoints, task states, and callbacks |
| [contracts/](contracts/) | Reviewing lane configuration, callbacks, and result schemas |

## Repository Layout

```text
src/api/        FastAPI routes, schemas, and services
src/worker/     Celery tasks and video pipeline
src/tfengine/   Shared AI/runtime engine
frontend/       React + Vite application
benchmark/      Benchmark parsers, runners, metrics, and configuration
tools/archive/  Historical manual scripts; not used by runtime or CI
```

## Documentation Classification

- `docs/current/`: the source of truth for the current state and run procedures.
- `docs/contracts/`: boundaries that must not be changed casually during refactoring.
- Phase, portfolio, and raw reports were removed from the source tree because they are not required for the current runtime path.
