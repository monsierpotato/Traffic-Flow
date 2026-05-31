import argparse
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_command(command):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            shell=True,
        )
    except Exception as exc:
        return f"unavailable ({exc})"

    output = (result.stdout or result.stderr).strip()
    return output if output else "unavailable"


def get_python_package_version(package_name, import_name=None):
    import_name = import_name or package_name
    try:
        module = __import__(import_name)
    except Exception:
        return "not installed"
    return getattr(module, "__version__", "unknown")


def get_torch_info():
    try:
        import torch
    except Exception:
        return {
            "torch": "not installed",
            "cuda_available": "unknown",
            "gpu": "unknown",
            "cuda_version": "unknown",
            "cudnn_version": "unknown",
        }

    cuda_available = torch.cuda.is_available()
    return {
        "torch": torch.__version__,
        "cuda_available": str(cuda_available),
        "gpu": torch.cuda.get_device_name(0) if cuda_available else "CPU only",
        "cuda_version": str(torch.version.cuda),
        "cudnn_version": str(torch.backends.cudnn.version()),
    }


def get_ram_gb():
    try:
        import psutil
    except Exception:
        return "unknown"
    return f"{psutil.virtual_memory().total / (1024 ** 3):.1f} GB"


def build_markdown():
    torch_info = get_torch_info()
    nvidia_smi = run_command("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")

    return "\n".join(
        [
            "# System Info",
            "",
            f"- OS: {platform.platform()}",
            f"- CPU: {platform.processor() or platform.machine()}",
            f"- RAM: {get_ram_gb()}",
            f"- GPU: {torch_info['gpu']}",
            f"- GPU VRAM: {nvidia_smi}",
            f"- CUDA available: {torch_info['cuda_available']}",
            f"- CUDA version: {torch_info['cuda_version']}",
            f"- cuDNN version: {torch_info['cudnn_version']}",
            f"- Python version: {sys.version.split()[0]}",
            f"- PyTorch version: {torch_info['torch']}",
            f"- OpenCV version: {get_python_package_version('opencv-python', 'cv2')}",
            f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="Collect local machine info for benchmark reports.")
    parser.add_argument(
        "--output",
        default="benchmark_results/system_info.md",
        help="Path to output markdown file.",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_markdown(), encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
