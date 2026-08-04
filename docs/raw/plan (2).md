# TrafficFlow AI Pipeline — Kế hoạch triển khai, benchmark và hoàn thiện portfolio

> **Loại dự án:** Dự án nhóm 5 thành viên  
> **Phạm vi cá nhân chính:** AI pipeline, ROI/lane geometry, detection, tracking, counting, evaluation  
> **Đóng góp thứ cấp:** Phân tích, đề xuất và kiểm chứng tối ưu live AI runtime/end-to-end integration  
> **Không nhận ownership cá nhân:** Toàn bộ frontend, general backend platform, storage, authentication hoặc toàn bộ DevOps

---

# 0. Mục tiêu của kế hoạch

Tài liệu này là **nguồn hướng dẫn bắt buộc** cho người hoặc Coding Agent triển khai phần bổ sung của TrafficFlow.

Mục tiêu cuối cùng là biến TrafficFlow thành một dự án Computer Vision/AI Engineering có thể:

1. Đưa vào CV bằng các con số có bằng chứng.
2. Trình bày đầy đủ trên GitHub.
3. Giúp HR hiểu nhanh vấn đề, vai trò và kết quả.
4. Giúp technical interviewer kiểm tra sâu AI pipeline.
5. Phân biệt rõ thành quả của nhóm và phạm vi cá nhân.
6. Tái lập được benchmark từ config, split, raw prediction và run manifest.
7. Không phóng đại ownership hoặc accuracy.

Nhà tuyển dụng phải hiểu được các câu hỏi sau:

- TrafficFlow giải quyết vấn đề gì?
- Dự án nhóm gồm những phần nào?
- Ứng viên chịu trách nhiệm chính phần nào?
- Từ một frame đến một counting event đi qua những bước nào?
- Lane, direction và counting line được định nghĩa ra sao?
- Tracker giữ identity bằng cách nào?
- Model nào được thử và vì sao chọn model cuối?
- Detection, tracking, counting được benchmark như thế nào?
- Backend/runtime optimization đóng góp điều gì?
- Kết quả có tái lập và kiểm chứng được không?
- Hệ thống còn giới hạn gì?

---

# 1. HARD RULES — Coding Agent bắt buộc tuân thủ

> **Không tuân thủ một rule bên dưới thì phase không được đánh dấu PASS.**

## 1.1. Rule về phạm vi và ownership

1. Luôn tách ba phạm vi:
   - **Sản phẩm do nhóm xây dựng.**
   - **AI pipeline do ứng viên phụ trách chính.**
   - **Live runtime optimization là phần ứng viên phân tích/đóng góp/kiểm chứng cùng nhóm.**
2. Không được viết rằng ứng viên một mình xây toàn bộ full-stack hoặc toàn bộ end-to-end product.
3. Chỉ dùng các từ `designed`, `implemented`, `owned`, `evaluated` đối với phần ứng viên thực sự có thể giải thích và bảo vệ:
   - ROI processing.
   - Detection integration/model evaluation.
   - Pre-tracker filtering.
   - Tracking.
   - Lane association.
   - Direction validation.
   - Counting logic.
   - Derived GT.
   - AI benchmark.
4. Với phần shared contribution, phải dùng cách diễn đạt như:
   - `contributed to`
   - `collaborated on`
   - `led the analysis of`
   - `helped validate`
5. Không thực hiện refactor frontend, database, authentication, storage hoặc hạ tầng không liên quan trực tiếp đến:
   - AI pipeline.
   - AI contracts.
   - Benchmark.
   - AI runtime instrumentation.
6. Nếu cần chỉnh backend để đo AI runtime, phải ghi rõ đó là instrumentation/integration support, không biến nó thành claim full-stack ownership.

## 1.2. Rule về tính trung thực của benchmark

1. **Cấm tự tạo hoặc ước lượng metric không được đo.**
2. Không được suy ra kết quả cuối từ một vài log tức thời.
3. Mọi metric phải truy ngược được đến:
   - Run ID.
   - Git commit.
   - Dataset split.
   - Frozen config.
   - Raw prediction.
   - File summary/report.
4. Không được gọi một kết quả là `held-out test` nếu video đó từng được dùng để tuning.
5. **Cấm random split theo frame.**
6. Đơn vị split nhỏ nhất là một sequence/video hoàn chỉnh.
7. Nếu xác định được camera/scene, ưu tiên group split theo camera/scene.
8. Không tune model, threshold, tracker, counting rule hoặc geometry dựa trên kết quả test.
9. Geometry được phép khác nhau theo camera, nhưng phải freeze trước khi chấm prediction.
10. Không di chuyển counting line sau khi xem prediction test nhằm làm metric đẹp hơn.
11. Phải kiểm tra class label thật trong UA-DETRAC parser trước khi tạo class mapping.
12. Không báo cáo motorcycle accuracy từ UA-DETRAC nếu source annotation không có class tương thích.
13. Counting GT tạo từ UA-DETRAC phải được gọi rõ:

```text
derived task-specific counting ground truth
```

14. Code sinh GT và code sinh prediction event không được phụ thuộc mù quáng vào cùng một nhánh logic mà không có kiểm chứng độc lập.
15. Phải audit thủ công một mẫu derived GT trước khi dùng làm benchmark.
16. Không dùng một mình aggregate count error vì miss và duplicate có thể triệt tiêu nhau.
17. Counting report bắt buộc có cả:
   - Event-level metrics.
   - Aggregate count metrics.

## 1.3. Rule về an toàn khi sửa code

