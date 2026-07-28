# Phase 09 - Ablation And Error Analysis

## Status

PARTIAL PASS.

Tracker ablation and live scheduling ablation are documented from frozen benchmark evidence. ROI accuracy ablation is blocked because the 14 UA-DETRAC benchmark sequences have manual lane/counting geometry but no frozen user-drawn crop ROI per sequence. The live crop-ROI config has no GT, so AP/Event F1/WAPE would not be comparable.

## Muc tieu

Show which technical decisions improved or weakened the pipeline, and document failure modes with traceable examples.

## Pham vi da hoan thanh

- Generated ablation summaries, error taxonomy rows, example traces, representative source-frame images, and a local detailed report under `benchmark/`.
- Updated portfolio error analysis and limitations to reflect Phase 09 evidence.
- Added wiki mirror and wiki log entry.

## Key findings

| Area | Finding | Evidence |
|---|---|---|
| Tracker E2E | Direct ByteTrack beats the production re-tracker on held-out tracking/counting. | `docs/reports/end-to-end-bytetrack-production-comparison.md` |
| ROI strategy | Formal full-frame vs crop-ROI accuracy ablation is blocked by missing frozen crop ROI GT for UA-DETRAC. | This report |
| Live scheduling | Current realtime latest-frame loop reached 14.895 FPS, 0 drops, frame-age p95 0.9 ms in a 30-minute soak. | `docs/reports/phase-08-live-runtime.md` |
| Detection | Small/occluded vehicles and `van -> truck` mapping remain major failure modes. | `docs/reports/phase-04-detection-benchmark.md` |

## Commands da chay

```powershell
.venv\Scripts\python.exe -m benchmark.phase09_analysis --print-summary
```

Validation commands:

```powershell
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m compileall -q src benchmark
git diff --check
```

## Ket qua validation

- Phase 09 generator: PASS, created 10 ablation rows, 21 taxonomy rows, and 15 representative example rows.
- pytest: `.venv\Scripts\python.exe -m pytest tests -q` -> 175 passed, 1 existing datetime deprecation warning.
- compileall: `.venv\Scripts\python.exe -m compileall -q src benchmark` -> PASS.
- whitespace: `git diff --check` -> PASS, with Windows CRLF conversion warnings only.
- wiki Obsidian links: PASS, 0 missing links.

## Public Evidence

- `docs/reports/phase-09-ablation-error-analysis.md`
- `docs/portfolio/error-analysis.md`
- `docs/portfolio/limitations.md`
- `docs/wiki/ai-workflow/phase-09-ablation-error-analysis.md`

Generated local artifacts included ablation reports, CSV summaries, error taxonomy rows, example traces, and representative frames under `benchmark/`.

## Acceptance criteria

- Three ablations completed or blocked with specific reason: PASS.
- Error examples trace to sequence/frame/track where available: PASS.
- Limitations specific: PASS.
- Negative finding disclosed: PASS.

## Stop gate

Phase 09 is complete at `PARTIAL PASS`. Stop gate reached before any additional release-prep work.
