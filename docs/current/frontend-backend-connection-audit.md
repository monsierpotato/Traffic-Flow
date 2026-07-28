# Frontend ↔ Backend Connection Audit

Audit date: 2026-07-28

Scope: `frontend/src/App.jsx`, `frontend/src/api/client.js`, the Vite proxy, FastAPI routes/schemas/services, and worker entrypoints. The frontend intentionally uses the root compatibility endpoints (`/videos`, `/tasks`, and `/live`); this is not a confusion with the versioned `/api/v1/*` endpoints.

## Verified Call Graph

### Upload and Batch Processing

```text
UploadStep.acceptFile
  -> App.handleUpload
    -> uploadVideo
      -> POST /videos (FormData[file])
        -> compat_upload
          -> validate_video_file
          -> save_upload_to_temp
          -> create_uploaded_video_task_from_path
          -> { task_id: video_id, preview_url, ... }
    -> fetchPreview
      -> GET /videos/{task_id}/preview
    -> RoiMaskingStep -> LaneEditorStep
      -> buildLaneConfig (source-frame coordinates)
      -> submitTask
        -> POST /tasks ({ task_id, lane_config })
          -> compat_submit
            -> persist lane configuration
            -> process_task
              -> Celery trafficflow.process_video
                -> worker detect -> track -> count -> render -> storage
                -> PUT /api/v1/tasks/progress/{task_id}
    -> pollTask -> GET /tasks/{task_id}
    -> fetchResult -> GET /tasks/{task_id}/result
```

The upload response intentionally aliases `video_id` as `task_id` in the compatibility route. Subsequent compatibility routes resolve either identifier, so preview, submit, polling, and result retrieval use the same ID correctly.

### Live Processing

```text
handleLiveResolve
  -> POST /live/resolve
  -> GET /live/sources/{source_id}/preview (using returned preview_url)
  -> buildLaneConfig
  -> validateLiveConfig -> POST /live/validate-config
  -> createLiveSession -> POST /live/sessions
  -> fetchLiveSession -> GET /live/sessions/{session_id}
  -> MJPEG GET /live/sessions/{session_id}/stream
  -> stopLive -> DELETE /live/sessions/{session_id}
  -> removeLive -> DELETE /live/sessions/{session_id}/remove
```

### Shared Frontend Function Checks

| Function | Consumers | Result |
|---|---|---|
| `apiRequest` | Upload, live, and task calls | Connected; parses JSON/text and preserves status/code/details |
| `apiBlob` | Preview retrieval | Connected; returns an image blob and handles JSON error payloads |
| `normalizeSource` | Upload response | Connected; maps compatibility `task_id`/`video_id` |
| `normalizeTaskStatus` | Submit and polling | Connected; preserves backend `stage_detail` and normalized `detail` |
| `normalizeAnalyticsResult` | Result dashboard | Connected; maps compatibility `counts`/`outputs`/`total_count` |
| `normalizeLiveSession` | Live creation and polling | Connected; maps `session_id` and runtime counters |
| `buildLaneConfig` | Batch and live submission | Connected; output matches `LaneConfigRequest` and live validation |
| Canvas helpers | ROI/lane editor handlers | Connected through pointer effects and immutable state updates |

## Findings Fixed in the Audit

1. The frontend previously accepted only MP4/AVI while the backend accepts MP4/AVI/MOV/MKV/WEBM. The file chooser, client validation, and operator message now match the backend.
2. Full-frame ROI points can sit exactly on the right/bottom boundary. Live validation now accepts boundary points while still rejecting points outside the frame.
3. FastAPI can return `detail` as an object or validation-error array. The frontend error adapter now extracts `message`, `error`, nested `detail`, or validation messages instead of producing `[object Object]`.
4. API and asset requests now use `VITE_API_BASE_URL` in production while retaining the Vite proxy for local development. This allows the frontend to run on Vercel while the backend runs on a separate public service.

## Verification

- FastAPI OpenAPI exposes 35 paths, including every frontend-called method/path.
- Frontend production build passes.
- Live full-frame geometry validation smoke passes.
- Frontend API error parsing smoke passes for string, object, and array detail.
- Production API URL resolution is covered by the frontend build path and `vercel.json` configuration.

## Intentional Boundaries

- The frontend does not call `/api/v1/*` directly; the root compatibility routes are the active UI contract.
- Worker progress callbacks are internal and are not called from browser code.
- The output MJPEG URL is intentionally a stream URL, not an image blob URL.
- Vercel hosts only the static React application. FastAPI, Celery, Redis, model inference, and persistent storage remain outside Vercel.
