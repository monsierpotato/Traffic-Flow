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

`powershell
docker compose logs --tail=200 api | Select-String -Pattern 'live/sessions|Live source opened|Live inference ready|Live session tick|Live session failed'
curl http://localhost:8000/live/sessions
nvidia-smi
` 

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
