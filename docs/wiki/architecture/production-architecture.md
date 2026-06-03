# Production Architecture

## Summary

TrafficFlow is moving from a CLI-first AI prototype toward a production-style system with backend API, background worker, queue, storage, observability, and a reusable AI runtime.

## Current State

- The reusable AI workflow lives in `trafficflow/runtime/engine.py`.
- The CLI entrypoint `trafficflow/cli/run_counting.py` should remain a thin wrapper around the runtime engine.
- Production-facing package boundaries already exist: `trafficflow/api`, `trafficflow/worker`, `trafficflow/queue`, `trafficflow/storage`, and `trafficflow/observability`.

## Target Flow

```text
Frontend
-> Backend API
-> Task queue
-> Worker
-> TrafficFlowEngine
-> Storage/DB
-> API result/status
-> Frontend dashboard
```

## Open Questions

- Which DB will be used first: SQLite for local MVP or PostgreSQL for team integration?
- Which queue implementation will be locked for MVP: Celery + Redis or a simpler local worker?

## Links

- [[Runtime Engine]]
- [[Project Backlog]]
- [[Decision Log]]
