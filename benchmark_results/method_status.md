# Method Status

Date: 2026-05-19

## Local Environment

- OS: Windows 11
- Active GPU env: `.venv-gpu`
- Python: 3.10.9
- PyTorch after setup: `2.12.0+cu130`
- CUDA available in PyTorch: true
- GPU: NVIDIA GeForce RTX 5070 Ti
- GPU VRAM: 16303 MiB
- Conda: not installed
- CUDA toolkit: 13.2 installed at `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2`
- MSVC Build Tools: Visual Studio BuildTools 2022 installed

## UFLD

Status: runnable.

- Repo: `repos/UFLD`
- Weight used: `weights/ufld_tusimple_18.pth`
- Weight source: Hugging Face mirror, `jkdxbns/autonomous-driving-carla/tusimple_18.pth`
- Dataset head: TuSimple / ResNet18
- Device used: GPU
- Outputs:
  - `benchmark_results/outputs/ufld/traffic_01_overlay.mp4`
  - `benchmark_results/outputs/ufld/traffic_02_overlay.mp4`
  - `benchmark_results/outputs/ufld/traffic_03_overlay.mp4`
  - `benchmark_results/outputs/ufld/*_fps.csv`
  - `benchmark_results/outputs/ufld/*_lanes.jsonl`

Notes:

- This is a real pretrained UFLD run, not a dummy benchmark.
- FPS is inference-only and uses CUDA synchronization for correct timing.
- These public clips are time-lapse/stock videos, so quality is only a smoke test.

## PolyLaneNet

Status: runnable, but weak qualitative output on current clips.

- Repo: `repos/PolyLaneNet`
- Weight used: `weights/polylanenet/tusimple/models/model_2695.pt`
- Config used: `repos/PolyLaneNet/cfgs/tusimple_resnet50.yaml`
- Backbone: ResNet50
- Dataset head: TuSimple
- Device used: GPU
- Script: `scripts/run_polylanenet_video.py`
- Outputs:
  - `benchmark_results/outputs/polylanenet/traffic_01_overlay_gpu.mp4`
  - `benchmark_results/outputs/polylanenet/traffic_02_overlay_gpu.mp4`
  - `benchmark_results/outputs/polylanenet/traffic_03_overlay_gpu.mp4`
  - `benchmark_results/outputs/polylanenet/fps.csv`
  - `benchmark_results/outputs/polylanenet/lane_output.jsonl`

FPS:

| Video | FPS | Avg latency | Avg inference |
|---|---:|---:|---:|
| `traffic_01_time_lapse.mp4` | 106.17 | 9.419 ms | 4.897 ms |
| `traffic_02_clouds_highway.mp4` | 102.61 | 9.746 ms | 5.087 ms |
| `traffic_03_night_time_lapse.mp4` | 107.21 | 9.327 ms | 4.819 ms |

Notes:

- The checkpoint is a ResNet50 TuSimple checkpoint and loads cleanly.
- Polynomial output is converted to the shared lane polyline schema.
- Visual overlays show frequent hallucinated/crossing lanes on the current stock/time-lapse clips.
- Keep it as a geometry-friendly benchmark method, but do not choose it as production lane source yet.

## ENet-SAD

Status: blocked in the current Windows/Python benchmark.

- Official repo checked: `repos/Codes-for-Lane-Detection`
- PyTorch reimplementation checked: `repos/ENet-SAD_Pytorch`
- Official pretrained model downloaded:
  - `weights/enet_sad/official/ENet-label-new.t7`
- Source: official `ENet-Label-Torch/README.md`, Google Drive ID `1pIMThIsGn8z8rIs6WgSNzom1H8WVvP5Q`

Observed blocker:

- Official implementation is Torch7/Lua (`ENet-Label-Torch`), not PyTorch.
- Official pretrained file is a Torch7 `.t7` serialized `nn.Sequential`.
- `InhwanBae/ENet-SAD_Pytorch` provides PyTorch code, but no matching pretrained checkpoint.

Decision:

- Do not run untrained ENet-SAD.
- Record ENet-SAD as blocked for v2.
- If a third runnable method is required, use LaneATT as the replacement candidate because CUDA NMS now builds locally.

## LaneATT v2 Replacement Run

Status: runnable.

