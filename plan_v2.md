# plan_v2.md — Kế hoạch benchmark Lane-Only Models cho TrafficFlow

## 1. Mục tiêu

Mục tiêu của kế hoạch này là cập nhật lại benchmark lane detection cho dự án **TrafficFlow** sau khi nhóm đã test thực tế và phát hiện một số model ban đầu không phù hợp với môi trường local hiện tại.

Benchmark mới chỉ tập trung vào **lane-only models**, không dùng các model multi-task như YOLOP, TwinLiteNet hoặc HybridNets.

Pipeline TrafficFlow tổng thể:

```text
Video input
→ Lane detection / lane geometry
→ YOLOv8 vehicle detection
→ ByteTrack vehicle tracking
→ Lane assignment
→ Direction logic
→ Vehicle counting
→ JSON result + visualization
```

Trong đó, phần benchmark này chỉ đánh giá module:

```text
Video / frame
→ Lane-only model
→ Lane lines / lane polylines / lane masks
→ Lane geometry usable for counting
```

---

## 2. Bối cảnh sau benchmark ban đầu

Nhóm đã chuẩn bị 3 video test nhẹ trong:

```text
data/raw_videos/
```

Các file hiện có:

| File | Resolution | Duration | Size |
|---|---:|---:|---:|
| `traffic_01_time_lapse.mp4` | 640x360 | 26.54s | 2.22 MB |
| `traffic_02_clouds_highway.mp4` | 640x360 | 24.67s | 2.06 MB |
| `traffic_03_night_time_lapse.mp4` | 640x360 | 13.04s | 1.10 MB |

Nhóm cũng đã cắt frame mẫu:

| Folder | Số frame |
|---|---:|
| `data/frames/traffic_01/` | 11 |
| `data/frames/traffic_02/` | 10 |
| `data/frames/traffic_03/` | 6 |

Nguồn video ban đầu:

```text
https://publicdomainmovie.net/movie/traffic-time-lapse-free-to-use-hd-stock-video-footage
https://publicdomainmovie.net/movie/traffic-and-clouds-free-to-use-hd-stock-video-footage
https://publicdomainmovie.net/movie/night-traffic-time-lapse-free-to-use-hd-stock-video-footage
```

Nguồn CCTV tốt hơn cho benchmark chính:

```text
https://github.com/City-of-Bellevue/TrafficVideoDataset
```

Dataset Bellevue phù hợp hơn cho TrafficFlow vì là video giao thông thật từ camera giao lộ, độ phân giải 1280x720, 30Hz, nhiều giờ video, nhưng kích thước lớn nên chỉ nên tải một phần nhỏ để benchmark.

---

## 3. Kết quả benchmark ban đầu

| Method | Trạng thái |
|---|---|
| UFLD | Chạy được thật trên 3 video |
| LaneATT | Bị block do thiếu CUDA toolkit / CUDA_HOME để build NMS |
| CondLaneNet | Bị block do stack cũ mmdetection/mmcv không tương thích Python 3.13 hiện tại |
| UFLDv2 | Bị block bởi dependency `nvidia.dali` / môi trường Windows hiện tại |

UFLD đã chạy với pretrained `tusimple_18.pth` tải từ Hugging Face mirror.

Thông tin môi trường hiện tại:

```text
torch 2.12.0+cpu
cuda False
```

FPS CPU-only của UFLD:

| Video | FPS |
|---|---:|
| `traffic_01_time_lapse.mp4` | 11.54 |
| `traffic_02_clouds_highway.mp4` | 11.13 |
| `traffic_03_night_time_lapse.mp4` | 9.33 |

Kết luận ban đầu:

```text
UFLD giữ lại làm speed baseline.
LaneATT và CondLaneNet không nên tiếp tục cố chạy trên Windows Python 3.13 hiện tại.
UFLDv2 chỉ thử lại nếu đổi sang WSL2/Linux hoặc conda environment phù hợp.
```

---

## 4. Lý do cập nhật benchmark

Benchmark ban đầu gồm:

```text
UFLD / UFLDv2
LaneATT
CondLaneNet-small / medium
```

Tuy nhiên, sau khi test thực tế:

