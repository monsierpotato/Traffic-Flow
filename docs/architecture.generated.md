# TrafficFlow backend architecture

```text
Frontend → FastAPI control plane
              ├─ auth, request IDs, rate limiting, validation
              ├─ MongoDB repositories/collections
              ├─ private asset endpoint → R2 or local development storage
              └─ Redis/Celery task enqueue
                                ↓
                         Celery worker
                  download → inference → artifacts
                                ↓
                         authenticated callback
```

## Boundaries

- `src/api`: HTTP contracts, authentication boundary and request orchestration.
- `src/shared`: settings, persistence adapter and object storage adapter.
- `src/worker`: batch processing and callback delivery.
- `src/tfengine`: geometry, tracking and counting domain logic.

## Production invariants

- No public mount of the storage root.
- Every protected route is authenticated; callbacks use a distinct token.
- User-controlled media URLs pass scheme, DNS and private-network checks.
- Task enqueue uses a compare-and-set claim and optional idempotency key.
- Worker and API consume the same configured Celery queue.
- MongoDB fallback is disabled in production.
- R2 URLs are private/presigned in production.
