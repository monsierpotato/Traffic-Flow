# Kế hoạch coding benchmark Lane Detection trên máy local

## 1. Mục tiêu benchmark

Mục tiêu của file này là hướng dẫn nhóm triển khai benchmark 3 hướng lane detection khác nhau trên máy local để chọn phương án phù hợp cho dự án **TrafficFlow**:

1. **UFLD / UFLDv2**
   Ưu tiên tốc độ rất cao, triển khai nhanh, phù hợp làm baseline nhẹ.

2. **LaneATT**
   Cân bằng tốt giữa độ chính xác và tốc độ, phù hợp làm ứng viên chính cho prototype.

3. **CondLaneNet-small / medium**
   Ưu tiên độ chính xác cao hơn trong giao thông phức tạp, nhiều lane chồng lấn, merge/split, vẫn giữ FPS tốt nếu có GPU.

Kết quả cuối cùng cần trả lời được:

- Method nào chạy nhanh nhất trên máy local?
- Method nào cho lane đủ ổn để gán xe vào làn?
- Method nào dễ tích hợp nhất với pipeline YOLOv8 + ByteTrack + Counting?
- Method nào nên chọn làm baseline chính cho TrafficFlow?
- Method nào nên giữ làm phương án nâng cấp?

---

## 2. Phạm vi benchmark

Benchmark không chỉ đo lane detection đẹp hay xấu trên ảnh, mà phải đánh giá khả năng phục vụ bài toán traffic flow.

### 2.1. Input

Sử dụng 3 nhóm dữ liệu:

| Nhóm dữ liệu | Mục đích | Ghi chú |
|---|---|---|
| Public sample từ TuSimple / CULane | Kiểm tra repo chạy đúng | Dùng sample nhỏ, không cần train full |
| Video CCTV giao thông của nhóm | Đánh giá sát bài toán TrafficFlow | Quan trọng nhất |
| Một số frame tự cắt từ video nhóm | Test nhanh overlay lane và gán lane | Dùng cho debug |

### 2.2. Output cần có

Mỗi method cần tạo ra:

- Video hoặc ảnh overlay lane.
- File log FPS.
- File JSON/CSV lưu kết quả benchmark.
- Nhận xét định tính: lane ổn, lệch, đứt đoạn, sai topology, nhạy ánh sáng.
- Nhận xét tích hợp: output có dễ chuyển thành lane polygon / centerline / BEV hay không.

---

## 3. Cấu hình máy local cần ghi nhận

Trước khi benchmark, ghi rõ cấu hình máy để kết quả có ý nghĩa.

Tạo file:

```bash
benchmark_results/system_info.md
```

Nội dung cần có:

```md
# System Info

- OS:
- CPU:
- RAM:
- GPU:
- GPU VRAM:
- CUDA version:
- cuDNN version:
- Python version:
- PyTorch version:
- OpenCV version:
- Date:
```

Lệnh gợi ý:

```bash
python --version
python -c "import torch; print('torch:', torch.__version__); print('cuda:', torch.cuda.is_available()); print('device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
python -c "import cv2; print('opencv:', cv2.__version__)"
nvidia-smi
```

---

## 4. Cấu trúc thư mục đề xuất

Tạo một workspace riêng cho benchmark:

```text
lane-benchmark/
│
├── README.md
├── plan.md
├── requirements-base.txt
│
├── data/
│   ├── raw_videos/
│   │   ├── traffic_01.mp4
│   │   ├── traffic_02.mp4
│   │   └── traffic_03.mp4
│   │
│   ├── frames/
│   │   ├── traffic_01/
│   │   ├── traffic_02/
│   │   └── traffic_03/
│   │
│   └── samples_public/
│
├── repos/
│   ├── UFLD/
│   ├── UFLDv2/
│   ├── LaneATT/
│   └── CondLaneNet/
│
├── scripts/
│   ├── extract_frames.py
│   ├── run_ufld.py
│   ├── run_ufldv2.py
│   ├── run_laneatt.py
│   ├── run_condlanenet.py
│   ├── benchmark_fps.py
│   ├── convert_lane_output.py
│   └── visualize_overlay.py
│
├── benchmark_results/
│   ├── system_info.md
│   ├── fps_results.csv
│   ├── qualitative_results.md
│   ├── summary.md
│   └── outputs/
│       ├── ufld/
│       ├── ufldv2/
│       ├── laneatt/
│       └── condlanenet/
│
└── trafficflow_integration/
    ├── lane_schema.md
    ├── sample_lane_output.json
    └── notes.md
```