1. **LaneATT** bị chặn bởi custom CUDA/NMS extension.
2. **CondLaneNet** phụ thuộc stack cũ như `mmdetection`, `mmcv`, CUDA/C++ extension, không hợp với Python 3.13.
3. **UFLDv2** gặp vấn đề dependency `nvidia.dali`, không thuận lợi trên Windows hiện tại.
4. Dự án TrafficFlow có deadline ngắn, nên benchmark phải ưu tiên model có khả năng chạy được nhanh và dễ tích hợp.

Vì vậy, benchmark v2 chuyển sang:

```text
UFLD
PolyLaneNet
ENet-SAD
```

Optional:

```text
CLRNet
UFLDv2
```

---

## 5. Bộ model benchmark v2

### 5.1. Model chính

| Ưu tiên | Model | Vai trò | Lý do chọn |
|---:|---|---|---|
| 1 | UFLD | Speed baseline | Đã chạy được, FPS CPU-only đã có |
| 2 | PolyLaneNet | Geometry-friendly lane-only model | Output dạng polynomial, hợp với lane geometry |
| 3 | ENet-SAD | Lightweight segmentation lane-only model | Nhẹ, có nền tảng học thuật tốt, thay CondLaneNet |

### 5.2. Model optional

| Ưu tiên | Model | Vai trò | Điều kiện thử |
|---:|---|---|---|
| 4 | CLRNet | Accuracy-oriented lane-only model | Chỉ thử nếu có WSL2/Linux/conda ổn định |
| 5 | UFLDv2 | Nâng cấp UFLD | Chỉ thử nếu xử lý được dependency DALI/môi trường |

---

## 6. Method A — UFLD

### 6.1. Vai trò

UFLD là baseline tốc độ cho benchmark v2.

```text
Role: Speed baseline / lightweight lane-only baseline
Status: Already runnable
```

### 6.2. Link repo

```text
https://github.com/cfzd/Ultra-Fast-Lane-Detection
```

### 6.3. Input

```text
data/raw_videos/traffic_01_time_lapse.mp4
data/raw_videos/traffic_02_clouds_highway.mp4
data/raw_videos/traffic_03_night_time_lapse.mp4
```

Nếu tải được Bellevue sample:

```text
data/raw_videos/bellevue_sample_01.mp4
data/raw_videos/bellevue_sample_02.mp4
```

### 6.4. Output hiện có

```text
benchmark_results/outputs/ufld/
benchmark_results/outputs/ufld/result.md
benchmark_results/outputs/ufld/fps.csv
benchmark_results/summary.md
benchmark_results/method_status.md
scripts/run_ufld_video.py
```

### 6.5. Điểm mạnh

- Đã chạy được trên môi trường hiện tại.
- Tốc độ tốt với CPU-only.
- Dễ dùng làm baseline.
- Phù hợp để chứng minh benchmark có chạy thực tế.

### 6.6. Điểm yếu

- Pretrained TuSimple thiên về dashcam/highway.
- Có thể yếu trên CCTV/góc nhìn cao.
- Cần hậu xử lý lane output để phục vụ lane assignment.
- Không phải lựa chọn tốt nhất cho cảnh lane phức tạp.

### 6.7. Việc cần làm tiếp

- Giữ kết quả hiện tại.
- Chạy lại nếu có GPU CUDA.
- Test thêm trên Bellevue CCTV sample.
- Convert output về schema lane chung.

---

## 7. Method B — PolyLaneNet

### 7.1. Vai trò

PolyLaneNet là model thay thế chính cho LaneATT.

```text
Role: Geometry-friendly lane-only model
Reason: Output dạng polynomial dễ dùng cho TrafficFlow
```

### 7.2. Link tham khảo

```text
Paper / project:
https://arxiv.org/abs/2004.10924

GitHub search keyword:
PolyLaneNet lane detection GitHub
```

Nếu dùng repo public, lưu vào:

```text
repos/PolyLaneNet/
```

### 7.3. Vì sao phù hợp với TrafficFlow

TrafficFlow cần lane để gán xe vào làn và đếm theo làn. PolyLaneNet dự đoán lane theo dạng đường cong/đa thức, nên thuận lợi để chuyển thành:

```text
lane polyline
lane boundary
lane polygon
lane centerline
```

Điều này phù hợp hơn với counting so với output quá phụ thuộc vào mask hoặc custom format.

### 7.4. Điểm mạnh

- Lane-only, đúng nhu cầu benchmark.
- Output có tính hình học rõ ràng.
- Dễ giải thích trong báo cáo methodology.
- Có thể tái sử dụng trong module lane geometry.
- Có tiềm năng dễ tích hợp với lane assignment.

### 7.5. Điểm yếu

- Có thể không mạnh trong cảnh merge/split phức tạp.
- Có thể bị domain shift nếu pretrained trên dashcam nhưng test trên CCTV.
- Repo có thể cũ, cần kiểm tra version Python/PyTorch.
- Nếu output polynomial không ổn định, counting theo lane có thể sai.

### 7.6. Checklist triển khai

- [ ] Tìm repo PolyLaneNet có pretrained weight.
- [ ] Clone repo vào `repos/PolyLaneNet/`.
- [ ] Tạo environment riêng nếu cần.
- [ ] Chạy inference trên sample image của repo.
- [ ] Chạy inference trên frame trong `data/frames/`.
- [ ] Chạy inference trên 3 video local.
- [ ] Đo FPS CPU/GPU.
- [ ] Convert output polynomial thành list point/polyline.
- [ ] Overlay lane lên video.
- [ ] Ghi kết quả vào `benchmark_results/outputs/polylanenet/`.

### 7.7. Output cần tạo

```text
benchmark_results/outputs/polylanenet/result.md
benchmark_results/outputs/polylanenet/fps.csv
benchmark_results/outputs/polylanenet/overlay_traffic_01.mp4
benchmark_results/outputs/polylanenet/overlay_traffic_02.mp4
benchmark_results/outputs/polylanenet/overlay_traffic_03.mp4
benchmark_results/outputs/polylanenet/lane_output.jsonl
```

---

## 8. Method C — ENet-SAD

### 8.1. Vai trò

ENet-SAD là model thay thế CondLaneNet theo hướng nhẹ hơn.

```text
Role: Lightweight segmentation-based lane-only model
Reason: Nhẹ hơn, có self-attention distillation, phù hợp benchmark nhanh
```

### 8.2. Link tham khảo

```text
Paper:
https://arxiv.org/abs/1908.00821

GitHub search keyword:
ENet-SAD lane detection GitHub
```

Nếu dùng repo public, lưu vào:

```text
repos/ENet-SAD/
```

### 8.3. Vì sao phù hợp với TrafficFlow

ENet-SAD có thể sinh lane map hoặc lane segmentation output. Sau đó nhóm có thể hậu xử lý thành:

```text
binary lane mask
skeleton lane line
polyline
lane polygon
```

Dạng output này phù hợp cho visualization và có thể dùng để tạo vùng làn.

### 8.4. Điểm mạnh

- Lane-only.
- Nhẹ hơn các model phức tạp như CondLaneNet.
- Có nền tảng học thuật tốt.
- Có thể so sánh tốt với UFLD:
  - UFLD: row-anchor/classification style.
  - ENet-SAD: segmentation/distillation style.

### 8.5. Điểm yếu

- Repo có thể cũ.
- Có thể vẫn cần version PyTorch/Python thấp hơn.
- Output segmentation cần hậu xử lý để thành polyline.
- Nếu lane mask nhiễu, lane assignment có thể không ổn định.

### 8.6. Checklist triển khai

- [ ] Tìm repo ENet-SAD có pretrained weight.
- [ ] Clone repo vào `repos/ENet-SAD/`.
- [ ] Tạo environment riêng.
- [ ] Chạy demo image.
- [ ] Chạy trên frame local.
- [ ] Chạy trên 3 video local.
- [ ] Đo FPS.
- [ ] Convert mask/lane output thành schema chung.
- [ ] Overlay lane lên video.
- [ ] Ghi nhận lỗi dependency nếu có.

### 8.7. Output cần tạo

