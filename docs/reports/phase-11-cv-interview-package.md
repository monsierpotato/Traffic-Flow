# Phase 11 - CV And Interview Package

## Status

PASS.

## Mục tiêu

Turn benchmark evidence into concise CV bullets, interview answers, and a metric evidence map.

## Phạm vi đã hoàn thành

- Created a four-bullet CV version and a shorter recruiter version.
- Created interview answers for pipeline, ROI coordinate spaces, lane semantics, tracking, derived GT, model selection, runtime profiling, live scheduling, failure cases, limitations, and AI-assisted development.
- Created evidence map for each metric used in README/CV wording.

## File tạo mới

- `docs/portfolio/cv/trafficflow-cv-bullets.md`
- `docs/portfolio/cv/trafficflow-interview-answers.md`
- `docs/portfolio/cv/trafficflow-evidence-map.md`
- `docs/reports/phase-11-cv-interview-package.md`

## File sửa đổi

- None.

## Commands đã chạy

```powershell
.venv\Scripts\python.exe -c "<read benchmark CSV/JSON summaries>"
```

## Kết quả validation

- pytest: `.venv\Scripts\python.exe -m pytest tests -q` -> 175 passed, 1 existing datetime deprecation warning.
- compileall: `.venv\Scripts\python.exe -m compileall -q src benchmark` -> PASS.
- whitespace: `git diff --check` -> PASS, with Windows CRLF conversion warnings only.
- docs secret scan: no credentials found; matches were only explanatory text about secret/public-release review.
- wiki relative links: PASS, 0 broken links from new wiki index entries.

## Metrics/results

| Metric | Value | Run ID | Evidence |
|---|---:|---|---|
| Held-out detector AP50 / recall | 0.582020 / 0.679091 | `phase04-heldout-yolov8m-docker-gpu-20260718` | `benchmark/reports/detection_summary.csv` |
| Held-out ByteTrack Event F1 / WAPE | 0.942238 / 0.050360 | `e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718` | `benchmark/reports/end_to_end_summary.csv` |
| Uploaded runtime FPS / RTF | 75.829 / 3.033x | `phase07-upload-runtime-bytetrack-production-docker-gpu-20260718-v2` | `benchmark/reports/batch_runtime_summary.csv` |
| Live soak FPS / frame age p95 / drops | 14.895 / 0.9 ms / 0 | `phase08-live-hls-30min-20260718` | `benchmark/reports/live_runtime_report.md` |

## Quyết định kỹ thuật

- CV bullets avoid full-stack ownership.
- AI assistance is documented only for interview use, not CV.
- Metrics are limited to values with evidence.

## Known limitations

- Phase 09 tracker/live ablation and error taxonomy are available as supporting interview evidence.

## Risks

- Do not claim complete ROI ablation coverage until crop ROI GT exists.

## Nội dung cần người dùng review

- Confirm target resume length and whether to use the four-bullet or shorter version.

## Phase tiếp theo được đề xuất

Phase 12 final review and release gate.
