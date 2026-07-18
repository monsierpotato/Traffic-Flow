# Phase 00 - Repository Audit and Baseline Freeze

## Status

PASS

Phase 00 completed the repository audit artifacts and a scoped baseline-fix pass. Validation is now clean with the project `.venv` interpreter.

## Mục tiêu

Freeze trạng thái thật của source code trước khi bổ sung benchmark hoặc portfolio claim mới.

## Phạm vi đã hoàn thành

- Đọc kế hoạch tại `docs/raw/plan (2).md` và tuân thủ rule bắt đầu từ Phase 00.
- Audit hai runtime path chính:
  - Upload/batch path: API upload/task route -> Celery worker -> local/remote inference -> tracker -> counting -> renderer -> callback/report.
  - Live/HLS path: FastAPI live route/service -> FFmpeg/OpenCV reader -> local/remote inference -> pre-tracker filtering -> tracker -> counting -> MJPEG/status.
- Freeze model inventory bằng SHA256.
- Freeze config baseline từ `src/shared/config.py`, `docker-compose.yml`, và README.
- Ghi environment snapshot của host local.
- Tạo ownership matrix không phóng đại phạm vi cá nhân.
- Mirror báo cáo vào wiki theo yêu cầu người dùng.
- Sửa các lỗi baseline trực tiếp chặn Phase 00/benchmark sau này:
  - `LocalInferenceClient` nhận optional `imgsz`.
  - Local YOLO class-id parser thực sự parse `AI_CLASS_IDS`.
  - API task serialization giữ `processing_roi` và metadata geometry.
  - Upload worker dùng `crop_rect` như crop-enabled mode, shift lane source-frame sang crop-local, và không còn dùng biến `lanes` chưa định nghĩa.
  - Test config được cập nhật theo defaults hiện tại.

## Code Path Map

| Area | Current path | Notes |
|---|---|---|
| Upload create task | `src/api/services/upload_service.py`, `src/api/routes/upload.py` | Normalize/store video, create preview/task document. |
| Upload enqueue | `src/api/routes/tasks.py` | Requires lane config, sends `trafficflow.process_video` to Celery queue. |
| Batch AI processing | `src/worker/celery_app.py` | Downloads working video, preprocesses frames, calls inference, tracks, counts, renders, writes benchmark summary. |
| Live source resolve/config | `src/api/routes/live.py` | Resolves YouTube/HLS/source preview and validates geometry before live session. |
| Live AI runtime | `src/api/services/live_service.py` | Runs inside API process, not Celery worker. Uses FFmpeg latest-frame reader when available. |
| Model inference | `src/worker/pipeline/local_client.py`, `src/tfengine/core_ai/detector.py`, `src/worker/pipeline/ai_client.py` | Local YOLO or remote Modal-style HTTP endpoint. |
| ROI/coordinate transform | `src/worker/pipeline/processor.py` | Letterbox transform maps AI bboxes back to crop/full frame. |
| Filtering | `src/worker/pipeline/detection_filter.py` | Pre-tracker filtering used in live service. |
| Tracking | `src/worker/pipeline/tracker.py` | Local Kalman tracker with timestamp-aware dt, association, min hits, and time/frame TTL. |
| Counting | `src/worker/services/counting_service.py` | Bottom-center anchor, lane lock, direction validation, line crossing, duplicate prevention. |
| Rendering | `src/worker/pipeline/renderer.py` | Draws lanes/counting lines/tracks; hides unconfirmed/lost/out-of-zone by default. |
| Runtime metrics | `src/worker/pipeline/profiler.py`, `src/api/services/live_service.py` | Batch has profiler summaries; live exposes per-session perf fields. |
| Existing benchmark | `benchmark/run_benchmark.py`, `benchmark/run_full_benchmark.py`, `benchmark/detrac/` | Historical DETRAC runner exists but lacks the new frozen split/protocol/run manifest standard. |

## File tạo mới

- `docs/reports/phase-00-repository-audit.md`
- `docs/portfolio/project-scope-and-ownership.md`
- `benchmark/baseline/current_defaults.yaml`
- `benchmark/baseline/environment.json`
- `benchmark/baseline/model_inventory.json`
- `docs/wiki/ai-workflow/phase-00-repository-audit.md`

## File sửa đổi

- `docs/wiki/index.md`
- `docs/wiki/log.md`
- `.agent_scratchpad.md`
- `src/api/routes/tasks.py`
- `src/worker/celery_app.py`
- `src/worker/pipeline/local_client.py`
- `tests/test_api_integration.py`

## Commands đã chạy

```bash
Get-Content -LiteralPath 'docs/raw/plan (2).md'
rg --files
git status --short --branch
Select-String ... TrafficFlow memory quick pass
Get-FileHash -Algorithm SHA256 models/*.pt
.venv\Scripts\python.exe -c "<environment snapshot>"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
ffmpeg -version
ffprobe -version
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m compileall -q src benchmark
git diff --check
docker compose config
```

## Kết quả validation

- `pytest`: PASS - 151 passed, 1 warning.
  - Command: `.venv\Scripts\python.exe -m pytest tests -q`
  - Warning: existing `datetime.utcnow()` deprecation in `tests/test_api_integration.py::TestTaskSchemas::test_task_status_response`.
