"""Download the LFW dataset and the official verification protocol files.

The canonical host (vis-www.cs.umass.edu) is frequently unreachable, so this uses the
figshare mirrors that scikit-learn's `fetch_lfw_pairs` relies on.

Files fetched:
  lfw-funneled.tgz  images, funneled alignment
  pairs.txt         View 2 protocol: 10 folds x (300 matched + 300 mismatched) = 6000 pairs
  people.txt        identity -> image count, used for the training-overlap guard
"""

from __future__ import annotations

import argparse
import tarfile

from _common import PROJECT_ROOT, download, require_disk
from app.core.config import settings

MIRRORS = {
    "lfw-funneled.tgz": "https://ndownloader.figshare.com/files/5976015",
    "pairs.txt": "https://ndownloader.figshare.com/files/5976006",
    "pairsDevTrain.txt": "https://ndownloader.figshare.com/files/5976012",
    "pairsDevTest.txt": "https://ndownloader.figshare.com/files/5976009",
    "people.txt": "https://ndownloader.figshare.com/files/5976000",
}


def build_people_file() -> None:
    """Derive people.txt from the extracted directory tree if the mirror is unavailable."""
    people = settings.lfw_people
    if people.exists() and people.stat().st_size > 0:
        return
    root = settings.lfw_images_dir
    entries = sorted(
        (d.name, len(list(d.glob("*.jpg")))) for d in root.iterdir() if d.is_dir()
    )
    with people.open("w") as fh:
        fh.write(f"{len(entries)}\n")
        for name, count in entries:
            fh.write(f"{name}\t{count}\n")
    print(f"  derived people.txt with {len(entries)} identities")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep-archive", action="store_true", help="keep the .tgz after extraction")
    args = ap.parse_args()

    settings.ensure_dirs()
    lfw = settings.lfw_dir
    lfw.mkdir(parents=True, exist_ok=True)
    require_disk(PROJECT_ROOT, need_gb=1.0)

    print("Protocol files:")
    for name in ("pairs.txt", "pairsDevTrain.txt", "pairsDevTest.txt", "people.txt"):
        try:
            download(MIRRORS[name], lfw / name)
        except Exception as exc:  # people.txt mirror is the least reliable
            print(f"  WARN could not fetch {name}: {exc}")

    print("Images:")
    archive = lfw / "lfw-funneled.tgz"
    if not settings.lfw_images_dir.exists():
        download(MIRRORS["lfw-funneled.tgz"], archive)
        print("  extracting")
        with tarfile.open(archive) as tf:
            tf.extractall(lfw, filter="data")
        if not args.keep_archive:
            archive.unlink(missing_ok=True)
            print("  removed archive to save disk")
    else:
        print(f"  cached {settings.lfw_images_dir}")

    build_people_file()

    n_ids = sum(1 for d in settings.lfw_images_dir.iterdir() if d.is_dir())
    n_imgs = sum(1 for _ in settings.lfw_images_dir.rglob("*.jpg"))
    print(f"\nLFW ready: {n_ids} identities, {n_imgs} images at {settings.lfw_images_dir}")

    if settings.lfw_pairs.exists():
        lines = settings.lfw_pairs.read_text().strip().splitlines()
        print(f"pairs.txt header: {lines[0]!r}, {len(lines) - 1} pair lines")


if __name__ == "__main__":
    main()
