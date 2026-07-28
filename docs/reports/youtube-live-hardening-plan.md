# YouTube/Live Flow Hardening Plan

## Scope

This plan preserves the current operator flow:

```text
source URL
  -> POST /live/resolve
  -> preview snapshot
  -> ROI/lane annotation
  -> POST /live/validate-config
  -> POST /live/sessions
  -> status polling + MJPEG output
```

The system consumes YouTube media URLs for live inference. It does not use the
YouTube Data API for channel/video metadata.

## Implemented safeguards

| Area | Change | Expected behavior |
| --- | --- | --- |
| Provider resolution | Isolated `youtube_resolver` service | YouTube detection is hostname-exact and errors are testable |
| Signed URL privacy | Do not return resolved YouTube media URLs to the browser | Frontend keeps the source ID and original page URL |
| URL expiry | Keep origin URL and expiry metadata with the session | Re-resolve the origin URL before startup/reconnect |
| Cookies | Copy cookies to a `0600` temporary file and delete them after `yt-dlp` exits | Cookies are not stored below `/static` |
| Preview | Capture with FFmpeg subprocess timeout | A stalled source cannot hold an HTTP request forever |
| Source registry | Add lock, TTL and preview-file deletion | In-memory source records do not grow without bound |
| Direct sources | Validate scheme and block private hosts in production | Reduces malformed-source and SSRF exposure |
| Runtime | Limit active live sessions and clean terminal sessions | Prevents unbounded FFmpeg/thread growth |
| Benchmark flow | Send `source_id` after resolve | Benchmark uses the same resolved source as the UI |

## Verification gates

1. `python3 -m py_compile` for changed Python modules.
2. `pytest` for resolver, source privacy, reconnect and lifecycle tests.
3. Frontend production build.
4. Local HLS integration test with a controlled stream interruption.
5. YouTube smoke test with a public live source.
6. Multi-hour soak test and a separate ground-truth accuracy test before making
   live count accuracy claims.

## Remaining production work

- Move source/session state to a shared store if the API runs with multiple
  workers or replicas.
- Add authentication/ownership checks to source and session endpoints.
- Add a provider-specific re-resolution integration test using a controlled
  `yt-dlp` executable or fixture.
- Add live counting ground truth and report event precision/recall, missed
  counts, duplicate counts and WAPE separately from runtime stability.
