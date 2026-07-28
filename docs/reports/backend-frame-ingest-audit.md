# Backend frame-ingest audit

## Scope

This audit covers the API/backend path before and around frame publication:

- file upload and chunked upload handling;
- metadata probing, optional video normalization, preview extraction and storage;
- live-source probing, FFmpeg/OpenCV frame ingestion, latest-frame handoff,
  crop/resize/mask preprocessing, rendering and JPEG publication;
- API polling and MJPEG frame delivery.

AI model execution and the Celery/AI worker inference path are intentionally
excluded. The live-session timing field `infer_wall_ms` is retained only as a
boundary metric; it is not used to assess the backend changes here.

## Current flow

```text
Upload
  multipart parser -> file validation -> temp-file copy
  -> ffprobe/OpenCV metadata -> optional FFmpeg normalize
  -> object storage upload -> first-frame decode/JPEG -> preview upload
  -> local preview + task document

Live
  source resolve/probe -> FFmpeg raw BGR (or OpenCV fallback)
  -> latest-frame slot (old frames may be dropped)
  -> crop/resize/mask -> AI boundary
  -> tracking/render/JPEG -> latest frame -> /frame or MJPEG stream
```

## Findings before the fix

| Area | Finding | Effect |
| --- | --- | --- |
| Upload validation | The validator read the entire spooled file, then the route copied the file again. | One unnecessary full-file read for every upload. |
| Upload event loop | OpenCV, ffprobe, FFmpeg, local file copies and synchronous R2 calls ran inside async request handlers. | A large upload could block unrelated API requests on the same event loop. |
| Metadata | One OpenCV metadata open and one ffprobe process were used for the same file. | Extra startup work before normalization/upload. |
| Live startup | The session probed the source, then the FFmpeg reader probed it again. | Duplicate process/startup latency. |
| Live handoff | Raw pipe data was copied bytearray → bytes → ndarray, then the latest ndarray was copied again for the consumer. | Extra memory bandwidth and lock hold time per frame. |
| Live render | The crop was copied before every overlay render even though the frame had been transferred to the consumer. | Extra full-crop copy per processed frame. |
| Drop metrics | Sequence gaps created by the latest-frame slot were not counted. | `frames_dropped` understated ingest pressure. |

Local measurements on the repository environment before the fix were:

- 1920×1080/30fps sample: metadata about 52 ms, first-frame decode about
  44 ms, output JPEG about 4.1 ms per frame;
- 3840×2160 sample: metadata about 81 ms, normalization/transcode about
  1.23 s, first-frame decode about 0.38 s;
- live 1920×1080 handoff copy about 0.24 ms per frame and render copy about
  0.23 ms per frame.

The 4K transcode is the dominant single-upload latency by design: it creates
the bounded 1080p/30fps working video required by the existing downstream
contract. It was not removed because doing so would move the cost to every
downstream frame decode and increase memory/CPU pressure.

## Changes implemented

1. Validation now checks the seekable upload size with `seek/tell`, validates
   only the first 1 MiB for MIME/magic bytes, and restores the cursor.
2. The shared upload temp-copy helper uses one buffered copy in a worker
   thread. The compatibility and API upload routes now share it.
3. Blocking normalize, OpenCV decode, local file writes and R2 operations are
   moved off the async event-loop thread. The API contract remains synchronous
   from the caller's perspective: the response still contains the stored
   video and preview metadata.
4. Metadata probing requests dimensions, frame rate, duration and color fields
   in one ffprobe invocation, with the old OpenCV fallback for incomplete or
   unavailable probe results.
5. Live startup passes the already-probed source dimensions/FPS into the
   FFmpeg reader. Reconnects still re-probe so geometry changes are detected.
6. The FFmpeg reader reuses its raw pipe buffer, removes the redundant bytes
   conversion, and hands off the immutable latest ndarray without copying.
   Rendering uses that transferred frame directly.
7. The OpenCV fallback sets supported open/read timeout properties to avoid an
   indefinite wait on a dead source.
8. Live sequence gaps are counted as dropped frames, and upload task documents
   now retain `ingest_ms`, `storage_ms` and `preview_ms` for production
   diagnosis.

## Verification

- Maintained non-integration suite: `135 passed`.
- API integration suite: `32 passed`.
- Focused ingest/live tests: `11 passed`.
- Python compilation and `git diff --check`: passed.
- Real sample probes still report correct 1920×1080 and 3840×2160 metadata;
  4K normalization still produces a 1920×1080 working video.

## Remaining bottlenecks and next decision

- 4K normalization and remote object-storage upload remain the expected
  end-to-end upload bottlenecks. The next architectural step would be an
  upload-accepted/processing state with background normalization, but that
  changes the current response contract and was deliberately not introduced.
- Live throughput is still bounded by the AI boundary and the single live
  processing loop. The backend now drops stale frames intentionally to keep
  latency bounded; inference throughput is outside this audit.
- A real YouTube/RTSP soak test is still required to quantify network jitter,
  reconnect frequency and source-specific FFmpeg behavior.
