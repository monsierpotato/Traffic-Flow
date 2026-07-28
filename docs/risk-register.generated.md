# TrafficFlow risk register

| ID | Severity | Risk | Mitigation/status |
|---|---|---|---|
| SEC-001 | P0 | Local secret files may contain database credentials | `env` is ignored; rotate any exposed credential before release |
| SEC-002 | P0 | Unauthorized compatibility or asset access | Exact path auth boundary and security tests added |
| SEC-003 | P0 | Live/remote URL SSRF | Scheme, DNS and private-network validation added |
| DATA-001 | P1 | Mongo fallback can split production data | Production startup rejects local fallback |
| DATA-002 | P1 | Callback delivery/state races | Callback token, monotonic progress and CAS updates added |
| OPS-001 | P1 | Redis/worker unavailable | Readiness, queue alignment, Docker healthchecks and release gate added |
| OPS-002 | P1 | Local storage is not durable | Production template requires R2 presigned mode |
| PERF-001 | P1 | CPU/IO-heavy upload path blocks event loop | OpenCV, ffmpeg and storage operations moved to worker threads |
| LIVE-001 | P1 | Process-local live sessions do not scale horizontally | Per-client/global limits added; dedicated live service remains follow-up |
| TEST-001 | P1 | No safe staging E2E evidence | CI gates and evidence templates added; staging execution remains blocked |
