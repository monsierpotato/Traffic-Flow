# TrafficFlow Limitations

## Benchmark Limitations

- Phase 04 detector scoring is sampled with `frame_stride=100`, not exhaustive over every frame.
- Phase 05 oracle tracking uses GT detections, so it isolates association rather than full production detection + tracking.
- Phase 06 oracle counting uses GT-backed prediction events, so it validates counting evaluator plumbing rather than production accuracy.
- Phase 09 is `PARTIAL PASS`: tracker and live scheduling ablations are documented, but formal ROI accuracy ablation is blocked because the UA-DETRAC selected sequences do not have frozen crop ROI GT and the live crop source has no GT.

## Dataset Limitations

- UA-DETRAC in this repo has 100 usable XML/image sequences, all 960x540.
- UA-DETRAC labels do not provide a motorcycle-compatible class, so motorcycle metrics are not reported.
- `van` is mapped to TrafficFlow `truck`, creating a weak truck metric and a known class-mapping caveat.
- The selected benchmark split has no benchmark-safe 1080p or 10+ minute uploaded-video input.

## Runtime Limitations

- Uploaded-video runtime was measured on local generated/available UA-DETRAC MP4 files, not production R2/network transfer.
- Live runtime was measured on one YouTube HLS source for 30 minutes; this is a stability benchmark, not broad network coverage.
- Live operational counts have no accuracy claim without GT.
- Live scheduling ablation uses a historical pending-future smoke run as the old baseline; that run lacks frame-age and loop-idle instrumentation, so it is not a fully symmetric A/B experiment.
- YouTube resolved HLS URLs can expire and may require cookies or challenge-solving dependencies.

## Ownership Limitations

This project should not be presented as solo full-stack ownership. The correct framing is AI/computer-vision pipeline ownership within a five-member team, with live-platform integration as shared work.