1. Đọc code hiện tại trước khi sửa; tài liệu cũ có thể không còn đúng.
2. Không broad refactor trong lúc xây benchmark.
3. Mỗi phase chỉ thay đổi đúng phạm vi của phase đó.
4. Không xóa benchmark output cũ.
5. Không overwrite frozen split, frozen config hoặc final report.
6. Mọi run phải nằm trong thư mục versioned theo `run_id`.
7. Không dùng `git reset --hard`, force push hoặc rewrite history.
8. Không thay đổi API/schema mà chưa tìm toàn bộ reader và writer.
9. Mọi public schema mới phải có `schema_version`.
10. Mọi geometry phải khai báo coordinate space:

```text
source_frame
crop_local
model_input
```

11. Mọi benchmark phải lưu hardware/software metadata.
12. Khi so sánh model, các điều kiện còn lại phải giống nhau, trừ biến đang được nghiên cứu.
13. Một ablation chỉ được thay đổi một biến chính.
14. Một GPU mặc định chỉ dùng một inference process, trừ khi test chủ đích là GPU contention.
15. Phải warm up model trước khi đo steady-state latency.
16. Secrets, cookie, API key, credential và private model không được đưa vào report hoặc commit.

## 1.4. Rule về validation

Trước khi kết thúc một phase, Agent phải chạy các lệnh phù hợp:

```bash
python -m pytest tests -q
python -m compileall -q src benchmark
git diff --check
```

Nếu đụng frontend:

```bash
npm --prefix frontend run build
```

Nếu đụng Docker/runtime config:

```bash
docker compose config
```

Quy tắc:

- Validation fail thì phase không được `PASS`.
- Không được giấu failed test bằng cách chỉ báo cáo phần pass.
- Test bị skip phải nêu lý do.
- Test phụ thuộc GPU/dataset phải ghi rõ môi trường đã dùng.

## 1.5. Rule về báo cáo và STOP GATE

1. Agent **phải dừng sau mỗi phase**.
2. Agent phải tạo report tại:

```text
docs/reports/phase-XX-<phase-name>.md
```

3. Agent phải báo cáo lại cho người dùng bằng tiếng Việt.
4. Agent không được tự chuyển sang phase tiếp theo nếu chưa có xác nhận của người dùng.
5. Mỗi report bắt buộc có:
   - Status: `PASS`, `PARTIAL`, `BLOCKED`.
   - Mục tiêu.
   - Phạm vi đã hoàn thành.
   - File tạo mới.
   - File sửa đổi.
   - Command đã chạy.
   - Kết quả test chính xác.
   - Metric và Run ID.
   - Quyết định kỹ thuật.
   - Known limitations.
   - Risks.
   - Nội dung cần người dùng review.
   - Đề xuất phase tiếp theo.
6. Nếu bị block, phải ghi đúng blocker và dừng.
7. Không được dùng câu chung chung như “đã tối ưu” nếu chưa có before/after metric.

---

# 2. Output cuối cùng phải có

## 2.1. Bộ tài liệu về vai trò và AI pipeline

```text
docs/portfolio/
├── project-scope-and-ownership.md
├── recruiter-overview.md
├── ai-pipeline.md
├── lane-geometry-and-counting.md
├── tracking-design.md
├── benchmark-methodology.md
├── runtime-optimization-case-study.md
├── error-analysis.md
├── limitations.md
├── release-checklist.md
└── cv/
    ├── trafficflow-cv-bullets.md
    ├── trafficflow-interview-answers.md
    └── trafficflow-evidence-map.md
```

## 2.2. Bộ benchmark có thể tái lập

```text
benchmark/
├── README.md
├── schemas/
│   ├── benchmark_manifest.schema.json
│   ├── counting_event.schema.json
│   └── run_summary.schema.json
├── baseline/
│   ├── current_defaults.yaml
│   ├── environment.json
│   └── model_inventory.json
├── splits/
│   └── ua_detrac_split_v1.json
├── configs/
│   ├── benchmark_protocol_v1.yaml
│   ├── class_mapping_v1.yaml
│   ├── model_matrix_v1.yaml
│   ├── runs/
│   └── geometry/
├── ground_truth/
│   ├── derived_events/
│   ├── counts/
│   └── audit/
├── predictions/
│   ├── detection/
│   ├── tracking/
│   └── counting/
├── runs/
│   └── <run_id>/
│       ├── manifest.json
│       ├── config_snapshot.yaml
│       ├── environment.json
│       ├── raw_metrics.json
│       ├── summary.json
│       ├── summary.csv
│       └── report.md
└── reports/
    ├── detection_report.md
    ├── tracking_report.md
    ├── counting_report.md
    ├── batch_runtime_report.md
    ├── live_runtime_report.md
    ├── ablation_report.md
    └── final_portfolio_report.md
```

## 2.3. Output GitHub

Root `README.md` cuối cùng phải có:

1. Một câu mô tả vấn đề.
2. Demo image/video placeholder.
3. Key results table.
4. Team scope.
5. `My contribution`.
6. AI pipeline diagram.
7. Lane/tracking/counting design.
8. Benchmark protocol.
9. Detection/tracking/counting results.
10. Uploaded-video runtime results.
11. Live runtime case study.
12. Error analysis.
13. Limitations.
14. Reproduction commands.
15. Team attribution.

## 2.4. Output CV

CV chỉ dùng metric đã có evidence. Mỗi claim phải có mapping:

| CV claim | Evidence file | Run ID | Raw source |
|---|---|---|---|
| HOTA/IDF1 | tracking report | ... | TrackEval output |
| Event F1/WAPE | counting report | ... | event match CSV |
| Upload FPS/RTF | batch runtime report | ... | run summary |
| Live 15 FPS | live soak report | ... | timeseries CSV |

Không có evidence row thì không được đưa số vào CV.

---

# 3. Câu chuyện cuối cùng cần kể

README, CV và phỏng vấn phải thống nhất theo thứ tự:

```text
Problem
→ Team product
→ My responsibility
→ AI pipeline
→ Lane/counting semantics
→ Tracking design
→ Benchmark protocol
→ Quantitative results
→ Runtime optimization
→ Error analysis
→ Limitations
→ Reproducibility
```

