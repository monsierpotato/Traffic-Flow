# TrafficFlow Wiki Log

## [2026-07-15] fix | Stable YouTube/HLS Live Inference at 15 FPS

- Problem: after fixing frame tearing and tracker churn, live YouTube/HLS sessions still ran at only about 2-5 FPS even though YOLO11m inference was fast enough.
- Diagnosis: HLS frame delivery arrived in bursts followed by stalls. The latest-only buffer protected latency but starved inference between bursts, so GPU idle time was hidden outside model timing.
- Solution: added FFmpeg realtime pacing, a Python wall-clock pacer, stale-frame dropping, a dedicated synchronous live inference loop over the latest frame, and wall-clock timing metrics.
- Baseline: `LIVE_FFMPEG_OUTPUT_FPS=15`, `LIVE_FFMPEG_REALTIME_PACING=true`, `LIVE_FRAME_QUEUE_SIZE=1`, `LIVE_MAX_FRAME_AGE_SECONDS=0.25`, `LIVE_TRACK_MIN_HITS=3`, `LIVE_TRACK_MAX_LOST_SECONDS=0.7`, `LIVE_TRACK_RESET_GAP_SECONDS=1.0`, `AI_MODEL_PATH=models/yolo11m.pt`, `AI_IMGSZ=640`, `RENDER_DEBUG=false`.
- Validation: observed `14.97-15.05` FPS, `frame_interarrival_ms ~= 66.7`, `frame_age_ms ~= 0.7-1.3`, `frames_dropped=0`, `infer_wall_ms ~= 9-18`, `lost_tracks=0`, and `last_error=null`.
- Next focus: counting accuracy, multi-lane counting semantics, local model warmup, explicit frontend `geometry_space`, and MongoDB Atlas TLS.

## [2026-05-31] ingest | Initialize TrafficFlow Wiki

- Created the initial TrafficFlow wiki structure.
- Added index and seed pages for architecture, AI workflow, contracts, sprints, and decisions.
- Source evidence: current repo structure, existing runtime refactor, ROI annotation contract, and project planning discussion.

## [2026-05-31] ingest | Add Raw Source Layer

- Added `docs/raw` as the immutable source layer for future wiki ingest.
- Updated the TrafficFlow wiki agent schema to use `docs/raw` for reusable source material and `docs/wiki` for synthesized pages.

## [2026-05-31] ingest | Default Wiki-First Query Flow

- Updated the TrafficFlow wiki agent to search `docs/wiki/index.md` and recent `docs/wiki/log.md` entries first for project questions.
- Purpose: recover prior conversation context, completed work, architecture decisions, project progress, and related pages while keeping future answers concise.

## [2026-05-31] ingest | Config Generator ROI Support

- Added rectangular annotation ROI support to `trafficflow.cli.config_generator`.
- Supported modes: `--annotation-roi x,y,width,height` and `--select-roi`.
- Drawing occurs on the cropped preview; saved lane geometry remains in source-frame coordinates and config includes `annotation_roi` metadata.

## [2026-05-31] ingest | Google Doc Work Plan

- Ingested Google Doc `Phan chia cong viec deploy AI Traffic`.
- Added raw snapshot at `docs/raw/notes/2026-05-31-google-doc-work-plan.md`.
- Added source summary page `docs/wiki/sources/deploy-ai-traffic-work-plan.md`.
- Updated `docs/wiki/sprints/project-backlog.md` with ownership, sprints 0-5, high/medium/post-MVP backlog, and additional backend/worker tasks.

## [2026-05-31] lint | Wiki Health Check

- Checked wiki index, log, cross-links, and core pages for stale claims and missing references.
- No broken Obsidian links found among current wiki pages.
- Updated `docs/wiki/sprints/project-backlog.md` to reflect implemented ROI contract/helper/config-generator support and remaining Sprint 0 gaps.
- Updated `docs/wiki/ai-workflow/runtime-engine.md` to note missing `progress_callback` and unfinished API result contract.
- Updated `docs/wiki/decisions/decision-log.md` with the accepted OpenCV ROI config-generator decision and deferred ROI edit-mode question.

## [2026-05-31] ingest | Runtime Progress Callback

- Added `progress_callback` support to `trafficflow.runtime.engine.VideoCountingRequest`.
- Progress payloads include `status`, `frame_index`, `frames_processed`, `total_frames`, and `progress`.
- Added `docs/contracts/progress_callback.md` and `docs/wiki/contracts/progress-callback-contract.md`.
- Updated Sprint 0 backlog status for `progress_callback` to Done.

## [2026-06-02] ingest | Complete Sprint 0 Runtime Contracts

- Added API-ready result contract at `docs/contracts/video_counting_result.md`.
- Added sample result JSON at `docs/contracts/result_sample.json`.
- Extended `VideoCountingResult.to_dict()` with `total_count` and output artifact paths.
- Added synthetic runtime smoke test coverage in `tests/test_runtime_engine.py`.
- Updated lane config sample to include rectangular `annotation_roi.type`.
- Ran real YOLO smoke on 5 frames using the Đà Nẵng Cầu Rồng video/config and `models/yolov8n.pt`; result completed with 5 processed frames and 1 counted car.
- Updated Sprint 0 backlog to Done.

