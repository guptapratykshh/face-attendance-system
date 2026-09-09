"""Detect and align faces once, caching the crops for reuse.

Detection is the slowest stage and is encoder-independent, so it runs a single pass over
each dataset and writes aligned crops at every size the encoders need (160 for FaceNet,
112 for ArcFace). Both sizes come from the same landmarks, so the encoders are compared
on identical geometry rather than on incidentally different crops.

Outputs:
    data/cache/lfw_crops_<size>.npy   uint8 (N, size, size, 3)
    data/cache/lfw_index.json         image path order, plus detection failures
    data/train_aligned/<class>/*.jpg  aligned training crops (ImageFolder layout)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from _common import PROJECT_ROOT, human, require_disk
from app.core.config import settings
from app.pipeline.align import align_arcface, align_margin
from app.pipeline.detector import get_detector

CROP_SIZES = (160, 112)


def cache_dir() -> Path:
    d = settings.data_dir / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_rgb(path: Path) -> np.ndarray | None:
    bgr = cv2.imread(str(path))
    if bgr is None:
        return None
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def align_all_sizes(
    image: np.ndarray, landmarks: np.ndarray | None, bbox: np.ndarray | None, sizes=CROP_SIZES
) -> dict[int, np.ndarray]:
    out = {}
    for size in sizes:
        if landmarks is not None:
            out[size] = align_arcface(image, landmarks, size=size)
        else:
            # No landmarks: fall back to a centre crop so the image still contributes
            # instead of being silently dropped from the protocol.
            if bbox is None:
                h, w = image.shape[:2]
                c = 0.6
                bbox = np.array(
                    [w * (1 - c) / 2, h * (1 - c) / 2, w * (1 + c) / 2, h * (1 + c) / 2],
                    dtype=np.float32,
                )
            out[size] = align_margin(image, bbox, size=size, margin=0.0)
    return out


def prepare_lfw(force: bool = False) -> dict:
    """One detection pass over LFW, caching aligned crops at every encoder size."""
    index_path = cache_dir() / "lfw_index.json"
    crop_paths = {s: cache_dir() / f"lfw_crops_{s}.npy" for s in CROP_SIZES}
    if not force and index_path.exists() and all(p.exists() for p in crop_paths.values()):
        meta = json.loads(index_path.read_text())
        print(f"cached LFW crops for {meta['count']} images ({len(meta['failed'])} detection misses)")
        return meta

    paths = sorted(settings.lfw_images_dir.rglob("*.jpg"))
    if not paths:
        raise SystemExit("No LFW images. Run scripts/download_lfw.py first.")
    n = len(paths)
    require_disk(PROJECT_ROOT, need_gb=2.0)

    detector = get_detector()
    arrays = {
        s: np.lib.format.open_memmap(
            crop_paths[s], mode="w+", dtype=np.uint8, shape=(n, s, s, 3)
        )
        for s in CROP_SIZES
    }

    failed: list[str] = []
    multi = 0
    for i, path in enumerate(paths):
        image = read_rgb(path)
        if image is None:
            failed.append(str(path.relative_to(settings.lfw_images_dir)))
            continue
        dets = detector.detect(image)
        if not dets:
            failed.append(str(path.relative_to(settings.lfw_images_dir)))
            crops = align_all_sizes(image, None, None)
        else:
            if len(dets) > 1:
                multi += 1
            # LFW is centre-framed, so the largest box is the subject.
            best = dets[0]
            crops = align_all_sizes(image, best.landmarks, best.bbox)
        for s in CROP_SIZES:
            arrays[s][i] = crops[s]
        if (i + 1) % 500 == 0 or i + 1 == n:
            print(f"\r  {i + 1}/{n} images, {len(failed)} detection misses", end="", flush=True)
    print()

    for arr in arrays.values():
        arr.flush()

    meta = {
        "count": n,
        "sizes": list(CROP_SIZES),
        "paths": [str(p.relative_to(settings.lfw_images_dir)) for p in paths],
        "failed": failed,
        "multi_face_images": multi,
    }
    index_path.write_text(json.dumps(meta))
    total = sum(p.stat().st_size for p in crop_paths.values())
    print(
        f"LFW crops cached: {n} images, {len(failed)} fell back to a centre crop, "
        f"{multi} had multiple detections, {human(total)} on disk"
    )
    return meta


def prepare_train(size: int = 160, force: bool = False, quality: int = 95) -> dict:
    """Align the VGGFace2 training subset into an ImageFolder tree."""
    src_root = settings.train_dir
    dst_root = settings.data_dir / "train_aligned"
    if not src_root.exists():
        raise SystemExit("No training subset. Run scripts/download_vggface2_subset.py first.")
    if dst_root.exists() and any(dst_root.iterdir()) and not force:
        n_ids = sum(1 for d in dst_root.iterdir() if d.is_dir())
        n_img = sum(1 for _ in dst_root.rglob("*.jpg"))
        print(f"cached aligned training set: {n_ids} identities, {n_img} images")
        return {"identities": n_ids, "images": n_img}

    detector = get_detector()
    classes = sorted(d for d in src_root.iterdir() if d.is_dir())
    dst_root.mkdir(parents=True, exist_ok=True)
    kept = 0
    missed = 0
    for ci, class_dir in enumerate(classes):
        out_dir = dst_root / class_dir.name
        out_dir.mkdir(parents=True, exist_ok=True)
        for img_path in sorted(class_dir.glob("*.jpg")):
            image = read_rgb(img_path)
            if image is None:
                continue
            dets = detector.detect(image)
            if dets:
                crop = align_arcface(image, dets[0].landmarks, size=size)
            else:
                # These crops are already face-centred by the dataset, so a whole-image
                # resize is a reasonable fallback and keeps the class balanced.
                missed += 1
                crop = cv2.resize(image, (size, size), interpolation=cv2.INTER_AREA)
            cv2.imwrite(
                str(out_dir / img_path.name),
                cv2.cvtColor(crop, cv2.COLOR_RGB2BGR),
                [cv2.IMWRITE_JPEG_QUALITY, quality],
            )
            kept += 1
        print(f"\r  {ci + 1}/{len(classes)} identities, {kept} crops, {missed} misses", end="", flush=True)
    print()
    print(f"Aligned training set: {len(classes)} identities, {kept} images ({missed} detection misses)")
    return {"identities": len(classes), "images": kept, "missed": missed}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lfw", action="store_true", help="prepare LFW crops")
    ap.add_argument("--train", action="store_true", help="prepare training crops")
    ap.add_argument("--size", type=int, default=160, help="training crop size")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not args.lfw and not args.train:
        args.lfw = args.train = True

    settings.ensure_dirs()
    if args.lfw:
        print("== LFW ==")
        prepare_lfw(force=args.force)
    if args.train:
        print("\n== training subset ==")
        prepare_train(size=args.size, force=args.force)


if __name__ == "__main__":
    main()