Định vị cá nhân chuẩn:

> AI Pipeline Engineer trong nhóm 5 thành viên, phụ trách chính computer vision, tracking, lane-level counting và evaluation; đồng thời đóng góp vào phân tích và kiểm chứng tối ưu live inference runtime.

---

# 4. Kế hoạch triển khai theo phase

---

## Phase 00 — Audit repository và freeze baseline

### Mục tiêu

Xác định trạng thái thật của source code trước khi bổ sung benchmark hoặc claim mới.

### Việc cần làm

1. Kiểm tra code path hiện tại của:
   - Upload video processing.
   - Live/HLS processing.
   - Model loading.
   - ROI/crop/coordinate transforms.
   - Pre-tracker filtering.
   - Tracker.
   - Lane association.
   - Counting event.
   - Renderer.
   - Runtime metrics.
2. So sánh code hiện tại với README/docs cũ.
3. Liệt kê conflict hoặc nội dung stale.
4. Ghi model hiện có và SHA256.
5. Ghi default config thật từ code/env.
6. Ghi GPU, CUDA, Python, PyTorch, Ultralytics, OpenCV.
7. Chạy toàn bộ test baseline.
8. Viết ownership matrix.
9. Không thay đổi behavior của production trong phase này.

### Output bắt buộc

```text
docs/reports/phase-00-repository-audit.md
docs/portfolio/project-scope-and-ownership.md
benchmark/baseline/current_defaults.yaml
benchmark/baseline/environment.json
benchmark/baseline/model_inventory.json
```

### Ownership matrix tối thiểu

| Module | Vai trò cá nhân | Vai trò nhóm | Evidence |
|---|---|---|---|
| ROI processing | Primary owner | Integration shared | source/tests |
| Lane geometry | Primary owner | UI editor shared | source/tests |
| Detection | Primary owner | — | source/benchmark |
| Tracking | Primary owner | — | source/tests |
| Counting | Primary owner | — | source/tests |
| Evaluation | Primary owner | QA hỗ trợ | benchmark |
| Live profiling | Analysis/validation lead | implementation shared | log/tests |
| Frontend | Không phải primary owner | team | — |
| General backend | Không phải primary owner | team | — |

### Acceptance criteria

- [ ] Code path map đầy đủ.
- [ ] Test baseline được lưu.
- [ ] Model inventory được tạo.
- [ ] Ownership rõ ràng và không phóng đại.
- [ ] Không thay đổi production behavior.

### STOP GATE

Tạo report, báo cáo người dùng và dừng.

---

## Phase 01 — Thiết kế benchmark protocol và dataset split

### Mục tiêu

Freeze quy trình đánh giá trước khi tuning.

### Việc cần làm

1. Inventory toàn bộ UA-DETRAC sequences đang có.
2. Parse metadata:
   - Sequence name.
   - Frame count.
   - FPS.
   - Resolution.
   - Số GT tracks.
   - Class distribution.
   - Camera/scene metadata nếu có.
   - Weather/traffic condition nếu có.
3. Chia:
   - `development`
   - `held_out_test`
   - optional `smoke_test`
4. Split theo full sequence.
5. Group theo camera/scene khi có dữ liệu.
6. Freeze class mapping.
7. Freeze counting-event matching tolerance.
8. Freeze metric definitions.
9. Freeze runtime measurement protocol.

### Quy mô khuyến nghị

Tối thiểu:

```text
Development: 3–5 sequences
Held-out test: ít nhất 3 sequences
```

Tốt hơn:

```text
Development: 5–8 sequences
Held-out test: 3–5 sequences
Có nhiều camera và traffic conditions
```

### File protocol bắt buộc

```yaml
protocol_version: 1
split_file: benchmark/splits/ua_detrac_split_v1.json
split_unit: full_sequence
random_frame_split: forbidden
geometry_policy: per_sequence_frozen_before_prediction_scoring
class_mapping_file: benchmark/configs/class_mapping_v1.yaml
counting_event_match:
  same_video: true
  same_lane: true
  same_direction: true
  class_policy: exact_or_documented_mapping
  temporal_tolerance_frames: 5
  spatial_tolerance_pixels: null
tracking:
  evaluator: TrackEval
  primary_metrics:
    - HOTA
    - DetA
    - AssA
    - IDF1
    - IDSW
    - Frag
counting:
  primary_metrics:
    - event_precision
    - event_recall
    - event_f1
    - WAPE
    - signed_bias
runtime:
  warmup_frames: 30
  timing_window: steady_state
  percentiles: [p50, p95, p99]
```

### Output bắt buộc

```text
benchmark/splits/ua_detrac_split_v1.json
benchmark/configs/benchmark_protocol_v1.yaml
benchmark/configs/class_mapping_v1.yaml
docs/portfolio/benchmark-methodology.md
docs/reports/phase-01-benchmark-protocol.md
```

### Acceptance criteria

- [ ] Không random split theo frame.
- [ ] Test split đã freeze.
- [ ] Class mapping khớp annotation thật.
- [ ] Metric được định nghĩa trước test.
- [ ] Test không dùng để tuning sau phase này.

### STOP GATE

Tạo report, báo cáo người dùng và dừng.

---

## Phase 02 — Geometry config và derived counting GT

### Mục tiêu

Dùng GT bbox/class/track ID của UA-DETRAC cùng geometry do ứng viên cấu hình để sinh lane-level counting ground truth.

### Pipeline GT

```text
UA-DETRAC GT tracks
+ ROI
+ lane valid zones
+ counting lines
+ direction vectors
→ derived crossing events
→ per-lane/per-class counts
```

### Việc cần làm

1. Tạo hoặc validate geometry cho từng sequence:
   - `annotation_roi`
   - `processing_roi`
   - `geometry_space`
   - lane polygon/valid zone
   - counting line
   - direction vector
