# Final Portfolio Report

## Status

READY_FOR_CV

READY_FOR_TECHNICAL_INTERVIEW

READY_FOR_GITHUB is conditional on demo media/link and public-release secret/data review.

## Evidence Summary

| Area | Result | Evidence |
|---|---:|---|
| Held-out detection | AP50 0.582020, recall 0.679091 | `benchmark/reports/detection_report.md` |
| Held-out E2E tracking, direct ByteTrack | HOTA 0.242433, IDF1 0.284952, IDSW 42 | `benchmark/reports/end_to_end_report.md` |
| Held-out E2E counting, direct ByteTrack | Event F1 0.942238, WAPE 0.050360 | `benchmark/reports/end_to_end_report.md` |
| Uploaded-video runtime | 75.829 FPS, 3.033x real time, 2878 MB VRAM peak | `benchmark/reports/batch_runtime_report.md` |
| Live/HLS runtime | 14.895 FPS, frame age p95 0.9 ms, 0 dropped frames over 1803.284 s | `benchmark/reports/live_runtime_report.md` |
| Phase 09 failure analysis | Tracker/live ablations documented; ROI accuracy ablation blocked by missing crop ROI GT | `benchmark/reports/ablation_report.md` |

## Documentation Package

- `README.md`
- `docs/portfolio/recruiter-overview.md`
- `docs/portfolio/ai-pipeline.md`
- `docs/portfolio/error-analysis.md`
- `docs/portfolio/limitations.md`
- `docs/portfolio/runtime-optimization-case-study.md`
- `docs/portfolio/cv/trafficflow-cv-bullets.md`
- `docs/portfolio/cv/trafficflow-interview-answers.md`
- `docs/portfolio/cv/trafficflow-evidence-map.md`
- `docs/portfolio/release-checklist.md`

## Scientific Validity

The benchmark uses sequence-level splits, frozen manual geometry, derived counting GT with audit artifacts, detection/tracking/counting/runtime metrics, Phase 09 ablation/error taxonomy artifacts, and preserved raw artifacts. Held-out results are separated from development model/tracker choices.

Phase 09 is `PARTIAL PASS`: tracker and live scheduling analysis are documented, while ROI accuracy ablation is blocked until crop ROI GT exists.

## Engineering Validity

The documentation package points to reproducible commands and run IDs.

Final validation:

- pytest: 175 passed, 1 existing datetime deprecation warning.
- compileall: PASS.
- `git diff --check`: PASS, with Windows CRLF conversion warnings only.
- docs secret scan: no credentials found; matches were only explanatory text about secret/public-release review.
- wiki relative links: PASS.

## Ownership Validity

The project is framed as a five-member team project. Personal contribution is scoped to AI/computer-vision pipeline ownership and live runtime analysis/validation. Full-stack/platform ownership is not claimed.

## Release Decision

- Use the CV bullets now.
- Use the technical interview answers now, while acknowledging the ROI-ablation blocker if asked about full-frame vs crop-ROI accuracy.
- Publish GitHub after adding demo media/link and confirming public-safe data/model/secret handling.