```text
benchmark_results/outputs/enet_sad/result.md
benchmark_results/outputs/enet_sad/fps.csv
benchmark_results/outputs/enet_sad/overlay_traffic_01.mp4
benchmark_results/outputs/enet_sad/overlay_traffic_02.mp4
benchmark_results/outputs/enet_sad/overlay_traffic_03.mp4
benchmark_results/outputs/enet_sad/lane_output.jsonl
```

---

## 9. Optional Method D — CLRNet

### 9.1. Vai trò

CLRNet là optional model theo hướng accuracy-oriented.

```text
Role: Accuracy-oriented lane-only model
Priority: Optional
```

### 9.2. Link tham khảo

```text
Paper:
https://arxiv.org/abs/2203.10350

GitHub search keyword:
CLRNet lane detection GitHub
```

### 9.3. Khi nào nên thử

Chỉ thử nếu có một trong các điều kiện sau:

```text
WSL2 Ubuntu
Linux server
conda Python 3.8/3.9
CUDA PyTorch ổn định
```

Không nên thử CLRNet nếu vẫn dùng:

```text
Windows native
Python 3.13
CPU-only
```

### 9.4. Điểm mạnh

- Mạnh hơn về độ chính xác lane detection.
- Có giá trị cao cho phần methodology.
- Phù hợp nếu nhóm muốn thảo luận cross-layer refinement.
- Có thể tốt hơn trong lane cong, lane khó.

### 9.5. Điểm yếu

- Setup có thể phức tạp.
- Không phù hợp làm blocker trong dự án 3 tuần.
- Có thể gặp dependency tương tự LaneATT/CondLaneNet.

### 9.6. Quy tắc timebox

```text
Nếu sau 1 ngày không chạy được demo image → dừng.
Không để CLRNet ảnh hưởng pipeline chính.
```

---

## 10. Optional Method E — UFLDv2

### 10.1. Vai trò

UFLDv2 là bản nâng cấp từ UFLD, nhưng hiện tại bị block do dependency.

```text
Role: Upgrade of UFLD
Priority: Optional
```

### 10.2. Link repo

```text
https://github.com/cfzd/Ultra-Fast-Lane-Detection-v2
```

### 10.3. Khi nào thử lại

Chỉ thử nếu nhóm chuyển sang môi trường:

```text
WSL2 Ubuntu
conda Python 3.8/3.9
CUDA PyTorch
Dependency DALI xử lý được
```

### 10.4. Quy tắc timebox

```text
Nếu sau 0.5 ngày chưa chạy được sample → dừng.
Dùng UFLD v1 thay thế.
```

---

## 11. Dataset đề xuất

### 11.1. Dataset local hiện tại

| Dataset/video | Mục đích | Ghi chú |
|---|---|---|
| `traffic_01_time_lapse.mp4` | Test baseline dễ | Nhẹ, chạy nhanh |
| `traffic_02_clouds_highway.mp4` | Test highway/time-lapse | Nhẹ, không quá giống CCTV |
| `traffic_03_night_time_lapse.mp4` | Test ánh sáng đêm | Ít frame, phù hợp smoke test |

Các video này chỉ nên dùng cho:

```text
smoke test
kiểm tra repo chạy được
benchmark tốc độ ban đầu
debug overlay
```

Không nên dùng để kết luận cuối cùng về chất lượng TrafficFlow.

### 11.2. Dataset CCTV chính

| Dataset | Mục đích | Link | Ghi chú |
|---|---|---|---|
| Bellevue Traffic Video Dataset | Benchmark chính cho CCTV traffic | `https://github.com/City-of-Bellevue/TrafficVideoDataset` | Nên tải sample nhỏ, không tải toàn bộ |

Bellevue phù hợp hơn vì:

- Video giao thông thật.
- Camera cố định.
- Gần với bài toán TrafficFlow.
- Có nhiều giao lộ.
- Có thể kiểm tra lane assignment và counting thực tế hơn.

### 11.3. Dataset lane public để test model

| Dataset | Phù hợp với model | Vai trò | Hạn chế |
|---|---|---|---|
| TuSimple | UFLD, PolyLaneNet | Test nhanh, nhiều pretrained hỗ trợ | Chủ yếu highway/dashcam |
| CULane | UFLD, ENet-SAD, CLRNet | Cảnh khó hơn: crowded, night, shadow | Dataset lớn hơn, setup lâu hơn |
| BDD100K | ENet-SAD / robustness | Đa dạng thời tiết, đô thị | Không phải benchmark lane đơn giản nhất |