2. Freeze geometry version trước khi chấm prediction.
3. Tạo GT event generator từ GT track ID.
4. Dùng bottom-center anchor:

```text
anchor_t = ((x1_t + x2_t) / 2, y2_t)
```

5. Crossing event phải kiểm tra:
   - Anchor trước và sau.
   - Signed side change đối với counting line.
   - Segment intersection.
   - Lane membership.
   - Direction alignment.
   - Dedup theo track/lane.
6. Xuất một JSONL record cho mỗi event.
7. Aggregate theo:
   - video
   - lane
   - class
   - direction
8. Audit thủ công tối thiểu:
   - 30–50 events, hoặc
   - 5% events,
   lấy mức phù hợp nhưng phải đủ đại diện.
9. Báo cáo lỗi của GT generator nếu phát hiện.

### Counting event schema

```json
{
  "schema_version": 1,
  "video_id": "MVI_20011",
  "gt_track_id": 42,
  "class_name": "car",
  "lane_id": "lane_1",
  "direction": "forward",
  "crossing_frame": 316,
  "crossing_time_s": 12.64,
  "crossing_point": [520.4, 361.8],
  "geometry_version": "MVI_20011-v1"
}
```

### Output bắt buộc

```text
benchmark/configs/geometry/<sequence>.json
benchmark/ground_truth/derived_events/<sequence>.jsonl
benchmark/ground_truth/counts/<sequence>.csv
benchmark/ground_truth/audit/audit_sample.csv
benchmark/ground_truth/audit/audit_report.md
docs/portfolio/lane-geometry-and-counting.md
docs/reports/phase-02-derived-ground-truth.md
```

### Acceptance criteria

- [ ] Geometry khai báo coordinate space.
- [ ] Point nằm trong processing frame.
- [ ] Mỗi event có geometry version.
- [ ] Không duplicate event ngoài protocol.
- [ ] Tổng count bằng số accepted GT events.
- [ ] Audit đã được thực hiện.
- [ ] Geometry test không chỉnh theo prediction.

### STOP GATE

Tạo report, báo cáo người dùng và dừng.

---

## Phase 03 — Unified benchmark runner và run manifest

### Mục tiêu

Tạo một entry point tái lập được cho detection, tracking, counting và runtime benchmark của upload video.

### Runner phải nhận

```text
protocol
split
sequence list
model
imgsz
confidence
iou
tracker config
counting config
geometry directory
output directory
```

### Command mục tiêu

```bash
python -m benchmark.run \
  --protocol benchmark/configs/benchmark_protocol_v1.yaml \
  --split development \
  --model models/yolo11m.pt \
  --config benchmark/configs/runs/yolo11m_640.yaml \
  --output benchmark/runs/<run_id>
```

### Runner bắt buộc lưu

- Raw detections.
- Raw tracks.
- Raw counting events.
- Stage timings.
- Resource samples.
- Config snapshot.
- Environment metadata.
- Model checksum.
- Git commit.
- Summary JSON/CSV/Markdown.

### Run manifest mẫu

```json
{
  "schema_version": 1,
  "run_id": "20260717-yolo11m-640-dev-001",
  "git_commit": "...",
  "dataset_split": "ua_detrac_split_v1",
  "protocol_version": 1,
  "model_path": "models/yolo11m.pt",
  "model_sha256": "...",
  "imgsz": 640,
  "confidence": 0.4,
  "iou": 0.45,
  "tracker_config": "...",
  "counting_config": "...",
  "geometry_versions": {},
  "device": "cuda:0",
  "gpu": "...",
  "software": {},
  "started_at": "...",
  "completed_at": "..."
}
```

### Output bắt buộc

```text
benchmark/run.py
benchmark/schemas/benchmark_manifest.schema.json
benchmark/schemas/run_summary.schema.json
benchmark/README.md
benchmark/runs/<smoke_run_id>/...
docs/reports/phase-03-benchmark-runner.md
```

### Acceptance criteria

- [ ] Smoke sequence chạy end-to-end.
- [ ] Raw outputs được giữ.
- [ ] Run tái lập được từ manifest.
- [ ] Không overwrite run ID.
- [ ] Invalid geometry/model/schema làm command fail rõ ràng.
- [ ] Không bắt buộc đi qua frontend để benchmark.

### STOP GATE

Tạo report, báo cáo người dùng và dừng.

---

## Phase 04 — Detection benchmark và model selection

### Mục tiêu

Đo chất lượng detector độc lập để biết lỗi downstream bắt đầu từ detection hay tracker/counting.

### Model candidates

Chỉ dùng model thực sự tồn tại hoặc đã được người dùng cho phép tải:

```text
yolo11m.pt
yolov8n.pt
yolov8s.pt
yolov8m.pt
```

### Metrics bắt buộc

```text
AP50
AP50–95
Precision
Recall
F1 tại operating threshold
Per-class AP
Per-class Recall
False positives/frame
False negatives/frame
Inference latency p50/p95
Peak VRAM
```

### Thí nghiệm

1. Baseline tại frozen config.
2. Model comparison cùng điều kiện.
3. Optional imgsz trade-off.
4. Optional full-frame vs crop-ROI ablation.
5. Chọn model trên development.
6. Freeze model/config.
7. Chạy held-out test một lần.

### Output bắt buộc

```text
benchmark/predictions/detection/<run_id>/
benchmark/reports/detection_report.md
benchmark/reports/detection_summary.csv
benchmark/reports/model_selection.md
docs/reports/phase-04-detection-benchmark.md
```

### Bảng report bắt buộc

| Model | Imgsz | Precision | Recall | AP50 | AP50-95 | Infer p95 | VRAM |
|---|---:|---:|---:|---:|---:|---:|---:|

### Acceptance criteria

