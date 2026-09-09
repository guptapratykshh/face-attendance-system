"""Download and cache the ONNX face models (InsightFace buffalo_l pack)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from app.core.config import settings

BUFFALO_L_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"

# Members of the pack that this project uses. The pack also ships 1k3d68, 2d106det and
# genderage, which are irrelevant here and are deleted to save disk.
DETECTOR_FILE = "det_10g.onnx"  # SCRFD-10GF detector, gives bbox + 5 landmarks
RECOGNITION_FILE = "w600k_r50.onnx"  # ArcFace ResNet50 trained on WebFace600K, 512-D
KEEP = {DETECTOR_FILE, RECOGNITION_FILE}


def buffalo_dir() -> Path:
    return settings.weights_dir / "buffalo_l"


def ensure_buffalo_l(keep_all: bool = False) -> Path:
    """Ensure the buffalo_l models are on disk and return their directory."""
    target = buffalo_dir()
    if all((target / f).exists() for f in KEEP):
        return target

    from torch.hub import download_url_to_file

    settings.weights_dir.mkdir(parents=True, exist_ok=True)
    archive = settings.weights_dir / "buffalo_l.zip"
    if not archive.exists():
        print(f"Downloading buffalo_l -> {archive}")
        download_url_to_file(BUFFALO_L_URL, str(archive))

    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        for member in zf.namelist():
            name = Path(member).name
            if not name.endswith(".onnx"):
                continue
            if not keep_all and name not in KEEP:
                continue
            with zf.open(member) as src, (target / name).open("wb") as dst:
                dst.write(src.read())
            print(f"  extracted {name}")

    archive.unlink(missing_ok=True)
    missing = [f for f in KEEP if not (target / f).exists()]
    if missing:
        raise RuntimeError(f"buffalo_l pack is missing {missing}")
    return target


def detector_path() -> Path:
    return ensure_buffalo_l() / DETECTOR_FILE


def recognition_path() -> Path:
    return ensure_buffalo_l() / RECOGNITION_FILE
