# Phase 10 - GitHub Documentation

## Status

PASS. Later Phase 09 completion updated the documentation package; ROI accuracy ablation remains the only disclosed blocker.

## Mục tiêu

Convert benchmark outputs into recruiter- and interviewer-readable GitHub documentation without inflated ownership claims.

## Phạm vi đã hoàn thành

- Rewrote root `README.md` using the required 16-section structure.
- Added recruiter overview, AI pipeline explanation, interim error analysis, and limitations pages.
- Preserved evidence paths for every metric in the README key-results table.
- Kept team ownership and personal contribution separated.

## File tạo mới

- `docs/portfolio/recruiter-overview.md`
- `docs/portfolio/ai-pipeline.md`
- `docs/portfolio/error-analysis.md`
- `docs/portfolio/limitations.md`
- `docs/reports/phase-10-github-documentation.md`

## File sửa đổi

- `README.md`

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
| Held-out detection AP50 / recall | 0.5820 / 0.6791 | `phase04-heldout-yolov8m-docker-gpu-20260718` | `benchmark/reports/detection_report.md` |
| Held-out E2E Event F1 / WAPE, ByteTrack | 0.942238 / 0.050360 | `e2e-heldout-bytetrack-vs-production-full-docker-gpu-20260718` | `benchmark/reports/end_to_end_report.md` |
| Uploaded-video FPS / RTF | 75.829 / 3.033x | `phase07-upload-runtime-bytetrack-production-docker-gpu-20260718-v2` | `benchmark/reports/batch_runtime_report.md` |
| Live FPS / frame age p95 / drops | 14.895 / 0.9 ms / 0 | `phase08-live-hls-30min-20260718` | `benchmark/reports/live_runtime_report.md` |

## Quyết định kỹ thuật

- README uses direct ByteTrack as the strongest measured end-to-end offline baseline.
- Oracle tracking/counting results are explicitly scoped as evaluator isolation, not production claims.
- Phase 09 tracker/live analysis and ROI blocker are disclosed in error-analysis and limitations pages.

## Known limitations

- Formal ROI accuracy ablation was not run because comparable crop ROI GT is unavailable.
- Demo link remains a placeholder.

## Risks

- Recruiter-facing numbers are strong enough for CV/README. A technical interviewer may ask about ROI; the docs now disclose the GT blocker.

## Nội dung cần người dùng review

- Confirm whether to include a public demo link or keep it as `TBD`.
- Confirm whether crop ROI GT should be collected before claiming ROI accuracy coverage.

## Phase tiếp theo được đề xuất

Phase 11 CV and interview package.
