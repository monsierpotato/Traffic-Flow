# GPU Docker + Live Streaming Optimization

## Goal

Keep the website responsive during batch video processing and prepare the same runtime for direct camera/API streaming.

## Optimized Batch Pipeline

1. Frontend/API upload stores video through a temp file path instead of loading the whole file into RAM.
2. API normalizes video by path and uploads the working copy through R2 streaming upload.
3. API enqueues the task to `CELERY_QUEUE_NAME`; Docker uses `trafficflow_gpu_queue` to avoid stale default-queue backlog.
4. Worker downloads the working video directly to a temp file path.
5. Worker performs ROI crop, local GPU YOLO/ByteTrack, Kalman tracking, counting, rendering, and path-based result upload.
6. Worker reports stage-specific progress: `downloading`, `opening_video`, `inferencing`, `rendering`, `uploading_result`, `completed`.

## GPU Runtime Rules

- Batch inference runs in the Celery `worker`; live inference currently runs in the FastAPI `api` process through LiveSessionManager, so both containers need NVIDIA runtime access for local GPU inference.

- One GPU should have one inference worker process: `--concurrency=1`.
- Docker worker should run on the dedicated GPU queue with `-Q trafficflow_gpu_queue`.
- API and worker must share `CELERY_QUEUE_NAME` so submitted tasks land on the queue the GPU worker consumes.
- Disable stabilization by default in Docker batch/live processing unless a camera source demonstrably needs it, because it adds CPU work and may introduce jitter.

## Live Camera Preparation

The live session loop is intentionally non-blocking. It reads frames continuously, submits inference only when no inference future is pending, and increments `frames_dropped` when it must skip a candidate inference frame. This keeps output near real time instead of building an ever-growing latency queue.

## Monitoring Signals

Use these commands while a live session is running:

~~~powershell
docker compose logs --tail=200 api | Select-String -Pattern 'live/sessions|Live source opened|Live inference ready|Live session tick|Live session failed'
curl http://localhost:8000/live/sessions
nvidia-smi
~~~

- `stage` / `stage_detail`: user-facing batch progress phase.
- `frames_processed`: frames actually inferred.
- `frames_read`: source frames consumed.
- `frames_dropped`: live frames skipped to preserve realtime behavior.
- Benchmark `inference` latency: measured from frame submit to future completion.

## Next Options

- Add direct frontend-to-R2 multipart upload to bypass API file ingress completely.
- Add WebSocket/SSE progress streaming instead of polling.
- Add batched inference endpoint for 4-8 frames per request if remote serving becomes the bottleneck.
- Add output streaming endpoint that emits annotated frames/events while live inference runs.



## OpenCV Version Guardrail

Live inference must run on OpenCV 4.10.x. OpenCV 5.0.0 can crash the YOLO/Kalman live path with `matmul.dispatch.cpp:363` / `cv::gemm`. Docker therefore removes any `opencv-python`/`opencv-contrib-python` wheel pulled by transitive dependencies and reinstalls only `opencv-python-headless==4.10.0.84` at the end of dependency installation.

Latest live smoke test:

- Source: `https://youtu.be/sJvEFrG0wq0` resolved to YouTube HLS.
- Config: 1920x1080, processing ROI, ROI polygon, 2 lanes, counting lines, direction vectors.
- Duration: 30 seconds.
- Result: `running`, no `last_error`, `frames_read=1184`, `frames_processed=233`, `frames_dropped=358`, `lane_volume_total=2`.
- GPU: API container sees RTX 5070 Ti through CUDA; `nvidia-smi` showed active VRAM usage during live inference.

## Live Visual Output

The live dashboard now has two visual endpoints:

- `GET /live/sessions/{session_id}/frame`: latest annotated JPEG snapshot.
- `GET /live/sessions/{session_id}/stream`: MJPEG stream for browser display via `<img>`.

The frame is rendered from the cropped/processed live frame and includes lane polygons, counting lines, tracked bounding boxes, track labels, and object centers. Metrics polling still drives FPS/count panels, while the MJPEG endpoint provides visual confirmation that live inference is running.

## Model Experiment: Vietnamese Vehicle Detection

A public YOLOv8 fine-tuned model from `minhtrietcancode/vietnamese-vehicle-detection` was integrated with a custom class map:

- `0 -> motorcycle`
- `1 -> car`
- `2 -> bus`
- `3 -> truck`

The model file is stored at `models/vietnamese_vehicle_detection/my_finetuned_yolov8.pt`. Docker sets `AI_CLASS_IDS=0,1,2,3`, `AI_CLASS_NAME_MAP=0:motorcycle,1:car,2:bus,3:truck`, and `AI_IMGSZ=960` for the experiment.