- [ ] Development và held-out result tách rõ.
- [ ] Model được chọn theo accuracy-speed trade-off.
- [ ] Per-class weakness được phân tích.
- [ ] Không claim class không có GT.
- [ ] Mọi result có run ID.

### STOP GATE

Tạo report, báo cáo người dùng và dừng.

---

## Phase 05 — Tracking benchmark

### Mục tiêu

Đánh giá khả năng giữ đúng identity của phương tiện qua thời gian.

### Metrics chính

```text
HOTA
DetA
AssA
IDF1
ID switches
Fragmentations
```

### Metrics phụ

```text
MOTA
MOTP hoặc LocA
Mostly Tracked
Mostly Lost
```

### Việc cần làm

1. Convert GT/prediction sang format evaluator hỗ trợ.
2. Dùng TrackEval hoặc evaluator chính thống có version ghi rõ.
3. Validate:
   - Frame numbering.
   - Bbox format.
   - Class mapping.
   - Track ID.
4. Chạy baseline tracker.
5. Tuning trên development.
6. Freeze tracker params.
7. Chạy held-out test.
8. So sánh nếu tái lập được:

```text
IoU-only + frame-based lifetime
vs.
timestamp-aware Kalman + Hungarian/combined association + time TTL
```

### Tracker config phải freeze

```text
state model
association cost weights
IoU gate
center-distance gate
class consistency
min_hits
max_lost_seconds
reset_gap_seconds
```

### Output bắt buộc

```text
benchmark/predictions/tracking/<run_id>/
benchmark/reports/tracking_report.md
benchmark/reports/tracking_summary.csv
benchmark/reports/tracking_ablation.csv
docs/portfolio/tracking-design.md
docs/reports/phase-05-tracking-benchmark.md
```

### Bảng report bắt buộc

| Tracker | HOTA | DetA | AssA | IDF1 | IDSW | Frag |
|---|---:|---:|---:|---:|---:|---:|

### Acceptance criteria

- [ ] Evaluator/version được ghi.
- [ ] Conversion được kiểm tra bằng sample.
- [ ] Test metric không dùng để tuning.
- [ ] Có ví dụ ID switch/fragmentation.
- [ ] Có phân tích detection error hay association error.

### STOP GATE

Tạo report, báo cáo người dùng và dừng.

---

## Phase 06 — Counting benchmark

### Mục tiêu

Đo đúng task chính: đếm phương tiện theo lane/class/direction.

## 06A. Event-level metrics

Bắt buộc:

```text
Event Precision
Event Recall
Event F1
Missed crossing rate
False crossing rate
Duplicate count rate
Wrong-lane rate
Wrong-class rate
Wrong-direction rate
Crossing-time error median/p95
```

### Event matching rule

Một prediction chỉ được match một GT event khi:

```text
cùng video
cùng lane
cùng direction
class tương thích theo protocol
nằm trong temporal tolerance
optional spatial tolerance
```

Dùng one-to-one matching; Hungarian được ưu tiên khi nhiều event gần nhau.

## 06B. Aggregate metrics

Bắt buộc:

```text
MAE
RMSE
WAPE
Signed Bias
Exact-count accuracy
Within-1 accuracy
```

Evaluation unit:

```text
video × lane × class × direction
```

Không dùng MAPE làm headline metric vì có nhiều GT count bằng 0.

### Việc cần làm

1. Sinh prediction event JSONL.
2. Match GT-pred events.
3. Xuất TP/FP/FN records.
4. Aggregate theo video/lane/class/direction.
5. Breakdown overall/per-video/per-lane/per-class.
6. Kiểm tra consistency:

```text
reported total count
= sum per-lane/per-class counts
= number of accepted prediction events
```

### Output bắt buộc

```text
benchmark/predictions/counting/<run_id>/events.jsonl
benchmark/reports/counting_report.md
benchmark/reports/counting_summary.csv
benchmark/reports/counting_event_matches.csv
benchmark/reports/counting_errors.csv
docs/reports/phase-06-counting-benchmark.md
```

### Bảng report bắt buộc

| Scope | Event P | Event R | Event F1 | WAPE | Bias | Duplicate rate | Miss rate |
|---|---:|---:|---:|---:|---:|---:|---:|

### Acceptance criteria

- [ ] Có event-level và aggregate metrics.
- [ ] Duplicate và missed events không bị tổng count che giấu.
- [ ] Wrong-lane và wrong-direction tách riêng.
- [ ] Summary truy ngược được đến event match CSV.
- [ ] Held-out metrics được đánh dấu rõ.

### STOP GATE

Tạo report, báo cáo người dùng và dừng.

---

## Phase 07 — Uploaded-video AI runtime benchmark

### Mục tiêu

Đo hiệu năng toàn AI path của video upload, không nhận ownership cho các tầng platform không thuộc phạm vi cá nhân.

### Phạm vi timing

```text
decode
→ ROI/crop/resize
→ inference
→ tracking
→ counting
→ rendering
→ encoding
```

### Metrics bắt buộc

```text
Processed FPS
Real-time factor
End-to-end AI task time
Decode latency p50/p95
Preprocess latency p50/p95
Inference latency p50/p95
Tracking latency p50/p95
Counting latency p50/p95
Render latency p50/p95
Encode latency p50/p95
Peak VRAM
GPU utilization avg/p95
CPU utilization avg/p95
Peak RAM
```

### Test matrix tối thiểu

```text
Short video: 30–60 giây
Medium video: 3–5 phút
Long video: 10+ phút nếu có
```

Ít nhất hai resolution khi có thể:

```text
960×540 hoặc 720p
1080p
```

### Định nghĩa

```text
Processed FPS = processed frames / processing seconds
Real-time factor = source duration / processing duration
```

`RTF > 1` nghĩa là xử lý nhanh hơn real time.

### Output bắt buộc