---

## 5. Dataset và video test local

### 5.1. Video test chính

Nên chọn ít nhất 3 video giao thông:

| Video | Điều kiện | Mục đích |
|---|---|---|
| `traffic_01.mp4` | Ít xe, vạch làn rõ | Test baseline dễ |
| `traffic_02.mp4` | Đông xe, che khuất nhiều | Test độ bền |
| `traffic_03.mp4` | Ánh sáng xấu / bóng đổ / đêm nếu có | Test robustness |

Nếu chưa có video thật, dùng tạm:

- Video CCTV traffic công khai từ YouTube hoặc dataset.
- Video tự quay từ camera cố định.
- Video trích từ dataset traffic public.

### 5.2. Cắt frame từ video

Tạo script `scripts/extract_frames.py`:

```python
import cv2
from pathlib import Path

def extract_frames(video_path, output_dir, step=30):
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    frame_id = 0
    saved_id = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_id % step == 0:
            out_path = output_dir / f"frame_{saved_id:05d}.jpg"
            cv2.imwrite(str(out_path), frame)
            saved_id += 1

        frame_id += 1

    cap.release()
    print(f"Saved {saved_id} frames to {output_dir}")

if __name__ == "__main__":
    extract_frames(
        video_path="data/raw_videos/traffic_01.mp4",
        output_dir="data/frames/traffic_01",
        step=30
    )
```

Chạy:

```bash
python scripts/extract_frames.py
```

---

## 6. Metric benchmark

### 6.1. Metric tốc độ

Cần đo:

| Metric | Ý nghĩa |
|---|---|
| FPS trung bình | Số frame xử lý mỗi giây |
| Latency trung bình / frame | Thời gian xử lý 1 frame |
| Latency P95 | 95% frame xử lý dưới ngưỡng này |
| GPU memory | VRAM sử dụng |
| CPU RAM | RAM hệ thống sử dụng |
| Model loading time | Thời gian load model |

Công thức:

```text
FPS = total_frames / total_inference_time
latency_ms = total_inference_time / total_frames * 1000
```

### 6.2. Metric chất lượng

Nếu chưa có ground-truth lane annotation, dùng đánh giá định tính theo thang 1-5.

| Tiêu chí | Điểm 1 | Điểm 5 |
|---|---|---|
| Lane visibility | Không thấy làn | Lane rõ, liên tục |
| Lane stability | Nhảy nhiều giữa frame | Ổn định |
| Occlusion robustness | Mất lane khi xe che | Vẫn giữ được lane |
| Curve / merge / split | Sai hoàn toàn | Bắt được topology |
| Integration readiness | Output khó dùng | Output dễ chuyển sang polygon / centerline |

Nếu có annotation custom, đo thêm:

- Lane F1 nếu format tương thích.
- Pixel IoU nếu output dạng mask.
- Point distance error nếu output dạng polyline.
- Lane assignment accuracy: xe có được gán đúng làn không.
- Counting error theo làn.

### 6.3. Metric tích hợp TrafficFlow

Đây là metric quan trọng nhất cho dự án.

| Metric | Mô tả |
|---|---|
| Lane assignment accuracy | Xe được gán đúng làn hay không |
| Direction accuracy | Xuôi/ngược chiều đúng hay không |
| Counting MAE | Sai số đếm tuyệt đối |
| Counting MAPE | Sai số đếm phần trăm |
| End-to-end FPS | FPS toàn pipeline lane + vehicle detection + tracking |
| Engineering complexity | Mức độ khó khi tích hợp vào code nhóm |

---

## 7. Chuẩn output lane dùng chung

Để so sánh công bằng, dù mỗi repo có output khác nhau, nhóm nên convert về một schema chung.

File mẫu:

```json
{
  "video_id": "traffic_01",
  "frame_id": 120,
  "method": "LaneATT",
  "lanes": [
    {
      "lane_id": 1,
      "confidence": 0.91,
      "points": [[420, 720], [430, 680], [445, 640], [465, 600]],
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

Schema chung này giúp:

- Frontend dễ overlay lane.
- Counting module dễ gán xe vào lane.
- Benchmark dễ lưu thành JSON/CSV.
- Có thể thay model mà không đổi toàn bộ pipeline.

---

## 8. Method 1: UFLD / UFLDv2

### 8.1. Mục tiêu

Dùng UFLD hoặc UFLDv2 để có baseline rất nhanh.

UFLD phù hợp khi:

- Cần chạy FPS cao.
- Muốn triển khai nhanh.
- Chấp nhận accuracy thấp hơn một chút trong cảnh phức tạp.
- Cần fallback model nhẹ.

UFLDv2 phù hợp hơn UFLD nếu:

- Muốn giữ tốc độ cao nhưng lane topology tốt hơn.
- Muốn thử bản row-anchor + column-anchor hiện đại hơn.
- Có thời gian setup repo phức tạp hơn UFLD gốc.

### 8.2. Link repo

```text
UFLD:
https://github.com/cfzd/Ultra-Fast-Lane-Detection

UFLDv2:
https://github.com/cfzd/Ultra-Fast-Lane-Detection-v2
```

### 8.3. Setup đề xuất

```bash
cd lane-benchmark
mkdir -p repos
cd repos

git clone https://github.com/cfzd/Ultra-Fast-Lane-Detection.git UFLD
git clone https://github.com/cfzd/Ultra-Fast-Lane-Detection-v2.git UFLDv2
```

Tạo môi trường riêng:

```bash
conda create -n lane-ufld python=3.8 -y
conda activate lane-ufld

pip install torch torchvision torchaudio
pip install opencv-python numpy scipy tqdm matplotlib
```

Nếu dùng Docker hoặc server không cần GUI:

```bash
pip uninstall opencv-python -y
pip install opencv-python-headless
```

### 8.4. Checklist chạy UFLD

- [ ] Clone repo thành công.
- [ ] Cài dependency thành công.
- [ ] Download pretrained weight.
- [ ] Chạy inference trên sample image.
- [ ] Chạy inference trên frame cắt từ video nhóm.
- [ ] Chạy inference trên video `.mp4`.
- [ ] Ghi FPS.
- [ ] Convert output về lane schema chung.
- [ ] Overlay lane lên video.

---

## 9. Method 2: LaneATT

### 9.1. Mục tiêu

LaneATT là ứng viên cân bằng giữa tốc độ và độ chính xác.

Phù hợp khi:

- Muốn model không quá nặng.
- Cần lane ổn hơn UFLD trong cảnh khó.
- Muốn output dạng lane proposals/anchors dễ chuyển thành polyline.
- Cần một candidate chính cho prototype.

### 9.2. Link repo

```text
LaneATT:
https://github.com/lucastabelini/LaneATT
```

### 9.3. Setup đề xuất

```bash
cd lane-benchmark/repos
git clone https://github.com/lucastabelini/LaneATT.git LaneATT
```

Tạo môi trường riêng:

```bash
conda create -n laneatt python=3.8 -y
conda activate laneatt

pip install torch torchvision torchaudio
pip install opencv-python numpy scipy tqdm matplotlib pyyaml
```

Nếu gặp lỗi dependency, ưu tiên đọc `README.md` chính thức của repo và pin version theo repo.

### 9.4. Checklist chạy LaneATT

- [ ] Clone repo.
- [ ] Cài dependency.
- [ ] Download pretrained weight.
- [ ] Chạy demo image.
- [ ] Chạy demo frame CCTV.
- [ ] Chạy batch frames.
- [ ] Chạy video.
- [ ] Đo FPS.
- [ ] Convert output về schema chung.
- [ ] Overlay lane.
- [ ] So sánh với UFLD/UFLDv2.

---

## 10. Method 3: CondLaneNet-small / medium

### 10.1. Mục tiêu

CondLaneNet là hướng ưu tiên chất lượng cao hơn, đặc biệt trong các cảnh:

- Giao thông đông.
- Nhiều lane gần nhau.
- Làn nhập/tách.
- Vạch làn bị che.
- Topology phức tạp.

Chạy bản:

- `small` trước để đo tốc độ.
- `medium` sau nếu cần accuracy cao hơn.

### 10.2. Link repo

```text
CondLaneNet:
https://github.com/aliyun/conditional-lane-detection
```

### 10.3. Setup đề xuất

```bash
cd lane-benchmark/repos
git clone https://github.com/aliyun/conditional-lane-detection.git CondLaneNet
```

Tạo môi trường riêng:

```bash
conda create -n condlane python=3.8 -y
conda activate condlane

