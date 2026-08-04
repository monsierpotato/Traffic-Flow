# Phase 09 Ablation And Error Analysis

## Status

PARTIAL PASS.

Tracker and live scheduling ablations are documented from frozen benchmark artifacts. ROI strategy ablation is blocked because the 14 UA-DETRAC benchmark sequences have manual lane/counting geometry but no frozen crop ROI GT, while the available live crop-ROI source has no GT.

## Artifacts

- `benchmark/reports/ablation_report.md`
- `benchmark/reports/ablation_summary.csv`
- `benchmark/reports/error_taxonomy.csv`
- `benchmark/reports/phase09_error_examples.csv`
- `benchmark/reports/phase09_error_frames/`
- `docs/reports/phase-09-ablation-error-analysis.md`

## Main Findings

| Topic | Result |
|---|---|
| Tracker E2E | Direct ByteTrack is stronger than the production re-tracker on held-out E2E. |
| ROI | Accuracy ablation blocked until per-sequence crop ROI is frozen for UA-DETRAC or an HLS source gets GT. |
| Live scheduling | Stable loop: 14.895 FPS, dropped-frame ratio 0.0, frame-age p95 0.9 ms. |
| Error taxonomy | Detection misses small/occluded vehicles; truck is weak because UA-DETRAC `van` maps to TrafficFlow `truck`; production re-tracker increases ID churn and missed crossings. |

## Decision

Use direct ByteTrack as the current measured offline baseline for portfolio claims. Keep the production re-tracker as the implementation baseline until a live/upload regression proves it should remain in the product path.