- `compileall`: PASS for `src` and `benchmark`.
- `git diff --check`: PASS.
- `docker compose config`: PASS. Secret values appeared in command output and were intentionally not copied into reports/artifacts.
- `frontend build`: not run because Phase 00 did not touch frontend.

## Metrics/results

| Metric | Value | Run ID | Evidence |
|---|---:|---|---|
| Portfolio metric | Not generated | phase-00-repository-audit-2026-07-17 | Phase 00 is audit-only |
| Tests passed | 151 | phase-00-repository-audit-2026-07-17 | `.venv\Scripts\python.exe -m pytest tests -q` |
| Tests failed | 0 | phase-00-repository-audit-2026-07-17 | full test suite |
| Model files inventoried | 5 | phase-00-repository-audit-2026-07-17 | `benchmark/baseline/model_inventory.json` |

## Audit Findings

| Severity | Finding | Evidence | Status |
|---|---|---|---|
| High | Live service calls `LocalInferenceClient(max_workers=1, imgsz=settings.ROI_INPUT_SIZE)`, but constructor did not accept `imgsz`. | `src/api/services/live_service.py:555`, `src/worker/pipeline/local_client.py` | Fixed in baseline pass. |
| High | Batch/upload worker referenced `lanes` at `CountingState(lanes)` and `FrameRenderer(lanes)` even though the parsed variable was `lanes_source`. | `src/worker/celery_app.py` | Fixed by using `lanes_processing`. |
| High | Batch/upload crop condition checked only `ROI_MODE == "roi_crop"`, while Docker baseline uses `ROI_MODE=crop_rect`. | `src/worker/celery_app.py`, `docker-compose.yml` | Fixed by treating `crop_rect` as crop-enabled and normalizing lane geometry. |
| Medium | `_parse_class_ids()` returned `None` before the parsing block, so `AI_CLASS_IDS=2,3,5,7` was not enforced in local YOLO inference. | `src/worker/pipeline/local_client.py`, `tests/test_api_integration.py` | Fixed and covered by a parser test. |
| Medium | Local host Python is CPU-only (`torch 2.13.0+cpu`) even though GPU exists via `nvidia-smi`; formal benchmark should run in Docker GPU or a CUDA venv. | `benchmark/baseline/environment.json` | Open. Do not use host Python timing for portfolio metrics. |
| Medium | `ffmpeg`/`ffprobe` are not in host PowerShell PATH. | command failure during audit | Open. Live host-run checks may fail outside Docker. |
| Medium | Historical DETRAC benchmark exists, but it predates the new required split/protocol/manifest standard. | `docs/wiki/log.md`, `benchmark/reports/` | Open. Treat old numbers as historical only. |
| Low | README current live baseline is fresher than some older wiki benchmark notes; wiki needs future consolidation after benchmark phases. | `README.md`, `docs/wiki/log.md` | Open. Address in Phase 10 documentation pass. |

## Model inventory

See `benchmark/baseline/model_inventory.json`.

Current notable model baseline:

- `models/yolo11m.pt`, SHA256 `D5FFC1A674953A08E11A8D21E022781B1B23A19B730AFC309290BD9FB5305B95`, used by Docker/README stable live baseline.

## Environment snapshot

See `benchmark/baseline/environment.json`.

Key points:

- Host GPU: NVIDIA GeForce RTX 5070 Ti, driver 591.74, 16303 MiB.
- Default PowerShell Python: Anaconda Python 3.13.9, missing FastAPI.
- Project validation Python: `.venv\Scripts\python.exe`, Python 3.13.9.
- Project `.venv` torch: `2.13.0+cpu`, CUDA unavailable.
- Docker compose renders GPU reservations for API and worker.

## Quyết định kỹ thuật

- Initial Phase 00 audit found blocking baseline issues; a scoped baseline-fix pass was applied before marking the phase PASS.
- The scoped fixes align runtime with the documented baseline but do not introduce benchmark protocol, dataset split, new metrics, or CV claims.
- Secrets from `docker compose config` were not copied into artifact files.
- Existing benchmark outputs are preserved and not overwritten.
- Report status is `PASS` because required validation is clean after the baseline-fix pass.
- The wiki mirror links to this report instead of duplicating every detail.

## Known limitations

- No formal benchmark metric was produced.
- No UA-DETRAC split was frozen yet.
- No manual derived-GT audit was performed yet.
- No Docker container runtime environment snapshot was collected beyond `docker compose config`.
- Host/project `.venv` Python is CPU-only and is not suitable for final GPU benchmark timing.

## Risks

- The baseline-fix pass changes runtime behavior in narrow compatibility areas; benchmark phases must cite the current commit/config after these fixes.
- If old DETRAC reports are reused without re-freezing protocol, CV claims could be unsupported.
- Live 15 FPS historical result needs a formal soak test before CV use.

## Nội dung cần người dùng review

- Confirm personal scope wording in `docs/portfolio/project-scope-and-ownership.md`.
- Confirm the scoped Phase 00 baseline fixes are acceptable.
- Confirm whether final benchmark should run inside Docker GPU rather than host Python.

## Phase tiếp theo được đề xuất

Phase 01 - Benchmark protocol and dataset split.

Per the plan STOP GATE, wait for user confirmation before moving to Phase 01.