```text
benchmark/reports/batch_runtime_report.md
benchmark/reports/batch_runtime_summary.csv
benchmark/reports/stage_latency.csv
benchmark/reports/resource_usage.csv
docs/reports/phase-07-upload-runtime.md
```

### Acceptance criteria

- [ ] Warmup tách khỏi steady-state hoặc báo riêng.
- [ ] Input resolution/duration/frame count được lưu.
- [ ] FPS là toàn AI path, không phải riêng YOLO.
- [ ] Có resource sampling.
- [ ] Mỗi result có run manifest.

### STOP GATE

Tạo report, báo cáo người dùng và dừng.

---

## Phase 08 — Live/HLS AI runtime và stability benchmark

### Mục tiêu

Cung cấp bằng chứng thứ cấp cho đóng góp phân tích/kiểm chứng tối ưu live AI runtime.

### Ownership wording bắt buộc

> Ứng viên phụ trách hoặc dẫn dắt phân tích bottleneck và validation của AI runtime; việc tích hợp live platform là đóng góp chung của nhóm.

### Metrics bắt buộc

```text
Processed FPS
Published FPS
Frame interarrival p50/p95/p99
Frame age p50/p95/p99
Dropped-frame ratio
Stale-frame ratio
Inference wall p50/p95/p99
Time to first inferred frame
Reconnect count
Reconnect duration
Stall count/hour
Total stall duration
Unexpected tracker reset count
Session error count
Peak VRAM
GPU utilization
RAM growth over time
```

### Test protocol

1. Dùng source cố định khi có thể.
2. Ghi source type, resolution, source FPS.
3. Warmup trước steady-state summary.
4. Soak test:

```text
Minimum: 30 phút
Preferred: 60 phút
```

5. Sample mỗi 5–10 giây.
6. Lưu raw timeseries CSV.
7. Ghi client connection state.
8. Ghi network/source interruption nếu có.

### Historical baseline

Có thể lưu làm lịch sử:

```text
Trước: khoảng 2–4 FPS, nhiều frame drop, scheduling không ổn định
Sau: khoảng 15 FPS dưới input cap 15 FPS, frame age rất thấp, final sample không drop
```

Nhưng CV chỉ được dùng số sau khi formal soak test hoàn tất.

### Output bắt buộc

```text
benchmark/reports/live_runtime_report.md
benchmark/reports/live_runtime_timeseries.csv
benchmark/reports/live_resource_timeseries.csv
docs/portfolio/runtime-optimization-case-study.md
docs/reports/phase-08-live-runtime.md
```

### Acceptance criteria

- [ ] Mọi stability claim có test duration.
- [ ] Có p95/p99/max, không chỉ average.
- [ ] Runtime metric tách khỏi accuracy metric.
- [ ] Shared ownership wording được giữ.
- [ ] Timeseries được lưu.

### STOP GATE

Tạo report, báo cáo người dùng và dừng.

---

## Phase 09 — Ablation studies và error analysis

### Mục tiêu

Chứng minh các quyết định kỹ thuật có tác dụng và ứng viên hiểu failure modes.

## Ablation bắt buộc

### A. Tracker

```text
IoU-only/frame-based timeout
vs.
timestamp-aware Kalman + combined association + time TTL
```

Metrics:

```text
HOTA
IDF1
ID switches
Fragmentations
Event F1
Duplicate count rate
```

### B. ROI strategy

```text
full-frame inference
vs.
crop-ROI inference
```

Metrics:

```text
AP/Recall
Processed FPS
Event F1
WAPE
```

### C. Live scheduling

```text
pending-future/bursty scheduling
vs.
realtime pacing + latest-frame + dedicated inference loop
```

Metrics:

```text
Processed FPS
Drop rate
Frame age p95
Inference idle ratio
```

## Error taxonomy

Bắt buộc phân loại tối thiểu:

```text
missed small vehicle
heavy occlusion
class confusion
ID switch
track fragmentation
wrong lane
wrong direction
duplicate crossing
missed crossing
early/late crossing
geometry mismatch
coordinate-space error
```

### Việc cần làm

1. Tạo bảng số lượng/tỷ lệ lỗi.
2. Lưu sequence/frame/track ID.
3. Lưu representative frame hoặc clip.
4. Xác định lỗi bắt nguồn từ:
   - Detection.
   - Tracking/association.
   - Lane geometry.
   - Counting logic.
   - Runtime scheduling.
5. Ghi fixable vs inherent limitation.
6. Không cherry-pick case tốt để đại diện tổng thể.

### Output bắt buộc

```text
benchmark/reports/ablation_report.md
benchmark/reports/ablation_summary.csv
docs/portfolio/error-analysis.md
docs/portfolio/limitations.md
docs/reports/phase-09-ablation-error-analysis.md
```

### Acceptance criteria

- [ ] Hoàn tất ba ablations hoặc ghi blocker cụ thể.
- [ ] Error examples truy ngược được.
- [ ] Limitation cụ thể.
- [ ] Negative finding không bị che giấu.

### STOP GATE

Tạo report, báo cáo người dùng và dừng.

---

## Phase 10 — Hoàn thiện GitHub documentation

### Mục tiêu

Biến output kỹ thuật thành một repository mà recruiter và interviewer đều đọc được.

### README structure bắt buộc

```text
1. Project title + one-sentence problem
2. Demo image/video placeholder
3. Key results
4. What the team built
5. My contribution
6. AI pipeline
7. Lane/tracking/counting design
8. Benchmark methodology
9. Detection/tracking/counting results
10. Uploaded-video runtime
11. Live runtime case study
12. Error analysis
13. Limitations
14. Architecture
15. Reproduction
16. Team attribution
```

### Recruiter key-results table

