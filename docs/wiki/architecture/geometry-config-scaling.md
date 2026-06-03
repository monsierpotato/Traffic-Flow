# Geometry Config Scaling

## Summary

Onboarding a new camera currently requires a human to hand-draw `valid_zone`, `counting_line`, and `direction` per lane in `trafficflow/cli/config_generator.py` before the counting pipeline can run. This manual step scales linearly with camera count and is the main bottleneck when moving from a handful of cameras to many. This page captures the analysis and the recommended phased plan for removing that bottleneck without losing per-lane / per-direction / per-class count granularity.

## Problem Framing

- The bottleneck is a human-in-the-loop step whose cost grows linearly with camera count.
- "Scale" is assumed here to mean **more cameras**. It could also mean more video-hours per camera or higher accuracy demands — these pull differently, so confirm the dominant axis before committing.
- Geometry is the most *visible* manual step, but the run is also GPU-bound (YOLOv8 + ByteTrack per stream). Removing the human step relocates the constraint to compute. **Validate streams-per-GPU at target resolution before investing in inference** — if compute is the real wall, the right work is `worker/` scheduling, not geometry inference.
- Manual configs are currently treated as ground truth, but their own error is unquantified.

## Current State

- Config is a frozen, versioned JSON schema (`version`, `camera_id`, `resolution`, `method`, `lanes`) — see `trafficflow/counting/config.py` and [[Lane Config Contract]]. It is already shaped for a service boundary.
- `trafficflow/api`, `worker`, `queue`, `storage` exist as stubs (see [[Production Architecture]]). The architecture anticipates a service; it is not one yet.
- Cameras are high-res (e.g. 3840×2160) with oblique, skewed-quadrilateral zones (`counting_gate`), not top-down axis-aligned boxes. Auto-inference is harder in this regime.
- Geometry is stored in source-frame pixel coordinates tied to a specific resolution; a resolution change silently invalidates a config.

## Solution Options

### Option 1 — Industrialize manual geometry
Move `config_generator` behind the planned `api/` boundary as a web annotation tool (draw on a JPEG frame, POST the same JSON). Add config versioning, a resolution-change "needs re-annotation" flag, and template-from-similar-camera.

- **Pros:** zero accuracy regression; smallest change; builds the real first `api/` + `storage/` seam.
- **Cons:** still O(cameras) human labor — cheaper per unit, not fewer units.
- **Risk:** low technical risk, high ceiling risk (reappears at higher scale).

### Option 2 — Automate geometry inference
Infer the config a human draws: run the detector over N minutes of a new camera, cluster ByteTrack trajectories into lane corridors → `valid_zone`; dominant flow per cluster → `direction`; perpendicular at corridor mid-point → `counting_line`. Output the same JSON, route low-confidence cameras to a human for a short correction.

- **Pros:** the only option that breaks the linear-labor curve; reuses tracking output already computed; review-cost ≪ authoring-cost.
- **Cons:** trajectory clustering is fragile on oblique 4K merging/diverging lanes and low-traffic warm-up; adds an ML subsystem; failure mode is **silent** under-counting.
- **Risk:** medium-high. Never auto-accept without a confidence gate and an audit sample.

### Option 3 — Change the counting paradigm
Make geometry matter less: (3a) zone-free counting of unique track IDs with flow-direction binning; (3b) a learned per-class flow/density model calibrated once per camera with a count, not a drawing.

- **Pros:** attacks the root assumption; 3a is cheap to prototype.
- **Cons:** loses per-lane / per-direction / per-class granularity that `counting_gate` provides today — often the actual product requirement. **Do not pursue unless the count consumer explicitly relaxes granularity.**
- **Risk:** high product risk (wrong granularity) more than technical risk.

## Cross-Domain Anchor

This is the OCR / document-digitization pattern: full automation drowns in silent errors; the winning shape is **confidence-routed human-in-the-loop** — machine handles the confident majority, routes the uncertain remainder to a human who *corrects* rather than *authors*, and every correction becomes future training signal. Keep a manual override first-class (the database query-planner lesson: optimizers won by being cheap and overridable, not always right).

## Recommendation

**Sequence Option 1 → Option 2, gated by measurement. Do not pursue Option 3 unless granularity is explicitly relaxed.**

Option 1 is the correct first move regardless of endpoint — it builds the `api/` + `storage/` seam the architecture already anticipates and gives Option 2 a review UI and a manual-config corpus to validate against. Option 2 on top of Option 1 is the OCR success pattern; Option 2 alone is the cautionary tale.

## Implementation Roadmap

| Step | Work | Depends on | Notes |
|---|---|---|---|
| 1 | Lift frame-grab + JSON-emit from `config_generator` into `trafficflow/api/`, persist via `storage/`; add `source: "manual"` + resolution-change invalidation (`version` bump) | — | Shippable value alone; first real `api/` endpoint |
| 2 | Build a config-scoring harness: score any config against hand-counts on a held-out clip | — | **Cheap, and the only thing that makes automation safe to trust. Do before any inference.** |
| 3 | Add `trafficflow/geometry/inference.py`: cluster ByteTrack trajectories → candidate `valid_zone` / `direction` / `counting_line`, stamped `source: "inferred"` + confidence | 2 | Test first on least-oblique cameras |
| 4 | Confidence-route: auto-accept high-confidence; push the rest to the Step 1 web UI as a pre-filled config the human nudges | 1, 3 | Correction rate = real automation % |
| 5 | Wire new-camera bootstrap as a `queue/` job → `worker/` runs inference → human review → activated config | 1, 3, 4 | First non-trivial workload for the stubbed packages |

## Success Metrics

- Median time-to-onboard a new camera: hours → <5 min auto-accepted, <2 min nudge for routed.
- % cameras auto-accepted without human edit.
- Count error of inferred vs. manual configs on the held-out harness; gate auto-accept (e.g. <5% deviation).
- Zero silent-drift incidents: every active config carries provenance + last-audited timestamp.

## Risk Mitigation

- Provenance-stamp every config (`manual` vs `inferred`).
- Never auto-accept without the Step 2 scoring harness.
- Keep manual override first-class.
- Audit a random sample of inferred configs monthly.

## Open Questions / Confidence

- **High confidence:** Option 1 is the right first step; the provenance + measurement discipline is non-negotiable.
- **Medium confidence (load-bearing):** that trajectory clustering reaches trustworthy auto-accept rates on *these* oblique 4K scenes. A 1-week spike on existing Đà Nẵng footage would resolve it.
- **Would change the recommendation:** if streams-per-GPU is the true binding constraint, priority flips to `worker/` scheduling; if the consumer only needs aggregate counts, Option 3 becomes viable.
- Should source-frame pixel geometry be normalized to a resolution-independent representation now, before configs proliferate and migration gets expensive?

## Links

- [[Production Architecture]]
- [[Project Backlog]]
- [[Lane Config Contract]]
- [[ROI Annotation]]
- [[Decision Log]]