## [2026-07-04] test | E2E Full Flow Verification

- Verified complete end-to-end pipeline: Frontend upload → Backend API → MongoDB → Redis/Celery → Worker → Modal AI → Callback → Result.
- All connections PASS: MongoDB Atlas, Redis Cloud, Cloudflare R2, Celery broker.
- New bug found: `.env` `AI_SERVING_URL` contained spaces and `--` in the URL (FIXED).
- New bug found: `HTTP_422_UNPROCESSABLE_ENTITY` deprecated warning in Starlette — should use `HTTP_422_UNPROCESSABLE_CONTENT`.
- Deprecation warning: `starlette.testclient` requires `httpx2` instead of `httpx`.
- Frontend built with Vite + React is fully functional — upload, ROI masking, lane geometry editor, analytics dashboard.
- See [[Backend Refactor Plan]] for the full refactor proposal.

## [2026-07-04] audit | Backend Package Architecture Audit

- **Critical issue**: Package name collision between root `trafficflow/` (backend) and `Traffic-Flow_Frontend/trafficflow/` (AI core). Both use `trafficflow` namespace.
- **Critical issue**: Worker bypasses AI core engine — uses HTTP to call Modal GPU API instead of importing `TrafficFlowEngine` from `trafficflow.runtime` directly.
- **Structural issue**: 10 empty stub directories in root `trafficflow/`: `runtime/`, `core_ai/`, `counting/`, `geometry/`, `pipeline/`, `worker/`, `queue/`, `storage/`, `observability/`, `cli/` — all contain only `__pycache__/`.
- **Bug**: `tasks.py` allows re-processing of already completed/failed tasks (status check only blocks "uploaded").
- **Decision**: Backend package needs refactoring into `backend/` to resolve namespace collision and clean up stub directories.

## [2026-07-04] fix | Applied Quick Fixes

- **FIXED**: `.env` `AI_SERVING_URL` spaces in URL (was `https://tienpm205 -- ...` → `https://tienpm205--...`)
- **FIXED**: Deprecated `HTTP_422_UNPROCESSABLE_ENTITY` → `HTTP_422_UNPROCESSABLE_CONTENT` in `upload.py:44`
- **FIXED**: Task status validation in `tasks.py:process_task` — now blocks re-processing of `completed`, `failed`, `archived` tasks and rejects concurrent `pending`/`processing` tasks with 409 Conflict

## [2026-07-04] refactor | Phase 1 — Backend Package Restructure

- **Moved**: root `trafficflow/` (backend) → `backend/` — resolves package name collision with AI core
- **Renamed**: `Traffic-Flow_Frontend/` → `ai-core/` — clear separation: `backend/` = FastAPI app, `ai-core/` = installable AI library
- **Deleted**: 10 empty stub directories (`runtime/`, `core_ai/`, `counting/`, `geometry/`, `pipeline/`, `worker/`, `queue/`, `storage/`, `observability/`, `cli/`)
- **Updated**: All 26 Python imports from `trafficflow.*` → `backend.*`
- **Updated**: `run_server.bat`, `run_worker.bat`, `backend/main.py` module paths
- **Updated**: Frontend mount path to `ai-core/frontend/dist`
- **Tested**: Full E2E flow verified — upload, configure lanes, process, Celery worker, progress callbacks

## [2026-07-10] perf | Phase 5 — Benchmark Runner + Matrix Report

- Created `benchmark/run_benchmark.py` — standalone CLI runner (`--preset`, `--all`, `--max-frames`, `--no-overlay`). Runs direct inference (no Celery/R2), multi-preset matrix, auto-generates `summary.csv`, `summary.json`, `benchmark_report.md`.
- Fixed `half` deprecation in ultralytics: moved from `model.track(half=...)` to `model.model.half()` in `YoloByteTrackDetector.__init__`.
- 8 presets in `benchmark/presets.json`: YOLOv8n/s × FP16/FP32 × imgsz 416/512/640 × frame_skip 1/2/3.
- Benchmark report format: Summary table (FPS, real-time factor, GPU%, VRAM) + Stage breakdown (avg/p95 ms) + Resource usage.
- Usage: `python -m benchmark.run_benchmark --all --max-frames 300`
- 137 tests pass, compile clean.

## [2026-07-10] data | UA-DETRAC Ground Truth Integration