Initial live smoke test on `https://youtu.be/1EamsYw_Xyo` ran without runtime errors but did not produce reliable detections in the sampled interval. Direct prediction showed low-confidence output, so this model should be treated as an experiment rather than a production improvement until more calibration/fine-tuning is done.

## Current Model Choice

Runtime has been switched back to a COCO-compatible model, but stronger than the original nano/small models during the current experiment:

- `AI_MODEL_PATH=models/yolo11m.pt`
- `AI_CLASS_IDS=2,3,5,7`
- `AI_CLASS_NAME_MAP=`
- `AI_IMGSZ=960`

This keeps class semantics aligned with existing TrafficFlow labels while using a stronger detector on local GPU hardware. The Vietnamese custom model remains downloaded for future experiments but is not the active runtime model.

### YOLOv8m Result

`YOLOv8m` at `AI_IMGSZ=960` is currently active for visual evaluation. In a 30-second smoke test on `https://youtu.be/1EamsYw_Xyo`, it produced clearer vehicle boxes than `YOLOv8s` but reduced live throughput to about 4-5 processed FPS. The test also exposed an oversized lost-track overlay, so live tracking cleanup is a likely next improvement.

### YOLO11m Result

`YOLO11m` at `AI_IMGSZ=960` is currently active. In a 30-second smoke test on `https://youtu.be/1EamsYw_Xyo`, it reached about 3-4 processed FPS and counted 2 motorcycles in lane 1 during the sampled interval. It appears more sensitive than `YOLOv8m` on this stream, but the FPS tradeoff is noticeable.

## Counting Geometry Rules

Traffic counting now uses these production-oriented rules:

1. Detection and tracking run in full-frame coordinates.
2. Each track is represented by a smoothed `bottom_center` anchor, not bbox center or bbox overlap.
3. ROI/lane polygons are post-detection analytics filters.
4. A lane is locked only after the anchor stays in the lane for several frames.
5. A count event requires the anchor trajectory segment to cross the counting line.
6. Direction is validated by dot product between recent anchor motion and the configured direction vector.
7. Lost/predicted tracks are not counted.

This keeps detection stable while making ROI/lane/line/vector responsible only for counting semantics.

## Live Debug Overlay Validation — 2026-07-14

Runtime has been rebuilt with the live debug overlay active:

- `AI_MODEL_PATH=models/yolo11m.pt`
- `ROI_MODE=full_frame`
- `AI_IMGSZ=960`

The live session snapshot now includes these operator-facing fields:

- `model_name`: active detector path.
- `roi_mode`: whether detection is full-frame or ROI-cropped.
- `ai_imgsz`: model inference image size.
- `latest_debug`: counting-state internals for visual/debug rendering.

The annotated live frame now includes:

- bottom-center anchor dots for each track;
- short anchor trails to show movement direction;
- lane candidate/locked labels per track;
- red count-event markers for recent accepted crossings;
- existing boxes, track IDs, lane polygons, and counting lines.

Validation performed after rebuild:

- Backend tests: `pytest tests -q` -> 143 passed.
- Frontend build: `npm run build` -> passed.
- Batch E2E: upload -> preview -> submit -> worker processing -> result completed.
- Live E2E: YouTube URL -> HLS resolve -> live session -> status polling -> latest annotated JPEG fetch -> session removal.

Live smoke result on `https://youtu.be/1EamsYw_Xyo` for 30 seconds:

- Source: YouTube HLS, 1920x1080, 30 FPS.
- Status: `running`, no `last_error`.
- `frames_read=914`, `frames_processed=76`, `frames_dropped=380`.
- Final sampled live FPS: `2.44`.
- Count in sampled interval: `lane_volume_total=0`.
- Frame output saved during validation: `scratch/live_vietnam_model_frame.jpg`.

Important operating note: in live mode, `frames_dropped` is not automatically a failure. It means the pipeline is intentionally discarding stale source frames while GPU inference is busy, so the visual output stays close to realtime instead of building a delayed backlog.

## Live HLS Stable Baseline -- 2026-07-15

The YouTube/HLS live path is now stable at the configured 15 FPS target.

### Problem -> Solution Timeline

1. Problem: live frames from YouTube showed horizontal tearing and repeated bands.
   Solution: FFmpeg raw `bgr24` ingest now reads exactly `width * height * 3` bytes per frame, forces even crop dimensions, uses deterministic crop output, and hands downstream code owned frame copies. Invalid raw reads restart the FFmpeg reader and reset live state instead of feeding corrupted frames into YOLO/tracking.

