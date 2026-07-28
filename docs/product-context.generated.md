# TrafficFlow product context

## Scope

TrafficFlow is a video and live-stream vehicle-counting platform. The current
product is a single-service pilot with FastAPI, MongoDB, Redis/Celery, local or
R2 object storage, and an inference worker.

## Critical workflows

1. Upload video → validate → normalize → store preview/media.
2. Save ROI/lane geometry → atomically claim task → enqueue worker.
3. Worker downloads media → inference/tracking/counting → uploads artifacts → authenticated callback.
4. Client polls status/result and retrieves private assets.
5. Resolve live URL → snapshot → validate geometry → start/stop live session.

## Data classes

- Uploaded videos, previews, rendered result videos and event logs: private media.
- Lane geometry and camera identifiers: operational configuration.
- Task status, progress, errors and counts: operational telemetry/results.
- MongoDB/Redis/R2 credentials and callback/API tokens: secrets.

## Access model

The current implementation supports a pilot bearer token and a separate worker
callback token. Full users, ownership, RBAC and tenant isolation are not yet
implemented; therefore this release is not approved as a public multi-tenant
SaaS.

## Environment policy

Local JSON storage and placeholder R2 credentials are development-only. A
production process must fail fast unless MongoDB, Redis, private object access,
API auth, callback auth and shared rate limiting are configured.
