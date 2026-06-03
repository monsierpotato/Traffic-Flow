# TrafficFlow Wiki Log

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
