
# Frontend Deploy Readiness

## Epic 1 — Operator Workflow and Button Semantics (2026-07-14)

Goal: make the webapp understandable enough for deployment/testing by a non-developer operator.

Completed changes:

- Workflow steps now read as `Source`, `ROI`, `Lanes`, and `Run`.
- Each step includes a short operational hint.
- Top bar exposes a real reset-workflow action instead of inactive settings/help controls.
- ROI instructions now reflect the full-frame detection architecture.
- ROI tools include `Reset ROI` and `Full Frame` buttons.
- Lane submission button adapts by source mode:
  - batch video: `Submit Batch Task`;
  - live stream: `Validate Live Config`.
- Live controls are explicit:
  - `Start Live`: starts realtime inference after config validation;
  - `Stop`: stops inference but leaves metrics visible;
  - `Clear Session`: removes the backend live session and clears the panel.
- Build validation passed with `npm --prefix frontend run build`.

Remaining deploy-readiness frontend epics:

1. Add a clearer live source/config readiness checklist.
2. Improve dashboard layout for output video, metrics, and debug state.
3. Add user-facing error recovery for upload/live resolve/session failures.
4. Run full E2E after final UI pass.

## Epic 2 — Live/Source Readiness Checklist (2026-07-14)

Goal: prevent operators from starting live inference before the source and geometry are truly ready.

Completed changes:

- Added a `Start readiness` checklist inside the live traffic panel.
- Checklist gates `Start Live` on four operator-visible requirements:
  - live source resolved;
  - stream URL available;
  - ROI and lanes validated;
  - no conflicting active session slot.
- Each checklist row shows a ready/blocked state plus the next action needed.
- `Start Live` now depends on the checklist result instead of only checking URL/config booleans.
- Styling uses lightweight ready/blocked cards so the panel remains deploy-friendly without adding modal friction.

Validation:

- `npm --prefix frontend run build` passed.

## Epic 3 — Dashboard Layout for Output, Metrics, and Debug State (2026-07-14)

Goal: make the run dashboard easier to operate during batch and live validation.

Completed changes:

- Rebalanced the dashboard so the video/live output remains the primary panel.
- Added an output summary row for output mode, runtime state, and frame health.
- Added a dedicated `Runtime debug` panel with source, session, status, stage, model, ROI mode, image size, and last error/detail.
- Kept lane metrics, live metrics, console output, and JSON access visible without hiding the main annotated output.
- Added responsive behavior so the summary/debug layout stacks cleanly on smaller screens.

Validation:

- `npm --prefix frontend run build` passed.

## Epic 4 — Error Recovery UX (2026-07-14)

Goal: make upload/live resolve/session failure recoverable without reading browser console logs.

Completed changes:

- Added dismissible operator alerts above the wizard workspace.
- Upload failures now set an `upload_failed` state, write the failure to logs, and tell the operator to retry the file/backend path.
- Live source resolve failures now set a `source_resolve_failed` state and provide a URL reachability recovery hint.
- Invalid live geometry now sets `live_config_invalid` and directs the operator back to lane/line/vector fixes.
- Batch task submission failures now set `task_submit_failed` and keep the operator on the workflow with a retry hint.
- Live session runtime errors remain surfaced in the live panel and are now also visible in the debug state table.

Validation:

- `npm --prefix frontend run build` passed.

## Epic 5 — Full E2E Validation After UI Pass (2026-07-14)

Goal: verify the deploy-ready frontend pass against frontend, backend, batch, and live runtime gates.

Validation completed:

- Backend tests: `pytest tests -q` passed with 143 tests and 1 deprecation warning.
- Frontend build: `npm --prefix frontend run build` passed.
- Batch E2E: `python scratch/_test_pipeline.py` passed upload -> preview -> task submit -> poll -> result with task `22742ed7-d235-4194-ab0d-4349254e3a00`.
- Live E2E: `python scratch/_test_live_vietnam_model.py` passed validate-config -> resolve YouTube HLS -> start session -> poll 30 seconds -> fetch JPEG frame -> remove session.
- Live E2E final sampled status: `running`, `frames_read=914`, `frames_processed=88`, `frames_dropped=368`, `fps=2.59`, `lane_volume_total=1`, `last_error=null`.

