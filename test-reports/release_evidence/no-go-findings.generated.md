# NO-GO findings

1. **P0 — credential hygiene:** a local environment file contains a database URI
   with credentials. Rotate/revoke it and keep environment files out of Git.
2. **P1 — staging dependencies:** Redis, durable R2 and a reachable inference
   worker are not available in this workspace, so the main business workflow
   has no end-to-end evidence.
3. **P1 — identity model:** the current bearer token is a pilot service token;
   per-user ownership, RBAC and tenant isolation are still required for SaaS.
4. **P1 — live scalability:** live sessions remain process-local; use a shared
   live worker/session broker before horizontal API scaling.
5. **P1 — index migration:** the currently reachable MongoDB has legacy
   non-unique indexes. Run the dry-run and reviewed `--apply` migration before
   setting `APP_ENV=production`; strict startup will reject unresolved conflicts.
