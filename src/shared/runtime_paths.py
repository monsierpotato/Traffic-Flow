"""Resolve runtime assets independently of the process working directory."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_DIR = PROJECT_ROOT / "inference" / "models"
DEFAULT_MODEL_NAME = "yolov8n.pt"


def _absolute_path(value: str | os.PathLike[str], base: Path = PROJECT_ROOT) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


def resolve_model_path(
    model_path: str | os.PathLike[str] | None = None,
    model_dir: str | os.PathLike[str] | None = None,
) -> str:
    """Return the best model path, preferring the colocated inference bundle.

    ``inference/models`` is the canonical deploy location. Existing local
    configurations using ``models/<file>`` remain readable while the canonical
    file is present, which allows a staged migration without breaking workers.
    """

    raw_path = Path(model_path or DEFAULT_MODEL_NAME).expanduser()
    if raw_path.is_absolute():
        return str(raw_path)

    configured_dir = model_dir or os.getenv("AI_MODEL_DIR")
    canonical_dir = _absolute_path(configured_dir) if configured_dir else DEFAULT_MODEL_DIR
    candidates: list[Path] = []

    if len(raw_path.parts) == 1:
        candidates.append(canonical_dir / raw_path.name)
    elif raw_path.parts[0] == "models" or raw_path.parts[:2] == ("inference", "models"):
        candidates.append(canonical_dir / raw_path.name)
        candidates.append(PROJECT_ROOT / raw_path)
    else:
        candidates.append(PROJECT_ROOT / raw_path)
        candidates.append(Path.cwd() / raw_path)

    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return str(candidate)

    return str(candidates[0].resolve())