Conclusion: Epics 1-5 are complete for the current deploy-readiness frontend pass.

## Epic 6 — Batch ROI Crop Pipeline (2026-07-14)

Goal: switch batch processing from full-frame/black-mask ROI behavior to padded ROI crop inference and ROI-only output while keeping live stream fallback safe.

Completed changes:

- Frontend still draws ROI on the original preview, then computes a tight ROI bbox plus `ROI_CROP_PADDING=0.10` and displays the padded crop in the lane editor.
- Batch lane config now emits crop-local `roi_polygon`, lane zones, counting lines, direction vectors, `roi_mode=crop_rect`, `output_frame_mode=roi`, `model_imgsz=640`, original resolution, padded crop rect, and processing resolution.
- Worker batch processing crops decoded frames before model inference for `crop_rect`; it no longer applies a black polygon mask on that path.
- Output video for batch `output_frame_mode=roi` is rendered at the padded crop resolution with crop-local overlays and detections.
- Task callbacks/results now carry `roi_mode`, `output_frame_mode`, original/processing resolutions, and crop rect metadata.
- Live now uses the stable crop-first baseline (`ROI_MODE=crop_rect`, `OUTPUT_FRAME_MODE=roi`, `AI_IMGSZ=640`) when valid crop metadata is available, and falls back to full-frame only when crop metadata is missing or invalid.

Validation:

- `pytest tests -q` passed with 144 tests and 1 deprecation warning.
- `npm --prefix frontend run build` passed.

## Epic 7 — ROI Live Stability and Clean Batch Output (2026-07-15)

Goal: make uploaded-video output playable in the web UI, keep live ROI crop mode fast enough for HLS sources, and reduce noisy false track IDs in ROI outputs.

Current runtime defaults:

- `ROI_MODE=crop_rect`
- `OUTPUT_FRAME_MODE=roi`
- `AI_IMGSZ=640`
- `AI_CONFIDENCE=0.4`
- `AI_IOU=0.45`
- `AI_MAX_DET=100`
- `AI_FRAME_SKIP=1`
- `TRACK_MATCH_THRESHOLD=0.3`
- `TRACK_BUFFER=8`
- `TRACK_FILTER_ZONE_PADDING_PX=12`
- `RENDER_SHOW_LOST=false`
- `RENDER_SHOW_OUT_OF_ZONE=false`

Completed changes:

- Batch output video is ROI-only and published through `outputs.video_path`; if R2 upload is unavailable, the worker writes `/static/results/{task_id}.mp4`.
- Worker transcodes rendered MP4 artifacts to browser-compatible H.264 before publishing, fixing cases where R2 returned a valid MP4 that the browser could not play.
- Cloudflare R2 `results/` access was verified independently: list, public `HEAD`, and byte-range `GET` all work.
- Live YouTube/HLS uses FFmpeg latest-frame ingest and crops in FFmpeg before piping frames to Python, reducing full-frame copy/decode pressure.
- Frontend live result view should show ROI-only annotated JPEG frames, while batch result view should play the H.264 ROI MP4 from R2 or local static fallback.
- Detection noise mitigation is now part of the processing path: raw YOLO detections are filtered by lane `valid_zone` and `class_allowed` before tracker update, using bottom-center anchors.
- Output overlays hide lost/out-of-zone tracks by default so operator-facing videos do not show grey ghost IDs unless debug flags are enabled.

Operator validation checklist:

- After a batch completes, call `/tasks/{task_id}/result` and confirm `outputs.video_path` is non-empty.
- Open `outputs.video_path` directly; it should return `200`, `Content-Type: video/mp4`, and support `Accept-Ranges: bytes`.
- Run `ffprobe` on the returned video and confirm `codec_name=h264` and `pix_fmt=yuv420p` for new outputs.
- Inspect worker logs for `raw_det`, `kept_det`, `active_tracks`, and `lost_tracks`; expected behavior is `kept_det` much lower than `raw_det` on noisy traffic scenes.
- If false motorcycles remain high, raise `AI_CONFIDENCE` to `0.5` for the next test run before changing tracker settings.

Validation completed:

- Detection filter tests passed.
- Runtime crop regression test passed.
- Frontend production build passed.
- Docker API/worker containers were rebuilt with the new defaults.

