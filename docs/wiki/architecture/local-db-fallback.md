# Local DB Fallback

## Problem

Local Windows runs can fail to connect to MongoDB Atlas with TLS handshake errors such as `TLSV1_ALERT_INTERNAL_ERROR`. Motor/PyMongo creates clients lazily, so API startup can appear successful even though the first real DB operation fails during upload.

## Solution

`shared.database.connect_to_mongo()` now performs a real `admin.command("ping")` at startup. If Atlas is unavailable and `MONGODB_LOCAL_FALLBACK=true`, the API switches to a local JSON-backed database at `storage/local_db.json`.

## Scope

The fallback implements the async collection operations used by the API workflow:

- `insert_one`, `insert_many`
- `find_one`, `find().sort().limit().to_list()`
- `update_one` with `$set` and `upsert`
- `delete_many`
- `count_documents`

This is intended for development, smoke tests, and local E2E resilience. Production should keep Atlas healthy and may set `MONGODB_LOCAL_FALLBACK=false`.

## Validation

Local E2E was run against a fresh API on port 8010 and a dedicated Celery queue. The workflow completed upload → preview → submit → progress callbacks → processing → result while Atlas TLS was failing.