| Category | Metric | Result | Evidence |
|---|---|---:|---|
| Detection | AP50 / Recall | TBD | detection report |
| Tracking | HOTA / IDF1 / IDSW | TBD | tracking report |
| Counting | Event F1 / WAPE | TBD | counting report |
| Upload runtime | FPS / RTF | TBD | batch runtime report |
| Live runtime | FPS / frame age p95 / drop rate | TBD | soak report |

### Rule trình bày

1. Bắt đầu bằng problem, không bắt đầu bằng tech stack.
2. Tách team result và personal contribution.
3. Giải thích vì sao YOLO chưa đủ.
4. Show pipeline:

```text
Frame
→ ROI
→ Detector
→ Filter
→ Tracker
→ Lane association
→ Direction validation
→ Crossing event
→ Count
```

5. Có before/after table.
6. Có benchmark protocol.
7. Có limitation.
8. Có reproduction command.
9. Không upload data vi phạm license.
10. Không đưa model weight/private credential lên repo.

### Output bắt buộc

```text
README.md
docs/portfolio/recruiter-overview.md
docs/portfolio/ai-pipeline.md
docs/portfolio/runtime-optimization-case-study.md
docs/reports/phase-10-github-documentation.md
```

### Acceptance criteria

- [ ] Recruiter hiểu contribution trong dưới một phút.
- [ ] Technical interviewer truy metric được.
- [ ] README không còn stale architecture.
- [ ] Setup không phụ thuộc undocumented local state.
- [ ] Không có inflated ownership.

### STOP GATE

Tạo report, báo cáo người dùng và dừng.

---

## Phase 11 — CV và interview package

### Mục tiêu

Chuyển benchmark thành các bullet ngắn, có bằng chứng và có thể vấn đáp.

### CV rule

1. Project title nên ghi:

```text
TrafficFlow — Computer Vision & AI Pipeline | Team of 5
```

2. Tối đa bốn bullets.
3. Mỗi bullet chỉ nên có một vai trò chính:
   - Scope/ownership.
   - AI quality.
   - Model/runtime trade-off.
   - Shared live-runtime improvement.
4. Không dùng full-stack ownership wording.
5. Chỉ dùng số đã đo.
6. Mọi số phải có evidence map.

### CV bullet template

#### Bullet 1 — Scope

> Owned the computer-vision pipeline for lane-level traffic analytics, covering ROI processing, YOLO-based detection, pre-tracker filtering, multi-object tracking, lane association, direction validation, and line-crossing counting in a five-member team project.

#### Bullet 2 — AI quality

> Evaluated the pipeline on held-out UA-DETRAC sequences using derived lane-crossing ground truth, achieving **[HOTA] HOTA, [IDF1] IDF1, [Event F1] event-level counting F1, and [WAPE]% WAPE**.

#### Bullet 3 — Model/runtime trade-off

> Benchmarked **[models/configurations]** and selected **[final model]** for the best accuracy-throughput trade-off, processing uploaded videos at **[FPS] FPS / [RTF]× real time** with **[VRAM] GB peak VRAM**.

#### Bullet 4 — Shared live-runtime contribution

> Led the diagnosis and validation of live AI-runtime improvements, helping increase YouTube/HLS processing from **[old FPS]** to **[new FPS]**, with **[drop rate]% frame drops** and **[frame age p95] ms p95 frame age** during a **[duration]-minute** soak test.

### Interview topics bắt buộc chuẩn bị

```text
Project problem
Team size and ownership
Input-to-count pipeline
ROI coordinate spaces
Lane semantics
Bottom-center anchor
Counting line crossing
Direction vector
Lane lock
Duplicate prevention
Kalman state
Timestamp-aware dt
Hungarian association
Track lifecycle
Derived GT
Sequence split
HOTA/IDF1
Event F1/WAPE
Model selection
Runtime profiling
Live scheduling problem
Failure cases
Limitations
AI-assisted development
Next improvements
```

### Cách nói về AI coding assistance

Không cần đưa vào CV. Khi được hỏi trực tiếp, trả lời:

> AI được dùng để hỗ trợ phân tích lỗi, thảo luận phương án, review và tăng tốc một phần implementation. Tôi chịu trách nhiệm xác định vấn đề, lựa chọn giải pháp, kiểm tra source code, viết/chạy test, benchmark, tích hợp và chỉ giữ lại những thay đổi tôi có thể giải thích.

### Output bắt buộc

```text
docs/portfolio/cv/trafficflow-cv-bullets.md
docs/portfolio/cv/trafficflow-interview-answers.md
docs/portfolio/cv/trafficflow-evidence-map.md
docs/reports/phase-11-cv-interview-package.md
```

### Acceptance criteria

- [ ] Mọi metric có evidence.
- [ ] Team/personal scope rõ.
- [ ] Không claim full-stack.
- [ ] Ứng viên giải thích được mọi technical claim.
- [ ] AI assistance được mô tả trung thực.

### STOP GATE

Tạo report, báo cáo người dùng và dừng.

---

## Phase 12 — Final review và release gate

### Mục tiêu

Kiểm tra consistency, reproducibility và recruiter readiness.

## Scientific validity checklist

- [ ] Split theo sequence, không theo frame.
- [ ] Test không dùng để tuning.
- [ ] Geometry freeze trước test scoring.
- [ ] Derived GT có audit.
- [ ] Counting có event-level và aggregate metrics.
- [ ] Tracking có association metrics.
- [ ] Runtime tách model latency và pipeline throughput.

## Engineering checklist

- [ ] Tests pass.
- [ ] Benchmark chạy lại được từ command/manifest.
- [ ] Raw predictions còn nguyên.
- [ ] Reports có run ID.
- [ ] Không lộ secret/private data.
- [ ] Documentation khớp code.

## Ownership checklist

- [ ] Team size được ghi.
- [ ] AI pipeline ownership rõ.
- [ ] Live runtime ghi shared contribution đúng mức.
- [ ] Không nhận full-stack ownership.

## Recruiter checklist

