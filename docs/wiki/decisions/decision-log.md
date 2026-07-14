# Decision Log

## Accepted Decisions

- Use `trafficflow.runtime.engine` as the reusable AI workflow entrypoint.
- Keep `trafficflow.cli.run_counting` as a thin wrapper.
- Add production boundaries for API, worker, queue, storage, and observability before implementing each layer.
- Use rectangular ROI for lane drawing support.
- Use `annotation crop: yes; processing crop: no` for the MVP.
- Store lane geometry in source-frame coordinates.
- Support rectangular annotation ROI in the OpenCV config generator before building the web canvas flow.
- **Package separation**: Name backend app `backend/` and AI core library `ai-core/` to resolve namespace collision.
- **Task status state machine**: Reject re-processing of completed/failed/archived tasks; reject concurrent processing with 409 Conflict.
- **Pipeline refactoring**: Split monolithic `celery_app.py` (499 lines) into 4 single-responsibility `pipeline/` modules — `processor.py`, `ai_client.py`, `tracker.py`, `renderer.py` — for testability and maintainability.
- **Local Kalman tracking (approach B)**: Worker runs `LocalTracker` with 8-state Kalman filter (cx,cy,w,h,vx,vy,vw,vh) instead of center-dead-reckoning velocity. Provides smooth velocity (converges in 2-3 frames) and lost-track prediction up to 30 frames. Strips Modal ByteTrack track IDs and re-tracks locally.
- **DirectionFilter with cosine similarity**: Replace raw dot-product direction check with `cos_sim >= 0.3` threshold to reject perpendicular movement (e.g. RIGHT-moving car on UP lane → cos_sim=0 → rejected).
- **COCO 4-class canonical**: Standardize vehicle classes to COCO: `car (2)`, `motorcycle (3)`, `bus (5)`, `truck (7)`. Filter early via `YOLO.track(classes=[2,3,5,7])` instead of post-processing filter. Legacy alias `motorbike` → `motorcycle`.
- **1 GPU = 1 Celery worker process**: Celery `--concurrency=1` for GPU inference. Two processes sharing 1 GPU causes contention, OOM, and degraded throughput.
- **FP16 inference on GPU**: `AI_HALF=true` enables half-precision for CUDA devices. Auto-disabled on CPU fallback.
- **Local Docker GPU deployment**: Dropped Modal GPU HTTP API; YOLOv8 runs locally via `LocalInferenceClient` with CUDA acceleration (RTX 5070 Ti). Removes network latency, Modal credit cost, and OpenCV 5.0.0 compatibility issues.
- **OpenCV 4.10.x for ONNX inference**: OpenCV 5.0.0 `cv::gemm` crashes every other frame with `matmul.dispatch.cpp:363` error. Downgraded to `opencv-python==4.10.0.84`. See taste: "Avoid OpenCV 5.0.0 for ONNX model inference."
- **UA-DETRAC as benchmark ground truth**: Use public UA-DETRAC dataset (Beijing/Tianjin traffic, 60 train sequences, 8.2K annotated vehicles) for objective counting accuracy measurement. Class map: car→car, bus→bus, van→truck, others→skip. No motorcycle class available — needs synthetic data for 4th class.
- **Benchmark sweet spot**: `optimized-a-yolov8n-fp16-640` (FP16, imgsz=640, frame_skip=2) delivers best accuracy-speed balance: ~6% counting error, 24 FPS, 1.8× real-time, ~3.4GB VRAM on RTX 5070 Ti.
- **Preprocess is bottleneck, not inference**: At 640px, inference takes ~8ms (FP16) but preprocess (decode+resize+normalize) takes ~14ms. Optimization priority: preprocess pipeline, not model size.
- **Per-video lane config required**: A single default counting line (y=50%) produces 40% error on unseen camera angles. Each DETRAC sequence needs its own lane geometry for fair benchmark comparison.
- **Benchmark-first optimization**: Every pipeline change is measured with per-stage timing (preprocess/inference/tracking/counting/overlay/encode) and resource sampling (GPU/VRAM/CPU/RAM). No optimization without evidence.
- **Ground truth by manual count annotation**: Benchmark accuracy uses per-lane-per-class manual counts (not full bbox annotation). Error metric = absolute count difference + error %. Sufficient for traffic counting system goals.
- **ROI crop + letterbox 640×640**: Inference runs on cropped ROI bbox, letterboxed/padded to 640×640 square. Replaces linear resize-to-longest-edge. YOLO sees fewer background pixels, objects appear larger. `FrameTransform` handles full bbox coordinate chain: AI-space → crop-space → full-frame-space.

## Proposed / Under Review

- Geometry config scaling: industrialize manual config first (web annotation behind `api/`), then automate geometry inference with confidence-routed human review; build a config-scoring harness before any inference. Do not change the counting paradigm unless count granularity is explicitly relaxed. See [[Geometry Config Scaling]].

## Deferred Decisions

- Whether to add ONNX/OpenVINO optimization before or after local end-to-end MVP.
- Whether MVP database starts with SQLite or PostgreSQL.
- Whether the OpenCV config generator needs ROI editing after lanes have already been added.

## Links

- [[Production Architecture]]
- [[ROI Annotation]]
- [[Project Backlog]]
- [[Geometry Config Scaling]]