2. Problem: tracker IDs churned and old/lost IDs stayed visible.
   Solution: live sessions now own tracker/counting/render state per session, reset on reconnect/input gaps, use timestamp-aware Kalman prediction, time-based lost-track expiry, minimum hits before confirmation, multi-criteria association, and production rendering hides tentative/lost/out-of-zone tracks.

3. Problem: debug anchor history polluted production output.
   Solution: production rendering now passes debug overlays only when `RENDER_DEBUG=true`, prunes inactive anchor/lane history, and keeps short track trails instead of unbounded historical anchors.

4. Problem: lane points could be interpreted in the wrong coordinate space after ROI cropping.
   Solution: live config supports explicit `geometry_space` with `source_frame` and `crop_local`; session validation and logs show normalized geometry before counting starts.

5. Problem: after frame integrity was fixed, observed live FPS was only about 2-5 FPS despite YOLO11m inference taking about 50 ms or less.
   Diagnosis: HLS delivered frames in segment bursts, then stalled. A latest-only queue prevented latency buildup but also let FFmpeg overwrite many burst frames while inference later waited for the next segment, leaving the GPU idle.
   Solution: FFmpeg realtime pacing (`-re`) and a Python wall-clock pacer smooth HLS frame delivery. The live loop no longer polls a future from the stream reader loop; it takes the latest paced frame, drops stale frames older than `LIVE_MAX_FRAME_AGE_SECONDS`, runs inference synchronously, publishes, then immediately takes the next latest frame.

### Stable Runtime Baseline

Current stable live config:

```env
LIVE_FFMPEG_OUTPUT_FPS=15
LIVE_FFMPEG_REALTIME_PACING=true
LIVE_FRAME_QUEUE_SIZE=1
LIVE_MAX_FRAME_AGE_SECONDS=0.25

LIVE_TRACK_MIN_HITS=3
LIVE_TRACK_MAX_LOST_SECONDS=0.7
LIVE_TRACK_RESET_GAP_SECONDS=1.0

AI_MODEL_PATH=models/yolo11m.pt
AI_IMGSZ=640
RENDER_DEBUG=false
```

Observed validation after the pacing/scheduler fix:

- FPS stays around `14.97-15.05`, matching `LIVE_FFMPEG_OUTPUT_FPS=15`.
- `frame_interarrival_ms` is about `66.7 ms`, matching 15 FPS pacing.
- `frame_age_ms` is about `0.7-1.3 ms`, so there is effectively no backlog.
- `frames_dropped=0`.
- `infer_wall_ms` is usually `9-18 ms`.
- `lost_tracks=0`.
- `last_error=null`.
- `reader_wait_ms` / `loop_idle_ms` around `45-55 ms` is expected because the loop is waiting for the next paced frame, not because YOLO is saturated.

Conclusion: YOLO11m is not the current bottleneck at 15 FPS. The previous low FPS was caused by HLS burst/stall delivery plus scheduling, not detector speed.

### Metrics Added for Future Debugging

Live session `perf` now exposes:

- `reader_wait_ms`
- `frame_interarrival_ms`
- `frame_age_ms`
- `infer_wall_ms`
- `future_done_wait_ms`
- `loop_idle_ms`
- `publish_ms`

Interpretation:

- If `infer_wall_ms < 70 ms` and `loop_idle_ms` is high, the pipeline is waiting for paced frames.
- If `infer_wall_ms` grows to `200-300 ms`, investigate CUDA synchronization, model contention, or inference-client scheduling.
- If `frame_age_ms` p95 exceeds `250 ms`, the pipeline is accumulating latency and should drop stale frames.

### Next Focus: Counting Accuracy

The live pipeline should now shift from FPS work to counting accuracy. Use a 5-10 minute clip and manually count:

- `lane_1`: car, motorcycle, bus, truck
- `lane_2`: car, motorcycle, bus, truck

Compare with:

```text
absolute_error = |predicted - ground_truth|
error_percent = absolute_error / max(ground_truth, 1) * 100%
```

Initial target:

- total counting error below `10-15%`;
- no duplicate count for the same vehicle within one lane;
- no systematic missed counts during dense traffic.

### Open Production Follow-Ups

- Decide multi-lane semantics. Current observed sample had `lane_volume_total=92`, `global_unique_count=84`, `multi_lane_track_count=8`. If lanes represent exclusive road directions, add a `COUNT_ALLOW_MULTI_LANE=false` style guard so one track cannot be counted in multiple lanes.
- Add local model warmup before session status becomes `running`; first inference can take about `3382 ms` and can trigger one input-gap reset.
- Update frontend live config payload to send `geometry_space: "crop_local"` explicitly instead of relying on backend inference.
- Resolve MongoDB Atlas TLS handshake before multi-machine production or any deployment requiring durable persistence beyond local JSON fallback.
