
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
