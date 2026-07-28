# TrafficFlow test strategy

## Fast local gate

```bash
PYTHONPATH=src .venv/bin/python -m compileall -q src tests
PYTHONPATH=src .venv/bin/python -m pytest -q tests
```

## PR gate

- Ruff fatal quality checks.
- Bandit high-severity scan.
- Unit, API contract and security tests.
- Frontend production build.
- JUnit and coverage artifacts.

## Staging gate

- MongoDB, Redis, R2 and inference service health.
- Synthetic upload → lane config → queue → worker → result flow.
- Callback duplicate/out-of-order tests.
- SSRF, authorization, asset isolation and chunk quota tests.
- Worker restart, callback outage and stale-task recovery tests.

## Explicitly blocked in this workspace

- Production or real-customer data tests.
- Destructive cleanup/restore tests.
- Full E2E because Redis and durable object storage are not configured.
- Load testing because no approved staging target was provided.
