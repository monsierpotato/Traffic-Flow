# TrafficFlow data flow

```text
UploadFile
  → bounded temporary file
  → ffprobe/normalization in a worker thread
  → R2/local adapter
  → tasks + preview metadata in MongoDB

LaneConfigRequest
  → strict geometry validation
  → lane_configs upsert
  → task status configured

Task process request
  → database compare-and-set claim
  → Celery queue
  → worker callback events
  → monotonic task state update
  → statistics and private result assets
```

The full upload-to-result workflow still requires a safe staging environment
with reachable MongoDB, Redis, object storage, a valid synthetic video and an
available inference service.