- Repo: `repos/LaneATT`
- Weight zip: `weights/laneatt/laneatt_experiments.zip`
- Extracted experiment: `weights/laneatt/extracted/experiments/laneatt_r18_tusimple`
- Weight used: `weights/laneatt/extracted/experiments/laneatt_r18_tusimple/models/model_0100.pt`
- Config used: `weights/laneatt/extracted/experiments/laneatt_r18_tusimple/config.yaml`
- Backbone: ResNet18
- Dataset head: TuSimple
- Device used: GPU
- Script: `scripts/run_laneatt_video.py`
- Outputs:
  - `benchmark_results/outputs/laneatt/traffic_01_overlay_gpu.mp4`
  - `benchmark_results/outputs/laneatt/traffic_02_overlay_gpu.mp4`
  - `benchmark_results/outputs/laneatt/traffic_03_overlay_gpu.mp4`
  - `benchmark_results/outputs/laneatt/fps.csv`
  - `benchmark_results/outputs/laneatt/lane_output.jsonl`

FPS:

| Video | FPS | Avg latency | Avg inference |
|---|---:|---:|---:|
| `traffic_01_time_lapse.mp4` | 122.58 | 8.158 ms | 3.932 ms |
| `traffic_02_clouds_highway.mp4` | 137.53 | 7.271 ms | 3.871 ms |
| `traffic_03_night_time_lapse.mp4` | 130.50 | 7.663 ms | 3.964 ms |

Notes:

- CUDA NMS extension is required and is working in `.venv-gpu`.
- LaneATT is used as the third runnable method because ENet-SAD is blocked by Torch7 weights.
- Visual output is more conservative than PolyLaneNet but still domain-shifted on stock/time-lapse clips.

## UFLDv2

Status: blocked by environment/dependencies.

Observed blockers:

- Initial import requires `addict`.
- Model import reaches `nvidia.dali`, which is not installed.
- NVIDIA DALI is primarily Linux-oriented and is not a good fit for this Windows/Python 3.13 setup.

Recommended next step:

- Run UFLDv2 in WSL2/Linux or Docker with Python 3.8 and CUDA PyTorch.
- Use official pretrained weights from the UFLDv2 README.

## LaneATT

Status: CUDA extension built.

Previous blocker:

```text
OSError: CUDA_HOME environment variable is not set. Please set it to your CUDA install root.
```

Cause:

- LaneATT requires `lib/nms` to compile a CUDA extension:
  `CUDAExtension('nms.details', ['src/nms.cpp', 'src/nms_kernel.cu'])`.
- PyTorch CUDA wheel provides CUDA runtime for inference, but not `nvcc` / full CUDA toolkit.

Resolution:

- Installed NVIDIA CUDA Toolkit 13.2 via winget.
- Installed Visual Studio Build Tools 2022 C++ workload via winget.
- Patched `repos/LaneATT/lib/nms` locally for CUDA 13 / PyTorch 2.12 compatibility:
  - added `/Zc:preprocessor`
  - replaced old `Tensor.type()` dispatch with `scalar_type()`
  - replaced old `.data<T>()` with `.data_ptr<T>()`
- Built and installed `nms-0.0.0-py3.10-win-amd64.egg` into `.venv-gpu`.

Remaining note:

- Importing `nms.details` requires CUDA and PyTorch DLL paths in the current shell PATH.

Recommended next step:

- Use Python 3.8 plus CUDA toolkit and CUDA PyTorch.
- Build with `cd repos/LaneATT/lib/nms && python setup.py install`.
- Then download LaneATT pretrained experiments from the official README.

## CondLaneNet

Status: blocked by old mmdetection/mmcv stack and Python 3.13 compatibility.

Observed blocker:

```text
KeyError: '__version__'
```

from `python setup.py develop` in `repos/CondLaneNet`.

Other expected blockers:

- Requires `mmcv==0.5.6`.
- Requires old mmdetection-style C++/CUDA ops.
- README targets older Python/PyTorch-era dependencies.

Recommended next step:

- Use a separate Linux/WSL2 env with Python 3.8.
- Install dependency versions from `repos/CondLaneNet/requirements`.
- Download `culane_small.pth` or `tusimple_small.pth` from the official Alibaba OSS links in README.
