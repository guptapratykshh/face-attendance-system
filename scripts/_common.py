"""Shared helpers for the data and training scripts."""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

# Make `backend` importable when running scripts directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))

USER_AGENT = "face-recognition-system/0.1 (+https://github.com)"


def human(nbytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(nbytes) < 1024:
            return f"{nbytes:.1f}{unit}"
        nbytes /= 1024
    return f"{nbytes:.1f}TB"


def download(url: str, dest: Path, expected_sha256: str | None = None) -> Path:
    """Download `url` to `dest`, resuming is not attempted but re-downloads are skipped."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  cached {dest.name} ({human(dest.stat().st_size)})")
        return dest

    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    print(f"  fetching {url}")
    with urllib.request.urlopen(req, timeout=120) as resp, tmp.open("wb") as fh:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
            done += len(chunk)
            if total:
                pct = 100 * done / total
                print(f"\r  {human(done)}/{human(total)} ({pct:5.1f}%)", end="", flush=True)
            else:
                print(f"\r  {human(done)}", end="", flush=True)
    print()

    if expected_sha256:
        digest = sha256(tmp)
        if digest != expected_sha256:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"checksum mismatch for {url}: got {digest}")

    tmp.replace(dest)
    return dest


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def free_disk_gb(path: Path) -> float:
    import shutil

    return shutil.disk_usage(path).free / 1024**3


def require_disk(path: Path, need_gb: float) -> None:
    free = free_disk_gb(path)
    if free < need_gb:
        raise SystemExit(
            f"Not enough disk: {free:.1f} GB free at {path}, need ~{need_gb:.1f} GB. "
            "Free space or lower --max-identities."
        )