pip install torch torchvision torchaudio
pip install opencv-python numpy scipy tqdm matplotlib pyyaml
```

Repo này có thể phụ thuộc framework hoặc config phức tạp hơn. Cần ưu tiên chạy theo README chính thức.

### 10.4. Checklist chạy CondLaneNet

- [ ] Clone repo.
- [ ] Cài dependency đúng version.
- [ ] Download pretrained weight bản small.
- [ ] Chạy inference sample.
- [ ] Chạy inference frame CCTV.
- [ ] Download pretrained weight bản medium nếu có.
- [ ] Chạy benchmark small.
- [ ] Chạy benchmark medium.
- [ ] So sánh FPS small vs medium.
- [ ] Convert output về schema chung.
- [ ] Overlay lane lên video.
- [ ] Đánh giá cảnh merge/split, đông xe, che khuất.

---

## 11. Script benchmark FPS dùng chung

Tạo file:

```text
scripts/benchmark_fps.py
```

Mẫu khung code:

```python
import time
import csv
import cv2
from pathlib import Path
import numpy as np

class LaneModelWrapper:
    def __init__(self, method_name, weight_path=None, device="cuda"):
        self.method_name = method_name
        self.weight_path = weight_path
        self.device = device
        self.model = self.load_model()

    def load_model(self):
        # TODO: implement theo từng repo
        raise NotImplementedError

    def infer(self, frame):
        # TODO: return lane output theo schema chung
        raise NotImplementedError

def benchmark_video(model, video_path, output_csv, warmup=10, max_frames=None):
    video_path = Path(video_path)
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    latencies = []
    frame_id = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if max_frames is not None and frame_id >= max_frames:
            break

        start = time.perf_counter()
        _ = model.infer(frame)
        end = time.perf_counter()

        if frame_id >= warmup:
            latencies.append((end - start) * 1000)

        frame_id += 1

    cap.release()

    total_ms = sum(latencies)
    avg_ms = total_ms / max(len(latencies), 1)
    fps = 1000.0 / avg_ms if avg_ms > 0 else 0
    p95 = float(np.percentile(latencies, 95)) if latencies else 0

    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["method", "video", "frames", "avg_latency_ms", "p95_latency_ms", "fps"])
        writer.writerow([model.method_name, str(video_path), len(latencies), round(avg_ms, 3), round(p95, 3), round(fps, 2)])

    print(f"Method: {model.method_name}")
    print(f"Video: {video_path}")
    print(f"Frames measured: {len(latencies)}")
    print(f"Avg latency: {avg_ms:.3f} ms")
    print(f"P95 latency: {p95:.3f} ms")
    print(f"FPS: {fps:.2f}")
```

Do mỗi repo có inference API khác nhau, nên nhóm cần viết wrapper riêng:

```text
run_ufld.py
run_ufldv2.py
run_laneatt.py
run_condlanenet.py
```

Nhưng tất cả nên trả về schema chung.

---

## 12. Bảng benchmark tổng hợp

Sau khi chạy xong, điền vào:

```text
benchmark_results/summary.md
```

Mẫu bảng:

```md
# Lane Detection Benchmark Summary

## Hardware

- CPU:
- GPU:
- RAM:
- PyTorch:
- CUDA:

## FPS result

| Method | Backbone / Variant | Video 1 FPS | Video 2 FPS | Video 3 FPS | Avg FPS | Avg latency | VRAM |
|---|---|---:|---:|---:|---:|---:|---:|
| UFLD | ResNet18 |  |  |  |  |  |  |
| UFLDv2 | ResNet18 |  |  |  |  |  |  |
| LaneATT | ResNet18 |  |  |  |  |  |  |
| CondLaneNet | Small |  |  |  |  |  |  |
| CondLaneNet | Medium |  |  |  |  |  |  |

## Qualitative result

| Method | Lane visibility | Stability | Occlusion | Curve/Merge | Integration readiness | Total |
|---|---:|---:|---:|---:|---:|---:|
| UFLD / UFLDv2 |  |  |  |  |  |  |
| LaneATT |  |  |  |  |  |  |
| CondLaneNet-small |  |  |  |  |  |  |
| CondLaneNet-medium |  |  |  |  |  |  |

## TrafficFlow integration result