### 11.4. Quy tắc dùng dataset

Thứ tự ưu tiên:

```text
1. Chạy được model trên sample của repo.
2. Chạy trên 3 video local hiện có.
3. Chạy trên Bellevue CCTV sample.
4. Nếu cần so sánh academic, chạy thêm TuSimple/CULane sample.
```

Không nên mất quá nhiều thời gian tải full dataset nếu mục tiêu là demo TrafficFlow trong 3 tuần.

---

## 12. Schema output lane chung

Mỗi method phải được convert về cùng một schema để dễ tích hợp.

File mẫu:

```json
{
  "video_id": "traffic_01",
  "frame_id": 120,
  "method": "PolyLaneNet",
  "lanes": [
    {
      "lane_id": 1,
      "confidence": 0.91,
      "points": [
        [420, 720],
        [430, 680],
        [445, 640],
        [465, 600]
      ],
      "type": "polyline"
    }
  ],
  "runtime": {
    "preprocess_ms": 3.2,
    "inference_ms": 8.7,
    "postprocess_ms": 2.1,
    "total_ms": 14.0,
    "fps": 71.4
  }
}
```

Lưu dạng JSONL:

```text
benchmark_results/outputs/<method>/lane_output.jsonl
```

Mỗi dòng là output của một frame.

---

## 13. Hậu xử lý lane cho TrafficFlow

### 13.1. Convert polynomial sang polyline

Với PolyLaneNet, nếu output là đa thức:

```text
x = a*y^3 + b*y^2 + c*y + d
```

Lấy nhiều giá trị `y` trong vùng ảnh:

```text
y = y_min, y_min + step, ..., y_max
```

Tính `x` tương ứng:

```text
x_i = a*y_i^3 + b*y_i^2 + c*y_i + d
```

Tạo polyline:

```json
[
  [x1, y1],
  [x2, y2],
  [x3, y3]
]
```

### 13.2. Convert mask sang polyline

Với ENet-SAD nếu output là lane mask:

1. Threshold mask.
2. Morphology để giảm nhiễu.
3. Skeletonize lane mask nếu cần.
4. Tách connected components.
5. Fit polyline hoặc polynomial.
6. Lưu về schema chung.

### 13.3. Lane assignment

Dùng điểm đại diện của xe:

```text
bottom-center = ((x1 + x2) / 2, y2)
```

Sau đó xác định xe thuộc làn nào bằng:

```text
point-in-polygon
nearest lane centerline
homography to bird-eye-view
```

Với CCTV cố định, nên ưu tiên:

```text
manual lane polygon + bottom-center point
```

Lane detection model có thể dùng để hỗ trợ gợi ý lane, nhưng counting production nên có fallback bằng polygon thủ công.

---

## 14. Metric benchmark

### 14.1. Metric tốc độ

| Metric | Ý nghĩa |
|---|---|
| FPS trung bình | Số frame xử lý mỗi giây |
| Latency trung bình / frame | Thời gian xử lý 1 frame |
| Latency P95 | 95% frame có latency dưới ngưỡng này |
| Model loading time | Thời gian load model |
| RAM/VRAM usage | Tài nguyên sử dụng |

Công thức:

```text
FPS = total_frames / total_inference_time
latency_ms = total_inference_time / total_frames * 1000
```

### 14.2. Metric chất lượng định tính

Chấm điểm 1-5:

| Tiêu chí | Mô tả |
|---|---|
| Lane visibility | Lane có rõ và đúng không |
| Temporal stability | Lane có bị nhảy giữa frame không |
| Occlusion robustness | Xe che vạch lane thì model có giữ được không |
| Night/lighting robustness | Có chịu được đêm/bóng đổ không |
| CCTV suitability | Có hợp với góc nhìn camera cố định không |
| Integration readiness | Output có dễ chuyển sang lane geometry không |

### 14.3. Metric phục vụ TrafficFlow

