# TrafficFlow Release Checklist

## Final Gate

| Status | Decision | Reason |
|---|---|---|
| READY_FOR_CV | GRANTED | CV bullets use only measured metrics with evidence map and team-scoped contribution wording. |
| READY_FOR_TECHNICAL_INTERVIEW | GRANTED | Core pipeline, metrics, runtime evidence, and Phase 09 failure analysis are documented. |
| READY_FOR_GITHUB | CONDITIONAL | README is project-readable, but public release should add demo media/link, keep the ROI-ablation blocker visible, and keep large runtime assets deliberate. |

## Scientific Validity

| Check | Status | Evidence |
|---|---|---|
| Split by sequence, not frame | PASS | `benchmark/splits/ua_detrac_split_v1.json` |
| Held-out not used for tuning | PASS | `docs/portfolio/benchmark-methodology.md` |
| Geometry frozen before scoring | PASS | `benchmark/configs/geometry_manual/`, `docs/reports/phase-02-derived-ground-truth.md` |
| Derived GT has audit | PASS | `docs/reports/phase-02-derived-ground-truth.md` |
| Counting has event and aggregate metrics | PASS | `docs/reports/phase-06-counting-benchmark.md`, `docs/reports/end-to-end-bytetrack-production-comparison.md` |
| Tracking has association metrics | PASS | `docs/reports/phase-05-tracking-benchmark.md`, `docs/reports/end-to-end-bytetrack-production-comparison.md` |
| Runtime separates model latency and pipeline throughput | PASS | `docs/reports/phase-07-upload-runtime.md`, `docs/reports/phase-08-live-runtime.md` |
| Formal ablation/error taxonomy complete | PARTIAL | Phase 09 tracker/live analysis is complete; ROI accuracy ablation is blocked by missing crop ROI GT. |

## Engineering

| Check | Status | Evidence |
|---|---|---|
| Tests pass | PASS | Phase 12 validation run |
| Benchmark commands documented | PASS | `README.md`, `benchmark/README.md` |
| Raw predictions/artifacts retained outside the curated public docs | PASS | Public summaries in `docs/reports/`; raw benchmark artifacts are local/generated storage. |
| Reports include run IDs | PASS | `docs/reports/*.md` |
| No private credentials in docs | PASS | Phase 12 docs scan found no credentials; matches were explanatory secret-review text only. |
| Documentation matches code paths | PASS | README and portfolio docs reference current `src/` and benchmark modules. |

## Ownership

| Check | Status | Evidence |
|---|---|---|
| Team size recorded | PASS | `README.md`, `docs/portfolio/project-scope-and-ownership.md` |
| Team and AI/CV contribution scope clear | PASS | `docs/portfolio/project-overview.md`, CV package |
| Live runtime shared contribution scoped | PASS | `README.md`, `docs/portfolio/runtime-optimization-case-study.md` |
| No solo full-stack claim | PASS | `README.md`, CV package |

## Public Readability

| Check | Status | Evidence |
|---|---|---|
| README has short project explanation | PASS | `README.md` |
| README has key-results table | PASS | `README.md` |
| README has team and contribution scope | PASS | `README.md` |
| Demo link placeholder | PARTIAL | Placeholder exists; public media/link still needed. |
| CV has GitHub link placeholder policy | PASS | Add the final repo URL manually when publishing. |
| CV avoids unsupported metrics | PASS | `docs/portfolio/cv/trafficflow-evidence-map.md` |
| Limitations presented | PASS | `docs/portfolio/limitations.md` |

## Publish Blockers

- Add or link a demo clip/image before broad public sharing.
- Do not claim complete ROI ablation coverage until crop ROI GT exists.
- Confirm model weights, UA-DETRAC data, cookies, `.env`, and private storage credentials are excluded from any public push.