| Method | Easy to convert to polyline | Easy to assign lane | Stable for counting | Needs fine-tuning | Recommended role |
|---|---|---|---|---|---|
| UFLD / UFLDv2 |  |  |  |  | Speed baseline / fallback |
| LaneATT |  |  |  |  | Main prototype candidate |
| CondLaneNet-small |  |  |  |  | Complex traffic candidate |
| CondLaneNet-medium |  |  |  |  | Accuracy upgrade |
```

---

## 13. Kế hoạch thực hiện trong 5 ngày

### Ngày 1: Chuẩn bị workspace và dữ liệu

Việc cần làm:

- Tạo cấu trúc thư mục.
- Tải hoặc chuẩn bị 3 video test.
- Cắt frame từ video.
- Ghi system info.
- Clone 3 repo chính.
- Đọc README từng repo.

Deliverables:

- `lane-benchmark/` hoàn chỉnh.
- `data/raw_videos/` có ít nhất 3 video.
- `data/frames/` có frame cắt ra.
- `benchmark_results/system_info.md`.

### Ngày 2: Chạy UFLD / UFLDv2

Việc cần làm:

- Setup environment UFLD.
- Download pretrained weights.
- Chạy inference sample.
- Chạy inference trên frame CCTV.
- Chạy inference trên video.
- Đo FPS.
- Ghi nhận lỗi setup.

Deliverables:

- `benchmark_results/outputs/ufld/result.md`
- `benchmark_results/outputs/ufld/fps.csv`
- Video overlay UFLD.
- Nhận xét sơ bộ: có dùng được cho TrafficFlow không.

### Ngày 3: Chạy LaneATT

Việc cần làm:

- Setup environment LaneATT.
- Download pretrained weights.
- Chạy inference sample.
- Chạy inference trên video nhóm.
- Đo FPS.
- Convert output về schema chung.
- So sánh nhanh với UFLD.

Deliverables:

- `benchmark_results/outputs/laneatt/result.md`
- `benchmark_results/outputs/laneatt/fps.csv`
- Video overlay LaneATT.
- Nhận xét khả năng chọn làm model chính.

### Ngày 4: Chạy CondLaneNet-small / medium

Việc cần làm:

- Setup environment CondLaneNet.
- Chạy bản small trước.
- Nếu ổn, chạy bản medium.
- Đo FPS.
- Đánh giá cảnh đông xe / lane nhập tách / che khuất.
- Ghi nhận độ khó tích hợp.

Deliverables:

- `benchmark_results/outputs/condlanenet/result.md`
- `benchmark_results/outputs/condlanenet/fps.csv`
- Video overlay CondLaneNet-small.
- Video overlay CondLaneNet-medium nếu chạy được.
- Nhận xét small vs medium.

### Ngày 5: Tổng hợp và chọn phương án

Việc cần làm:

- Điền bảng tổng hợp.
- So sánh FPS.
- So sánh chất lượng lane.
- So sánh độ khó tích hợp.
- Chọn method chính.
- Chọn method fallback.
- Viết kết luận cho TrafficFlow.

Deliverables:

- `benchmark_results/summary.md`
- `trafficflow_integration/sample_lane_output.json`
- `trafficflow_integration/notes.md`
- Quyết định cuối cùng:
  - Main method:
  - Fallback method:
  - Upgrade method:

---

## 14. Tiêu chí ra quyết định

### 14.1. Nếu ưu tiên deadline 3 tuần

Chọn:

```text
Lane geometry thủ công + homography + YOLOv8 + ByteTrack
```

Sau đó dùng lane detector như module hỗ trợ.

### 14.2. Nếu cần lane detector học sâu chạy nhanh

Chọn:

```text
UFLD / UFLDv2
```

Vai trò:

```text
Speed baseline / fallback
```

### 14.3. Nếu cần cân bằng nhất

Chọn:

```text
LaneATT
```

Vai trò:

```text
Main prototype candidate
```

### 14.4. Nếu video giao thông phức tạp

Chọn:

```text
CondLaneNet-small
```

Nếu small chưa đủ tốt và máy local có GPU đủ mạnh:

```text
CondLaneNet-medium
```

Vai trò:

```text
Accuracy upgrade / complex-scene candidate
```

---

## 15. Rủi ro và cách xử lý

| Rủi ro | Nguyên nhân | Cách xử lý |
|---|---|---|
| Repo lỗi dependency | Code cũ, version PyTorch/CUDA không khớp | Tạo environment riêng từng repo |
| Không chạy được pretrained weight | Link hỏng hoặc format khác | Tìm issue repo, dùng mirror, hoặc bỏ method nếu quá tốn thời gian |
| FPS thấp trên CPU | Lane models thường tối ưu GPU | Benchmark GPU nếu có, hoặc chạy lane theo chu kỳ |
| Lane sai do CCTV khác domain | Model train trên dashcam | Fine-tune bằng custom CCTV hoặc dùng lane polygon thủ công |
| Output mỗi repo khác nhau | Không có schema chung | Viết converter về polyline JSON |
| Tốn quá nhiều thời gian setup CondLaneNet | Repo phức tạp | Giới hạn timebox 1 ngày, không để ảnh hưởng pipeline chính |
| Lane detection đẹp nhưng counting vẫn sai | Sai gán xe vào làn / sai line crossing | Đánh giá downstream metric, không chỉ nhìn overlay |

---

## 16. Checklist cuối cùng

Trước khi kết thúc benchmark, cần có:

- [ ] Chạy được ít nhất 2/3 method.
- [ ] Có FPS cho từng method.
- [ ] Có video/ảnh overlay kết quả.
- [ ] Có bảng đánh giá định tính.
- [ ] Có nhận xét tích hợp TrafficFlow.
- [ ] Có schema output lane chung.
- [ ] Có kết luận chọn method chính.
- [ ] Có fallback nếu method chính lỗi.
- [ ] Có đề xuất bước tiếp theo: fine-tune hay không.

---

## 17. Kết luận đề xuất ban đầu

Trước khi benchmark, giả thuyết kỹ thuật là:

```text
UFLD / UFLDv2 = nhanh nhất, phù hợp fallback.
LaneATT = cân bằng nhất, nên là candidate chính.
CondLaneNet-small = phù hợp nếu cảnh phức tạp và cần accuracy tốt hơn.
CondLaneNet-medium = chỉ dùng nếu GPU đủ mạnh và small chưa đạt.
```

Tuy nhiên, quyết định cuối cùng phải dựa trên:

1. FPS thực tế trên máy local.
2. Độ ổn định lane trên video CCTV của nhóm.
3. Khả năng convert output thành polyline/polygon.
4. Độ dễ tích hợp với YOLOv8 + ByteTrack + counting logic.
5. Sai số counting theo làn, không chỉ chất lượng lane nhìn bằng mắt.

---

## 18. Gợi ý phân công nhóm 5 người

| Thành viên | Nhiệm vụ |
|---|---|
| Phúc - Leader | Quản lý benchmark, chốt tiêu chí, review kết quả cuối |
| Nhật | Thiết kế schema lane output, tích hợp lane với counting logic |
| Hưng Cận | Chuẩn bị video, cắt frame, annotation/checklist định tính |
| Hưng Lốp | Setup và chạy UFLD/UFLDv2 + LaneATT |
| Tiến | Setup CondLaneNet, làm overlay video, tổng hợp bảng kết quả |

---

## 19. Definition of Done

Benchmark được xem là hoàn thành khi có đủ:

```text
benchmark_results/system_info.md
benchmark_results/summary.md
benchmark_results/fps_results.csv
benchmark_results/qualitative_results.md
trafficflow_integration/sample_lane_output.json
ít nhất 2 video overlay kết quả
kết luận chọn method chính/fallback/upgrade
```

Kết luận phải viết rõ:

```md
## Final Decision