| Metric | Mô tả |
|---|---|
| Lane assignment accuracy | Xe có được gán đúng làn không |
| Counting compatibility | Output lane có dùng được cho đếm không |
| End-to-end FPS | FPS khi kết hợp lane + YOLOv8 + tracking |
| Engineering complexity | Độ khó tích hợp vào code hiện tại |
| Reusability | Có thể thay model mà không sửa pipeline không |

---

## 15. Bảng kết quả cần điền

Tạo file:

```text
benchmark_results/lane_only_summary_v2.md
```

Mẫu:

```md
# Lane-only Benchmark Summary v2

## Environment

- OS:
- Python:
- PyTorch:
- CUDA:
- CPU:
- GPU:
- RAM:

## Method status

| Method | Status | Reason |
|---|---|---|
| UFLD | Passed | Ran on 3 videos |
| PolyLaneNet |  |  |
| ENet-SAD |  |  |
| CLRNet | Optional |  |
| UFLDv2 | Optional |  |

## FPS

| Method | Video 1 FPS | Video 2 FPS | Video 3 FPS | Avg FPS | Device |
|---|---:|---:|---:|---:|---|
| UFLD | 11.54 | 11.13 | 9.33 | 10.67 | CPU |
| PolyLaneNet |  |  |  |  |  |
| ENet-SAD |  |  |  |  |  |

## Qualitative score

| Method | Visibility | Stability | Occlusion | Night | CCTV suitability | Integration | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| UFLD |  |  |  |  |  |  |  |
| PolyLaneNet |  |  |  |  |  |  |  |
| ENet-SAD |  |  |  |  |  |  |  |

## Final decision

- Main lane-only model:
- Speed baseline:
- Optional accuracy model:
- Fallback for production:
- Reason:
```

---

## 16. Roadmap 4 ngày cho benchmark v2

### Ngày 1 — Chuẩn hóa kết quả UFLD và chuẩn bị schema

Tasks:

- [ ] Review lại output UFLD hiện có.
- [ ] Tạo schema `lane_output.jsonl`.
- [ ] Viết converter UFLD → schema chung.
- [ ] Tạo script overlay chung.
- [ ] Chuẩn bị Bellevue sample nếu tải được.

Deliverables:

```text
benchmark_results/outputs/ufld/lane_output.jsonl
trafficflow_integration/lane_schema.md
scripts/visualize_lane_overlay.py
```

### Ngày 2 — Benchmark PolyLaneNet

Tasks:

- [ ] Tìm repo PolyLaneNet có pretrained.
- [ ] Clone vào `repos/PolyLaneNet/`.
- [ ] Setup environment.
- [ ] Chạy demo image.
- [ ] Chạy 3 video local.
- [ ] Đo FPS.
- [ ] Convert polynomial output → polyline.
- [ ] Overlay video.

Deliverables:

```text
benchmark_results/outputs/polylanenet/result.md
benchmark_results/outputs/polylanenet/fps.csv
benchmark_results/outputs/polylanenet/lane_output.jsonl
benchmark_results/outputs/polylanenet/overlay_traffic_01.mp4
```

Stop condition:

```text
Nếu sau 1 ngày không chạy được demo image hoặc không có pretrained weight usable → dừng PolyLaneNet, chuyển sang ENet-SAD.
```

### Ngày 3 — Benchmark ENet-SAD

Tasks:

- [ ] Tìm repo ENet-SAD có pretrained.
- [ ] Clone vào `repos/ENet-SAD/`.
- [ ] Setup environment.
- [ ] Chạy demo image.
- [ ] Chạy 3 video local.
- [ ] Đo FPS.
- [ ] Convert mask/lane output → polyline.
- [ ] Overlay video.

Deliverables:

```text
benchmark_results/outputs/enet_sad/result.md
benchmark_results/outputs/enet_sad/fps.csv
benchmark_results/outputs/enet_sad/lane_output.jsonl
benchmark_results/outputs/enet_sad/overlay_traffic_01.mp4
```

Stop condition:

```text
Nếu sau 1 ngày dependency lỗi nặng → dừng ENet-SAD, ghi rõ reason vào method_status.md.
```

### Ngày 4 — Tổng hợp và quyết định

Tasks:

- [ ] Điền bảng FPS.
- [ ] Chấm điểm định tính.
- [ ] So sánh output lane.
- [ ] Đánh giá khả năng tích hợp với TrafficFlow.
- [ ] Chọn model chính.
- [ ] Chọn fallback.
- [ ] Cập nhật báo cáo.

Deliverables:

```text
benchmark_results/lane_only_summary_v2.md
benchmark_results/final_decision_v2.md
```

---

## 17. Phân công nhóm 5 người

| Thành viên | Nhiệm vụ |
|---|---|
| Phúc - Leader | Chốt tiêu chí benchmark, review kết quả, quyết định model cuối |
| Nhật | Thiết kế schema lane output, lane assignment, tích hợp counting |
| Hưng Cận | Chuẩn bị video/dataset, tải Bellevue sample, ghi nguồn dataset |
| Hưng Lốp | Chạy UFLD và PolyLaneNet, ghi FPS/output |
| Tiến | Chạy ENet-SAD, overlay visualization, tổng hợp bảng kết quả |

---

## 18. Quy tắc không để benchmark làm chậm dự án

Do TrafficFlow là dự án 3 tuần, phần lane-only benchmark phải tuân thủ quy tắc:

```text
Mỗi model chỉ được timebox tối đa 1 ngày.
Nếu không chạy được demo image trong 1 ngày → dừng model đó.
Không sửa sâu dependency cũ nếu không cần thiết.
Không để lane detection model làm blocker cho YOLOv8 + tracking + counting.
```

Fallback production cho CCTV cố định:

```text
Manual lane polygon + bottom-center point + point-in-polygon
```

Lý do:

- Camera CCTV cố định.
- Lane geometry gần như không đổi.
- Dễ debug.
- Ổn định cho counting.
- Không phụ thuộc model lane detection mỗi frame.

Lane-only model nên dùng để:

```text
benchmark research
gợi ý lane
overlay visualization
so sánh phương pháp
hỗ trợ báo cáo kỹ thuật
```

Không nên bắt buộc dùng lane model làm module production nếu kết quả không ổn định.

---

## 19. Definition of Done

Benchmark v2 hoàn thành khi có:

- [ ] UFLD result đã chuẩn hóa.
- [ ] PolyLaneNet được chạy hoặc có lý do dừng rõ ràng.
- [ ] ENet-SAD được chạy hoặc có lý do dừng rõ ràng.
- [ ] Có ít nhất 2 method có kết quả so sánh.
- [ ] Có bảng FPS.
- [ ] Có bảng chất lượng định tính.
- [ ] Có overlay video hoặc overlay frame.
- [ ] Có schema lane chung.
- [ ] Có final decision.
- [ ] Có fallback nếu model lane-only không đủ ổn định.

---

## 20. Kết luận đề xuất trước khi chạy v2

Giả thuyết kỹ thuật trước khi chạy:

```text
UFLD = nhanh nhất và đã chạy được.
PolyLaneNet = ứng viên tốt nhất để thay LaneATT vì output hình học rõ ràng.
ENet-SAD = ứng viên nhẹ để thay CondLaneNet.
CLRNet = optional nếu cần accuracy cao và có môi trường Linux ổn.
UFLDv2 = optional nếu xử lý được dependency.
```

Quyết định mong muốn sau benchmark:

```text
Main lane-only benchmark model: PolyLaneNet hoặc UFLD
Speed baseline: UFLD
Lightweight alternative: ENet-SAD
Accuracy optional: CLRNet
Production fallback: Manual lane polygon
```

Ghi chú quan trọng cho báo cáo:

```text
LaneATT và CondLaneNet không tiếp tục trong benchmark chính vì không phù hợp với môi trường Windows Python 3.13 hiện tại:
- LaneATT cần CUDA_HOME / CUDA toolkit để build NMS extension.
- CondLaneNet phụ thuộc stack cũ mmdetection/mmcv.
- UFLDv2 gặp dependency nvidia.dali.
Nhóm thay thế bằng PolyLaneNet và ENet-SAD vì đây là lane-only models nhẹ hơn, có methodology rõ ràng và phù hợp hơn với deadline TrafficFlow.
```