- Integrated [UA-DETRAC](https://detrac-db.rit.albany.edu/) as benchmark ground truth source (60 train sequences, 8.2K annotated vehicles, 4-class: car/bus/van→truck/others-skip).
- Built `benchmark/detrac_parser.py`: XML → Tracklet extraction, counting-line crossing detection via `segments_intersect()`, batch `generate_detrac_ground_truth()` → `counts_summary.csv`.
- Built `benchmark/detrac/convert_detrac.py`: frames→mp4 (cv2), auto lane config, ground truth generation. One-shot for all sequences.
- Converted 3 sequences: MVI_20011 (664f/52t), MVI_20012 (936f/41t), MVI_20035 (800f/65t).
- **Class distribution**: car 92%, truck 5%, bus 3%. DETRAC has **no motorcycle** — that class is untested.
- **Important**: XMLs/images have double-nesting (`DETRAC-Train-Annotations-XML/DETRAC-Train-Annotations-XML/`), parser paths must match.

## [2026-07-10] fix | OpenCV 5.0.0 → 4.10.0 Downgrade

- OpenCV 5.0.0 `cv::gemm` crashes ONNX model inference every other frame (`matmul.dispatch.cpp:363`).
- Downgraded to `opencv-python==4.10.0.84` — all `gemm` errors gone, inference stable.
- Taste preference recorded: Avoid OpenCV 5.0.0 for ONNX inference.

## [2026-07-10] bench | Full DETRAC Benchmark Matrix

- Ran 12-run matrix: 3 videos × 4 presets (`optimized-a/b/c` + `baseline`) on RTX 5070 Ti.
- Added `video_id` field to `BenchmarkResult` for ground truth matching.
- Updated `reporter.py` `write_markdown()` to accept `comparisons` dict — auto-appends ground truth accuracy tables.
- Created `benchmark/run_full_benchmark.py` — batch runs all combinations, single aggregated report.
- **Key results**:

| Preset | Imgsz | Half | Avg FPS | Real-time | MVI_20011 Err |
|--------|-------|------|---------|-----------|--------------|
| optimized-a | 640 | FP16 | 24 | 1.95× | **6.06%** |
| optimized-b | 512 | FP16 | 29 | 2.35× | 15.15% |
| optimized-c | 416 | FP16 | **30** | **2.40×** | 21.21% |
| baseline | 640 | FP32 | 24 | 1.95× | 6.06% |

- **Sweet spot**: `optimized-a-yolov8n-fp16-640` — 6% counting error, 24 FPS, 1.8× real-time, ~3.4GB VRAM.
- **Caveat**: MVI_20035 shows 40% error — counting line at y=270 is arbitrary, doesn't match camera geometry. Needs per-video lane config tuning.
- Inference cost: FP16 640 = ~8ms, FP16 512 = ~0.4ms, FP16 416 = ~0.2ms. Bottleneck is preprocess (~14ms) not inference.
- GPU utilization stays near 0% (nvidia-smi samples every 2s, misses short inference bursts). VRAM ~3.4-3.7GB stable.

## [2026-07-10] plan | Next Steps (2026-07-11)

**Priority 1 — Lane Config Tuning for DETRAC**
- Visualize first frame + counting line overlay per video.
- Tune `counting_line` y-coordinate based on actual camera angle.
- Re-run DETRAC benchmark with correct lines → expect <15% error.
- Script: `benchmark/detrac/visualize_lanes.py`.

**Priority 2 — Model Comparison**
- Add `balanced-yolov8s-fp16-640` to matrix → compare n vs s accuracy-speed.
- Test frame_skip=1 (no skip) vs skip=2 vs skip=3 trade-off.

**Priority 3 — Motorcycle Testing**
- Generate synthetic motorcycle video with ground truth OR find public dataset with bike/motorcycle.
- Test 4-class accuracy end-to-end.

**Priority 4 — Final Portfolio Report**
- Aggregate all results → `benchmark/reports/final_report.md`.
- Include: speed-accuracy trade-off chart, per-stage profiling, optimization decisions explained, recommendations.

**Files touched today**:
- `benchmark/detrac_parser.py` (new), `benchmark/detrac/convert_detrac.py` (new), `benchmark/detrac/` (dataset ~85MB video + XML)
- `benchmark/run_full_benchmark.py` (new)
- `benchmark/run_benchmark.py` (updated: `video_id`, ground truth integration)
- `benchmark/presets.json` (updated: DETRAC video configs)
- `benchmark/ground_truth/counts_summary.csv` (3 videos, 7 rows)
- `src/worker/pipeline/profiler.py` (added `video_id` field)
- `src/worker/pipeline/reporter.py` (ground truth section in markdown)
- `src/worker/pipeline/ground_truth.py` (no changes — using existing `compare_counts`)






## [2026-07-13] optimize | GPU Docker + Smooth Progress + Live Streaming Prep

- Added file-path streaming for upload, R2 upload, worker download, and result upload to reduce RAM spikes on 700MB-1.2GB videos.
- Added `CELERY_QUEUE_NAME` and configured Docker to use `trafficflow_gpu_queue`, preventing new GPU tasks from being stuck behind stale/default Redis backlog.
- Updated task progress contract with `stage` and `stage_detail` so frontend can show `queued`, `downloading`, `opening_video`, `inferencing`, `rendering`, `uploading_result`, and `completed` instead of appearing frozen.
- Hardened local Kalman tracker for OpenCV 5 by passing a 4x1 measurement vector and filtering invalid bboxes, addressing prior `gemm` failures in Docker worker logs.
- Prepared live camera workflow by making live inference non-blocking: if inference is still pending, the live loop drops frames instead of accumulating latency; `frames_dropped` is exposed for monitoring.
- Docker runtime now avoids API reload mode and pins the GPU worker to one process/one queue for stable GPU ownership.

## [2026-07-13] fix | Mongo Atlas TLS Fallback for Local E2E

- Reproduced local MongoDB Atlas failure: `TLSV1_ALERT_INTERNAL_ERROR` during real `ping`/insert, despite API startup previously saying connected because the client was lazy.
- Updated `shared.database` to perform an actual `admin.command("ping")` during startup.
- Added automatic local JSON DB fallback at `storage/local_db.json` when Atlas is unavailable and `MONGODB_LOCAL_FALLBACK=true`.
- Added config keys `MONGODB_LOCAL_FALLBACK` and `LOCAL_DB_PATH` for development/test resilience.
- Re-ran local E2E on port 8010 with a dedicated Celery queue: upload, preview, task submit, progress callbacks, processing, and result all completed using the fallback DB.
- Note: Docker GPU path remains preferred for local GPU inference; the Windows venv worker still reported `No GPU found`, so CPU fallback is expected outside Docker.

## [2026-07-13] feature | Live Source Resolve + Annotate Before Inference

- Added live source resolver endpoints: `/live/resolve`, `/live/sources/{source_id}/preview`, `/live/sources/{source_id}/snapshot`, and `/live/validate-config`.
- YouTube page URLs are resolved with `yt-dlp` into a direct media/HLS URL before OpenCV capture; HLS/RTSP/MJPEG/direct video URLs pass through unchanged.
- The resolver captures a preview frame and returns resolution/FPS/source type so the frontend can reuse the existing ROI/lane/counting-line/direction-vector annotation workflow.
- Live counting now requires a valid lane config. `/live/sessions` rejects sources without ROI polygon, processing ROI, lanes, counting line, and direction vector.
- Frontend upload step now supports "Resolve Source" for YouTube/HLS/RTSP/MJPEG/direct video URLs, then routes the snapshot through ROI and lane editors before Start Live is enabled.

## [2026-07-13] fix | YouTube Resolver Cookies + JS Challenge Runtime

- Added `YTDLP_COOKIES_FILE`, `YTDLP_JS_RUNTIME`, and `YTDLP_REMOTE_COMPONENTS` settings for YouTube source resolution.
- Docker API mounts `C:/Users/ADMIN/Downloads/cookies.txt` read-only at `/run/secrets/youtube_cookies.txt` and passes it to `yt-dlp` with `--cookies`.
- Docker image now installs `nodejs`; resolver uses `--js-runtimes node` plus `--remote-components ejs:github` for YouTube JS challenge solving.
- Verified the previously failing YouTube live URL resolves locally with cookies + node + remote components, returning a `manifest.googlevideo.com` HLS playlist URL.

## [2026-07-13] verify | YouTube Cookies Resolve in Docker

- Rebuilt API image with Node.js and `yt-dlp` cookies support.
- Fixed read-only cookies mount issue by copying `/run/secrets/youtube_cookies.txt` to a writable runtime copy before invoking `yt-dlp`.
- Verified Docker API resolves `https://www.youtube.com/live/sJvEFrG0wq0` into a `manifest.googlevideo.com` HLS URL and captures a 1920x1080 preview at 30 FPS.

## [2026-07-13] fix | Live Session Visibility + API GPU Runtime

- Clarified the live UI state: `ready_to_start` now means source + geometry are valid, while `running` only appears after `/live/sessions` starts a live inference loop.
- Added an explicit frontend hint after geometry validation: click `Start Live` to begin inference.
- Added live runtime logs for source open, inference client creation, periodic frame ticks, and final session summary.
- Added `GET /live/sessions` to inspect active/recent live sessions during debugging.
- Enabled NVIDIA runtime/device reservation for the API container because live inference currently runs inside the API process, while batch inference runs in the Celery worker.
- Validation: `pytest tests -q` passed with 140 tests; `frontend` production build passed.

## [2026-07-13] fix | OpenCV 5 Live Gemm Crash

- Reproduced the live YouTube session failure with `OpenCV(5.0.0) ... matmul.dispatch.cpp:363 ... gemm` after live inference started.
- Root cause: `ultralytics` pulled `opencv-python 5.0.0.93` into the Docker image even though `opencv-python-headless 4.10.0.84` was also requested.
- Fixed Docker build by uninstalling `opencv-python`, `opencv-contrib-python`, and `opencv-python-headless`, then reinstalling only `opencv-python-headless==4.10.0.84` as the final dependency step.
- Pinned local project dependency to `opencv-python==4.10.0.84` to avoid accidental OpenCV 5 upgrades outside Docker.
- Rebuilt API/worker containers and verified both report `cv2=4.10.0` with CUDA available.
- Live E2E smoke test with `https://youtu.be/sJvEFrG0wq0` and the two-lane config ran for 30 seconds: status stayed `running`, `last_error=null`, `frames_read=1184`, `frames_processed=233`, `frames_dropped=358`, `lane_volume_total=2`.
- API logs confirmed `Live inference ready` with `LocalInferenceClient`; `nvidia-smi` showed RTX 5070 Ti activity and ~2403 MiB VRAM in use.
- Validation: `pytest tests -q` passed with 140 tests.

## [2026-07-13] feature | Live Annotated Video Output

- Added live annotated output frames to `LiveSessionState`: every processed live frame now stores the latest JPEG with lane geometry, counting lines, tracked boxes, labels, and track centers.
- Added `GET /live/sessions/{session_id}/frame` for the latest annotated JPEG snapshot.
- Added `GET /live/sessions/{session_id}/stream` as an MJPEG stream (`multipart/x-mixed-replace`) so the frontend can show live visual output, not only metrics.
- Frontend Analytics Dashboard now replaces the empty live video area with the live annotated MJPEG output after `Start Live`; it shows a placeholder only until the first inferred frame is ready.
- Smoke test: started a YouTube HLS live session, waited for `latest_frame_seq=1`, and verified `/live/sessions/{session_id}/stream` returns `200 multipart/x-mixed-replace; boundary=frame`.
- Validation: `pytest tests -q` passed with 140 tests; `npm run build` passed; Docker API/worker rebuilt and restarted.

## [2026-07-13] experiment | Vietnamese Vehicle Detection Model

- Downloaded the fine-tuned model from the public `minhtrietcancode/vietnamese-vehicle-detection` Google Drive folder to `models/vietnamese_vehicle_detection/my_finetuned_yolov8.pt`.
- Added `AI_CLASS_NAME_MAP` so custom model class IDs can map to TrafficFlow canonical classes. For this dataset: `0:motorcycle,1:car,2:bus,3:truck`.
- Configured Docker API/worker to test the model with `AI_MODEL_PATH=models/vietnamese_vehicle_detection/my_finetuned_yolov8.pt`, `AI_CLASS_IDS=0,1,2,3`, and `AI_IMGSZ=960`.
- Ran live smoke test with `https://youtu.be/1EamsYw_Xyo` and the new two-lane config for 30 seconds. Stream resolved to 1920x1080@30, session stayed `running`, `last_error=null`, `frames_processed=215`, `fps≈8`, but `latest_tracks=[]` and `lane_volume_total=0` during the sampled interval.
- Direct prediction on the saved live frame showed the custom model's labels are `{0: motorbike, 1: car, 2: minibus, 3: van_truck_container}` and only produced one low-confidence `van_truck_container` prediction at `conf=0.066`, likely a false positive on road/background.
- Conclusion: the downloaded model integrates technically, but does not yet improve this live CCTV stream without further threshold/calibration/fine-tuning. The upstream repo notes the model was trained on about 1,500 images for exploration, not the full original dataset.
- Validation: `pytest tests -q` passed with 140 tests; `npm run build` passed; Docker API/worker rebuilt with CUDA and OpenCV 4.10.

## [2026-07-13] change | Roll Back Custom Model, Use YOLOv8s COCO

- Rolled back the experimental Vietnamese custom model for runtime use because the initial live sample produced no reliable tracks and direct prediction showed only a low-confidence false positive.
- Switched Docker API/worker to `models/yolov8s.pt`, keeping COCO vehicle classes `AI_CLASS_IDS=2,3,5,7` and clearing `AI_CLASS_NAME_MAP`.
- Kept `AI_IMGSZ=960` to improve small-object recall compared with the previous 640 live setup while using the local RTX 5070 Ti.
- Rebuilt/restarted Docker and verified API settings: `model=models/yolov8s.pt`, `ids=2,3,5,7`, `imgsz=960`, `cuda=True`.
- Live smoke test on `https://youtu.be/1EamsYw_Xyo` with the new config ran for 30 seconds: `last_error=null`, `frames_processed=206`, `fps≈6.7`, GPU ~15%, but the sampled output frame contained no clear vehicle inside the ROI, so `lane_volume_total=0` for that interval.
- Next accuracy step: run a longer live interval or capture a short clip containing vehicles inside the configured ROI, then compare `yolov8n/s/m` at `imgsz=960/1280` against the same frame window.

## [2026-07-13] experiment | YOLOv8m Live Accuracy Test

- Downloaded `models/yolov8m.pt` and switched Docker API/worker from `yolov8s.pt` to `yolov8m.pt` while keeping COCO vehicle IDs `2,3,5,7` and `AI_IMGSZ=960`.
- Rebuilt/restarted Docker and verified API settings: `model=models/yolov8m.pt`, `ids=2,3,5,7`, `imgsz=960`, `cuda=True`.
- Live smoke test on `https://youtu.be/1EamsYw_Xyo` with the current config ran for 30 seconds: `last_error=null`, `frames_processed=136`, `fps≈4.5`, `lane_volume_total=1`.
- Compared to `yolov8s`, `yolov8m` detected clearer vehicle boxes in the sampled frame, including a parked/slow car at high confidence (`car 0.85`), but FPS dropped from roughly 6-8 FPS to roughly 4-5 FPS at `imgsz=960`.
- Observed one oversized/lost track box from Kalman prediction, suggesting the next accuracy fix should filter invalid predicted boxes before overlay/counting or reduce `TRACK_BUFFER` for live.
- Decision: keep `yolov8m.pt` active temporarily for user-side visual evaluation because hardware can handle it, but benchmark longer clips before making it the default.

## [2026-07-14] experiment | YOLO11m Live Accuracy Test

- Downloaded `models/yolo11m.pt` and switched Docker API/worker from `yolov8m.pt` to `yolo11m.pt`, keeping COCO vehicle IDs `2,3,5,7` and `AI_IMGSZ=960`.
- Rebuilt/restarted Docker and verified API settings: `model=models/yolo11m.pt`, `ids=2,3,5,7`, `imgsz=960`, `cuda=True`.
- Live smoke test on `https://youtu.be/1EamsYw_Xyo` with the current config ran for 30 seconds: `last_error=null`, `frames_processed=123`, `fps≈3.6`, `lane_volume_total=2`.
- Compared with `yolov8m`, `yolo11m` detected/counts more in this sampled interval (`motorcycle=2` on lane 1) but processed fewer frames (`123` vs `136`) at the same `imgsz=960`.
- Current active model is `yolo11m.pt` for user-side visual evaluation. If FPS is too low, next fallback is `yolov8m.pt` or `yolo11s.pt`.

## [2026-07-14] verify | Offline Count — Hầm Trần Thị Lý Middle Line

- Ran an independent offline count on `data/raw/danang/Hầm Trần Thị Lý.mp4` using the active `models/yolo11m.pt` detector in Docker GPU mode.
- Video metadata: 3840x2160, 1887 frames, ~30.04 FPS, ~62.8 seconds.
- Counting setup: one horizontal line across the middle of the frame at `y=1080`; COCO vehicle IDs `2,3,5,7`; `imgsz=960`; full-frame tracking with ByteTrack.
- At `conf=0.10`: total count `47` (`motorcycle=32`, `car=15`), direction split `down=30`, `up=17`.
- At `conf=0.25`: total count `46` (`motorcycle=31`, `car=15`), direction split `down=29`, `up=17`.
- The count is stable across confidence thresholds, but overlay inspection shows many detections far near the top of the frame; the middle horizontal line is acceptable for a quick test but not necessarily the best production counting line for this camera perspective.
- Outputs saved under `scratch/offline_count_ham_tran_thi_ly/` and `scratch/offline_count_ham_tran_thi_ly_conf025/`.

## [2026-07-14] output | Rendered Full Overlay Video — Hầm Trần Thị Lý

- Rendered the full 62.8-second offline inference video with detection boxes, track IDs, middle counting line, and running totals.
- Output file: `scratch/offline_count_ham_tran_thi_ly_conf025/ham_tran_thi_ly_yolo11m_count_overlay.mp4`.
- Render result matches the `conf=0.25` count: total `46` vehicles (`motorcycle=31`, `car=15`), direction split `down=29`, `up=17`.
- Render settings: 1280x720 output, `models/yolo11m.pt`, `imgsz=960`, COCO vehicle classes, horizontal line at original `y=1080`.

## [2026-07-14] fix | Stabilize Detection by Separating Detection From ROI Counting

- Investigated R2 video/task `4c9b1de3-5733-43dc-81b1-2154d5f0ced7` / task `5ee02741-338a-4b16-be4e-063b6d3341bd` after observing unstable detection between full-frame inference and ROI-based inference.
- The uploaded 4K source was normalized to 1920x1080 before processing; worker used `Processing ROI: x=3 y=96 w=1906 h=978` with `models/yolo11m.pt` and `imgsz=960`.
- Existing task result with ROI crop/mask returned total `24` (`lane_1: car=11, motorcycle=3, truck=1`; `lane_2: car=5, truck=1, motorcycle=3`).
- Direct comparison on the same 1080p R2 frame showed large detector differences: e.g. frame `900` full-frame detected `12` vehicles while ROI inference detected only `3`; frame `1500` full-frame detected `14` while ROI detected `4`.
- Root cause: ROI crop/polygon mask changes the visual distribution and context seen by YOLO. Even a near-full-frame ROI can remove top/horizon context and alter object scale/letterbox behavior, causing inconsistent detections and tracker IDs.
- Updated batch and live runtime so `ROI_MODE=full_frame` means detection runs on the full frame; ROI/lane geometry is not shifted/cropped and is used only for counting/filtering/overlay.
- Docker now sets `ROI_MODE=full_frame` for both API and worker. This favors stable detector behavior over ROI-crop speedups.
- Validation: `pytest tests -q` passed with 140 tests; `npm run build` passed; Docker rebuilt and API reports `model=models/yolo11m.pt`, `roi_mode=full_frame`, `imgsz=960`.

## [2026-07-14] fix | Bottom-Center Anchor + Lane Lock Counting

- Updated `worker.services.counting_service` to make traffic counting anchor-based instead of bbox-overlap-based.
- Counting now uses smoothed `bottom_center` anchors as the vehicle road-contact point.
- Lost/predicted tracks are skipped for counting to avoid oversized Kalman boxes creating false crossings.
- Lane assignment now uses `bottom_center in lane polygon`, then locks the lane only after `LANE_LOCK_FRAMES=3` consecutive observations.
- Direction validation now uses anchor trajectory over a history window instead of one-frame Kalman velocity, with dot-product threshold `0.35`.
- Added minimum visible track age (`MIN_TRACK_AGE_FRAMES=4`) before a track can count.
- Added focused worker counting tests for bottom-center crossing, lost-track skip, and wrong-direction rejection.
- Validation: `pytest tests -q` passed with 143 tests; `npm run build` passed; Docker API/worker rebuilt with `ROI_MODE=full_frame`, `models/yolo11m.pt`, `AI_IMGSZ=960`.

## [2026-07-14] live | Debug Overlay + End-to-End Validation

- Rebuilt and recreated Docker API/worker containers from the latest source so the live visual/debug changes are active in runtime.
- Confirmed active runtime inside the API container: `AI_MODEL_PATH=models/yolo11m.pt`, `ROI_MODE=full_frame`, `AI_IMGSZ=960`.
- Live annotated output now exposes model/debug context in the session snapshot: `model_name`, `roi_mode`, `ai_imgsz`, and `latest_debug`.
- The renderer overlays bottom-center anchors, anchor trails, lane candidate/locked labels, and recent count-event markers on top of the existing lane polygons, counting lines, boxes, and track IDs.
- Frontend live metrics now show the active model, ROI mode, and image size so the operator can verify whether live inference is using the expected runtime profile.
- Validation passed: `pytest tests -q` -> 143 passed; `frontend npm run build` -> passed; batch E2E upload/preview/submit/result -> passed with task `276f5f0d-3e44-4153-a691-720c464c5e18`.
- Live smoke test on `https://youtu.be/1EamsYw_Xyo` resolved YouTube HLS at 1920x1080/30 FPS and ran for 30 seconds with no runtime error; final sampled status was `running`, `frames_read=914`, `frames_processed=76`, `frames_dropped=380`, `fps=2.44`, `lane_volume_total=0`.
- Latest annotated live frame was successfully fetched from `GET /live/sessions/{session_id}/frame` and saved to `scratch/live_vietnam_model_frame.jpg` during the smoke test.

Current interpretation: the live path is operational and visually debuggable, but YOLO11m at `imgsz=960` on 1080p YouTube HLS is accuracy-first and may process only a few FPS depending on stream/network/GPU load. Dropped frames are expected in realtime mode because the system favors fresh frames over queue buildup.

## [2026-07-14] frontend | Epic 1 — Operator Workflow and Button Semantics

- Clarified the production workflow labels from broad wizard names to deploy-oriented steps: Source -> ROI -> Lanes -> Run.
- Added short help text to each wizard step so operators know what must be done before progressing.
- Replaced inactive top-bar Settings/Help icon buttons with a visible `Deploy-ready UI` badge and a real reset-workflow button.
- Added reset workflow behavior that clears source, preview, ROI, lanes, submitted config, task status, results, and logs.
- Updated ROI copy to match the current architecture: detection runs full-frame while ROI is used for analytics/lane context/operator review.
- Added explicit ROI actions: `Reset ROI` and `Full Frame`.
- Renamed lane submit action by mode: `Submit Batch Task` for uploaded files and `Validate Live Config` for live streams.
- Improved live controls: `Start Live`, `Stop`, and `Clear Session` now have disabled states/titles that explain operator intent.
- Added lightweight status styling for running/configured/failed/stopping states.
- Validation: `npm --prefix frontend run build` passed.

## [2026-07-14] frontend | Epic 2 — Live/Source Readiness Checklist

- Added an operator-facing `Start readiness` checklist to the live traffic panel.
- Checklist now confirms source resolution, stream URL availability, validated ROI/lane geometry, and clear session state before `Start Live` can run.
- Each readiness row shows a ready/blocked visual state and a short recovery hint so operators know what to fix next.
- Tightened `Start Live` enablement to use the checklist result rather than scattered URL/config checks.
- Validation: `npm --prefix frontend run build` passed.

## [2026-07-14] frontend | Epic 3 — Dashboard Layout for Output, Metrics, and Debug State

- Rebalanced the run dashboard so video/live output is the primary panel with metrics and debug state beside it.
- Added output summary cards for mode, runtime state, and frame health directly under the video surface.
- Added a `Runtime debug` panel for source/session/status/stage/model/ROI/imgsz/error inspection.
- Preserved lane chart, live controls, live metrics, console, and JSON access while reducing ambiguity for live validation.
- Validation: `npm --prefix frontend run build` passed.

## [2026-07-14] frontend | Epic 4 — Error Recovery UX

- Added dismissible operator alerts for recoverable frontend/backend failures.
- Upload, live resolve, live config validation, and batch task submission failures now update task state, logs, and operator-facing recovery text.
- Live session errors remain in the live panel and also feed the new debug state table.
- Validation: `npm --prefix frontend run build` passed.

## [2026-07-14] frontend | Epic 5 — Full E2E Validation After UI Pass

- Backend tests passed: `pytest tests -q` -> 143 passed, 1 deprecation warning.
- Frontend build passed: `npm --prefix frontend run build`.
- Batch E2E passed with `python scratch/_test_pipeline.py`: upload, preview, submit, poll, and result completed for task `22742ed7-d235-4194-ab0d-4349254e3a00`.
- Live E2E passed with `python scratch/_test_live_vietnam_model.py`: validate-config, resolve YouTube HLS, start session, poll 30 seconds, fetch JPEG frame, and remove session.
- Live final sample: `running`, `frames_read=914`, `frames_processed=88`, `frames_dropped=368`, `fps=2.59`, `lane_volume_total=1`, `last_error=null`.

## [2026-07-14] batch | ROI crop-local pipeline

- Switched batch defaults to `ROI_MODE=crop_rect`, `ROI_CROP_PADDING=0.10`, `AI_IMGSZ=640`, and `OUTPUT_FRAME_MODE=roi`.
- Frontend now stores crop metadata and emits crop-local ROI/lane geometry while preserving original resolution and crop rects for traceability.
- Worker and runtime engine now run inference on the cropped ROI frame and render ROI-only output for batch crop configs.
- Disabled black polygon masking for the new `crop_rect` batch path; legacy `roi_crop` masking remains backward-compatible.
- Live stream service now falls back to `full_frame` unless `LIVE_ROI_MODE` explicitly enables live crop testing.
- Validation: `pytest tests -q` -> 144 passed, 1 warning; `npm --prefix frontend run build` passed.

## [2026-07-15] fix | ROI Crop Live/Batch + Detection/Tracking Cleanup

- Batch and live are now aligned on crop-first ROI behavior: `ROI_MODE=crop_rect`, `OUTPUT_FRAME_MODE=roi`, `AI_IMGSZ=640`, with live falling back to `full_frame` only when crop metadata is missing or invalid.
- YouTube/HLS live ingest now uses an FFmpeg latest-frame reader with crop pushed into the FFmpeg filter graph, so Python receives ROI frames instead of full 1920x1080 frames.
- Live loop now processes completed inference futures before blocking on stream reads and uses a bounded latest-frame queue to smooth bursty HLS segments without unbounded backlog.
- Batch result publishing now keeps a local `/static/results/{task_id}.mp4` fallback when R2 upload fails, and output videos are transcoded to browser-playable H.264 MP4 (`yuv420p`, `+faststart`) before upload/publish.
- Verified Cloudflare R2 `results/` prefix is reachable: object listing works, public URLs return `200`, `Content-Type=video/mp4`, and byte-range requests are supported.
- Root cause for “video exists but does not play in web” was OpenCV `mp4v` output (`mpeg4` codec), not R2 path failure; new outputs are H.264.
- Detection defaults were tightened for traffic videos: `AI_CONFIDENCE=0.4`, `AI_IOU=0.45`, `AI_MAX_DET=100`, `AI_AGNOSTIC_NMS=false`.
- Tracking defaults were adjusted to reduce ghost IDs: `AI_FRAME_SKIP=1`, `TRACK_MATCH_THRESHOLD=0.3`, `TRACK_BUFFER=8`.
- Added a pre-tracker lane/class filter using bbox bottom-center anchors and padded valid zones (`TRACK_FILTER_ZONE_PADDING_PX=12`) so the tracker does not create IDs for detections outside lane zones.
- Renderer now hides lost tracks and out-of-zone tracks by default via `RENDER_SHOW_LOST=false` and `RENDER_SHOW_OUT_OF_ZONE=false`; these can be enabled for debug review.
- Live session snapshots now include `perf.raw_det`, `perf.kept_det`, `perf.active_tracks`, and `perf.lost_tracks` to verify filter effectiveness.

Validation:

- `pytest tests/test_detection_filter.py tests/test_api_integration.py::TestConfig::test_settings_defaults tests/test_runtime_engine.py::test_process_video_crop_rect_uses_roi_frame_and_metadata -q` passed.
- `npm --prefix frontend run build` passed.
- `docker compose up -d --build` completed and container settings were verified as `AI_CONFIDENCE=0.4`, `AI_FRAME_SKIP=1`, `TRACK_BUFFER=8`, `TRACK_MATCH_THRESHOLD=0.3`, `RENDER_SHOW_LOST=false`, `RENDER_SHOW_OUT_OF_ZONE=false`, `AI_IOU=0.45`, `AI_MAX_DET=100`.