- Main method:
- Fallback method:
- Upgrade method:
- Lý do chọn:
- Rủi ro còn lại:
- Việc cần làm tiếp theo:
```
## Dataset đề xuất cho benchmark lane detection

| Dataset | Mục đích | Phù hợp với method | Ưu điểm | Hạn chế | Link |
|---|---|---|---|---|---|
| TuSimple | Test nhanh lane detection highway | UFLD, UFLDv2, LaneATT | Nhẹ, dễ chạy, nhiều repo hỗ trợ | Chủ yếu highway, ít giống CCTV | ... |
| CULane | Benchmark cảnh khó hơn | UFLD, LaneATT, CondLaneNet | Có crowded, night, shadow, curve | Dữ liệu lớn hơn, setup lâu hơn | ... |
| BDD100K | Bổ sung domain đa dạng | Fine-tune / robustness | Nhiều điều kiện thời tiết, đô thị | Không phải lane benchmark đơn giản nhất | ... |
| CurveLanes | Lane cong, merge/split | CondLaneNet | Tốt cho topology phức tạp | Nặng hơn, không cần cho MVP | ... |
| Custom CCTV | Quan trọng nhất cho TrafficFlow | Tất cả | Giống bài toán thật | Cần tự cắt frame/gán nhãn | Local |
