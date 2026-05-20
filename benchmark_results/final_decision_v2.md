# Final Decision v2

Date: 2026-05-19

## Runnable Methods

| Method | Status | Role |
|---|---|---|
| UFLD ResNet18 / TuSimple | Passed | Speed baseline and current best smoke-test option |
| LaneATT ResNet18 / TuSimple | Passed | Third runnable lane-only method; optional accuracy candidate |
| PolyLaneNet ResNet50 / TuSimple | Passed, weak quality | Geometry-friendly method, but unstable on current clips |
| ENet-SAD | Blocked | Official weight is Torch7 `.t7`; no PyTorch pretrained checkpoint found |

## Decision

- Main lane-only model for current benchmark report: UFLD.
- Third runnable replacement for ENet-SAD: LaneATT.
- Geometry-friendly candidate: PolyLaneNet, but not production-ready from current results.
- Production fallback for fixed CCTV: manual lane polygons + vehicle bottom-center point.

## Reason

UFLD is the fastest method and looks more stable than the other runnable methods on the current three stock/time-lapse clips. LaneATT is now runnable after CUDA Toolkit and NMS setup, and is a better third benchmark method than forcing ENet-SAD. PolyLaneNet produces convenient polynomial geometry, but current pretrained output hallucinates and crosses lanes too often on these clips.

Before the final report, rerun UFLD and LaneATT on a small Bellevue CCTV sample because the current clips are useful for smoke tests, not for deciding CCTV production quality.
