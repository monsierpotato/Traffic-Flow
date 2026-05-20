# TrafficFlow Lane Benchmark

Workspace benchmark 3 hướng lane detection cho TrafficFlow:

- UFLD / UFLDv2: speed baseline.
- LaneATT: candidate cân bằng cho prototype.
- CondLaneNet-small / medium: candidate cho cảnh phức tạp.

## Quick Start

```bash
pip install -r requirements-base.txt
python scripts/collect_system_info.py
python scripts/extract_frames.py data/raw_videos/traffic_01.mp4 data/frames/traffic_01 --step 30
python scripts/benchmark_fps.py --video data/raw_videos/traffic_01.mp4 --method noop --max-frames 300
```

## GPU Environment

This project has a local GPU venv at `.venv-gpu` using Python 3.10 and PyTorch CUDA 13.0 wheels.

```bash
py -3.10 -m venv .venv-gpu
.\.venv-gpu\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv-gpu\Scripts\python.exe -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
.\.venv-gpu\Scripts\python.exe -m pip install -r requirements-gpu.txt
.\.venv-gpu\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

CUDA Toolkit and MSVC Build Tools were installed with:

```bash
winget install -e --id Nvidia.CUDA --accept-package-agreements --accept-source-agreements
winget install -e --id Microsoft.VisualStudio.2022.BuildTools --accept-package-agreements --accept-source-agreements --override "--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
```

For commands that compile CUDA extensions, use the Visual C++ build environment:

```bash
cmd /c ""C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" && set DISTUTILS_USE_SDK=1 && set CUDA_HOME=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2 && set CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2 && .venv-gpu\Scripts\python.exe setup.py install"
```

If importing a custom CUDA extension fails with a DLL load error, make sure the current shell can see CUDA and PyTorch DLLs:

```powershell
$env:CUDA_HOME = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2"
$env:CUDA_PATH = $env:CUDA_HOME
$env:Path = "$env:CUDA_HOME\bin;$PWD\.venv-gpu\Lib\site-packages\torch\lib;$env:Path"
```

Run UFLD on GPU:

```bash
.\.venv-gpu\Scripts\python.exe scripts/run_ufld_video.py --weights weights/ufld_tusimple_18.pth --video data/raw_videos/traffic_01_time_lapse.mp4 --output-video benchmark_results/outputs/ufld/traffic_01_overlay_gpu.mp4 --output-csv benchmark_results/outputs/ufld/traffic_01_fps_gpu.csv --output-jsonl benchmark_results/outputs/ufld/traffic_01_lanes_gpu.jsonl --device cuda
```

Output chính nằm trong:

```text
benchmark_results/
trafficflow_integration/
```

Repo model bên thứ ba nên clone vào `repos/`, mỗi method có wrapper riêng trong `scripts/run_*.py`.