- [ ] README có short project explanation.
- [ ] README có key-results table.
- [ ] README có `My contribution`.
- [ ] Có demo link placeholder.
- [ ] Có GitHub link placeholder trong CV draft.
- [ ] CV không có unsupported metric.
- [ ] Limitations được trình bày.

### Output bắt buộc

```text
benchmark/reports/final_portfolio_report.md
docs/reports/phase-12-final-review.md
docs/portfolio/release-checklist.md
```

### Final status hợp lệ

```text
READY_FOR_CV
READY_FOR_GITHUB
READY_FOR_TECHNICAL_INTERVIEW
```

Chỉ cấp status khi evidence tương ứng đã có.

---

# 5. Metric definitions cần chuẩn hóa

## 5.1. Detection

```text
Precision = TP / (TP + FP)
Recall = TP / (TP + FN)
F1 = 2 × Precision × Recall / (Precision + Recall)
```

AP50 và AP50–95 phải dùng evaluator được ghi version.

## 5.2. Tracking

Ưu tiên dùng evaluator chính thống cho:

```text
HOTA
DetA
AssA
IDF1
ID switches
Fragmentations
```

Không tự viết lại metric nếu chưa thật sự cần và chưa validate.

## 5.3. Counting event

```text
Event Precision = matched predicted events / all predicted events
Event Recall = matched GT events / all GT events
Event F1 = harmonic mean của Event Precision và Event Recall
```

## 5.4. Aggregate counting

Với unit `u = video × lane × class × direction`:

```text
MAE = mean(|Pred_u - GT_u|)
RMSE = sqrt(mean((Pred_u - GT_u)^2))
WAPE = sum(|Pred_u - GT_u|) / sum(GT_u)
Signed Bias = sum(Pred_u - GT_u) / sum(GT_u)
```

## 5.5. Uploaded-video runtime

```text
Processed FPS = processed frames / processing seconds
Real-time factor = source video duration / processing duration
```

## 5.6. Live runtime

```text
Dropped-frame ratio = dropped frames / frames read
Stale-frame ratio = stale frames / frames read
Frame age = inference start timestamp - frame reader/capture timestamp
```

`Published FPS` và `Processed FPS` phải tách riêng nếu khác nhau.

---

# 6. Mẫu report bắt buộc cho từng phase

Mỗi report phải theo cấu trúc sau:

````markdown
# Phase XX — <Tên phase>

## Status
PASS | PARTIAL | BLOCKED

## Mục tiêu
...

## Phạm vi đã hoàn thành
- ...

## File tạo mới
- ...

## File sửa đổi
- ...

## Commands đã chạy
```bash
...
```

## Kết quả validation
- pytest: ...
- compileall: ...
- frontend build: ...
- docker compose config: ...

## Metrics/results
| Metric | Value | Run ID | Evidence |
|---|---:|---|---|

## Quyết định kỹ thuật
- ...

## Known limitations
- ...

## Risks
- ...

## Nội dung cần người dùng review
- ...

## Phase tiếp theo được đề xuất
...
````

User-facing report không được giấu failed test, blocker hoặc uncertainty.

---

# 7. Thứ tự thực hiện bắt buộc

```text
Phase 00 — Audit và ownership
Phase 01 — Protocol và split
Phase 02 — Derived GT
Phase 03 — Benchmark runner
Phase 04 — Detection
Phase 05 — Tracking
Phase 06 — Counting
Phase 07 — Upload runtime
Phase 08 — Live runtime
Phase 09 — Ablation và error analysis
Phase 10 — GitHub documentation
Phase 11 — CV/interview package
Phase 12 — Final review
```

Không được viết CV bullet có metric trước khi các phase benchmark tương ứng hoàn tất.

---

# 8. Minimum viable portfolio completion

Nếu thời gian hạn chế, tối thiểu phải hoàn thành:

1. Phase 00.
2. Phase 01.
3. Phase 02 với GT audit.
4. Phase 03.
5. Detection benchmark.
6. Tracking benchmark.
7. Counting benchmark.
8. Upload runtime benchmark.
9. Live soak test 30 phút.
10. README và CV package.

Headline metrics tối thiểu:

```text
Detection:
- AP50
- Recall

Tracking:
- HOTA
- IDF1
- ID switches

Counting:
- Event F1
- WAPE
- Duplicate-count rate

Upload runtime:
- Processing FPS
- Real-time factor
- Peak VRAM

Live runtime:
- Stable processed FPS
- Frame age p95
- Dropped-frame ratio
- Test duration
```

---

# 9. Definition of Done cuối cùng

TrafficFlow chỉ được xem là sẵn sàng đưa vào CV/GitHub khi:

1. Vai trò cá nhân tách rõ khỏi thành quả nhóm.
2. AI pipeline được mô tả từ input đến count event.
3. Lane geometry và counting semantics rõ ràng.
4. Tracking architecture/lifecycle được giải thích.
5. UA-DETRAC split freeze theo sequence.
6. Derived counting GT được audit.
7. Detection/tracking/counting metrics có trên held-out videos.
8. Upload runtime đo toàn AI path.
9. Live runtime có formal soak test.
10. Có tracker, ROI và scheduling ablation.
11. Có failure cases và limitations.
12. Mọi CV claim truy được đến report/run ID.
13. README phục vụ được recruiter và interviewer.
14. Reproduction command đầy đủ.
15. Không có ownership hoặc accuracy claim phóng đại.

---

# 10. Hành động đầu tiên của Coding Agent

Agent chỉ được bắt đầu với **Phase 00**.

Agent chưa được implement benchmark trước khi hoàn thành và báo cáo đầy đủ:

```text
Repository audit
Current code-path map
Ownership matrix
Existing test baseline
Model inventory
Environment snapshot
Documentation conflict list
```

Sau khi người dùng review và xác nhận Phase 00, Agent mới được chuyển sang Phase 01.
