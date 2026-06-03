# Deploy AI Traffic Work Plan Source

## Summary

This source is the Google Doc planning document for TrafficFlow deployment work. It defines the five-member ownership model, sprint plan, current project progress, backlog priorities, and target MVP.

## Source

- Title: Phan chia cong viec deploy AI Traffic
- URL: https://docs.google.com/document/d/1x_FbgG4XOSfbQDaqcqXk9Rz4iTaEZP2VXozowfbT0KU/edit?usp=sharing
- Raw snapshot: `docs/raw/notes/2026-05-31-google-doc-work-plan.md`
- Fetched: 2026-05-31

## Key Takeaways

- Member 1 owns AI runtime: `TrafficFlowEngine`, progress callback, result contract, and optional ONNX later.
- Member 2 owns frontend upload, canvas lane drawing, coordinate scaling, progress polling, and dashboard.
- Member 3 owns FastAPI, DB schema, upload/preview APIs, task APIs, retention, and file validation.
- Member 4 owns Celery/Redis, worker integration, Docker, docker-compose, error handling/timeouts, and env settings.
- Member 5 owns local end-to-end QA, coordinate alignment, queue stress test, and release/deploy checklist.
- MVP should be local production-like docker-compose before cloud deployment.

## Links

- [[Project Backlog]]
- [[Production Architecture]]
- [[Runtime Engine]]
- [[Lane Config Contract]]
