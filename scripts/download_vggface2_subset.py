"""Build a disk-capped VGGFace2 training subset for fine-tuning.

Full VGGFace2 is ~19 GB across 40 parquet shards on this mirror, which does not fit the
available disk. Each shard holds ~78k images for ~215 identities (rows are label-sorted),
so downloading one or two shards and capping images-per-identity yields a usable subset.

Identities that also appear in LFW are skipped (see check_overlap.py) so the LFW
evaluation stays a genuine held-out benchmark.

Output layout, consumable by torchvision.datasets.ImageFolder:
    data/train/<class_id>/<nnnn>.jpg
    data/train/manifest.json
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
from pathlib import Path

from _common import PROJECT_ROOT, human, require_disk
from app.core.config import settings
from check_overlap import load_exclusions, load_vggface2_names

REPO = "chronopt-research/cropped-vggface2-224"
N_SHARDS = 40


def shard_name(i: int) -> str:
    return f"data/train-{i:05d}-of-{N_SHARDS:05d}.parquet"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--shards", type=int, default=2, help="how many parquet shards to pull")
    ap.add_argument("--max-identities", type=int, default=250, help="cap on identities kept")
    ap.add_argument("--images-per-identity", type=int, default=40, help="cap per identity")
    ap.add_argument("--min-images", type=int, default=12, help="drop identities below this count")
    ap.add_argument("--size", type=int, default=128, help="stored JPEG edge length")
    ap.add_argument("--quality", type=int, default=92, help="stored JPEG quality")
    ap.add_argument("--keep-cache", action="store_true", help="keep downloaded parquet shards")
    ap.add_argument("--force", action="store_true", help="rebuild even if output exists")
    args = ap.parse_args()

    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download
    from PIL import Image

    settings.ensure_dirs()
    out_root = settings.train_dir
    if out_root.exists() and any(out_root.iterdir()) and not args.force:
        n = sum(1 for d in out_root.iterdir() if d.is_dir())
        print(f"{out_root} already has {n} identities. Use --force to rebuild.")
        return
    if args.force and out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    require_disk(PROJECT_ROOT, need_gb=2.0)

    excluded = load_exclusions()
    names = load_vggface2_names()
    print(f"Excluding {len(excluded)} VGGFace2 identities that also appear in LFW.\n")

    kept: dict[str, int] = {}
    skipped_overlap = 0
    written = 0

    for shard_i in range(args.shards):
        if len(kept) >= args.max_identities:
            break
        fname = shard_name(shard_i)
        print(f"[shard {shard_i + 1}/{args.shards}] {fname}")
        path = Path(hf_hub_download(REPO, fname, repo_type="dataset"))
        print(f"  downloaded {human(path.stat().st_size)}")
        load_class_label_names(path)

        pf = pq.ParquetFile(path)
        for rg in range(pf.num_row_groups):
            table = pf.read_row_group(rg, columns=["image", "label"])
            labels = table.column("label").to_pylist()
            images = table.column("image").to_pylist()
            for label, img_struct in zip(labels, images, strict=True):
                class_id = names_key(label)
                if class_id in excluded:
                    skipped_overlap += 1
                    continue
                # Use .get() rather than kept[class_id]: indexing a defaultdict inserts the
                # key, which would make the identity cap below never fire.
                seen = kept.get(class_id, 0)
                if seen >= args.images_per_identity:
                    continue
                if class_id not in kept and len(kept) >= args.max_identities:
                    continue

                dest_dir = out_root / class_id
                dest_dir.mkdir(parents=True, exist_ok=True)
                idx = seen
                try:
                    with Image.open(io.BytesIO(img_struct["bytes"])) as im:
                        im = im.convert("RGB")
                        if args.size and max(im.size) > args.size:
                            im = im.resize((args.size, args.size), Image.LANCZOS)
                        im.save(dest_dir / f"{idx:04d}.jpg", "JPEG", quality=args.quality)
                except Exception as exc:
                    print(f"  WARN decode failed for {class_id}: {exc}")
                    continue
                kept[class_id] = seen + 1
                written += 1
            print(
                f"\r  rowgroup {rg + 1}/{pf.num_row_groups}: "
                f"{len(kept)} identities, {written} images",
                end="",
                flush=True,
            )
        print()
        if not args.keep_cache:
            # hf_hub_download stores a blob plus a symlink; unlink both.
            blob = path.resolve()
            path.unlink(missing_ok=True)
            blob.unlink(missing_ok=True)
            print("  cleared shard from HF cache")

    # Drop identities with too few images: they hurt more than help in a classification head.
    dropped = []
    for class_id, count in list(kept.items()):
        if count < args.min_images:
            shutil.rmtree(out_root / class_id, ignore_errors=True)
            dropped.append(class_id)
            del kept[class_id]
    if dropped:
        print(f"\nDropped {len(dropped)} identities with < {args.min_images} images")

    manifest = {
        "source": REPO,
        "shards_used": args.shards,
        "identities": len(kept),
        "images": sum(kept.values()),
        "images_per_identity_cap": args.images_per_identity,
        "min_images": args.min_images,
        "image_size": args.size,
        "excluded_lfw_overlap_identities": len(excluded),
        "skipped_images_from_overlap": skipped_overlap,
        "class_names": {cid: names.get(cid, cid) for cid in sorted(kept)},
        "counts": dict(sorted(kept.items())),
    }
    (out_root / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    total_bytes = sum(f.stat().st_size for f in out_root.rglob("*.jpg"))
    print(
        f"\nTraining subset ready: {len(kept)} identities, {sum(kept.values())} images, "
        f"{human(total_bytes)} on disk"
    )
    print(f"  skipped {skipped_overlap} images from LFW-overlapping identities")
    print(f"  -> {out_root}")


_NAMES_CACHE: list[str] | None = None


def names_key(label: int) -> str:
    """Map an integer ClassLabel index to the VGGFace2 class id (n000001 style)."""
    global _NAMES_CACHE
    if _NAMES_CACHE is None:
        _NAMES_CACHE = load_class_label_names()
    if 0 <= label < len(_NAMES_CACHE):
        return _NAMES_CACHE[label]
    return f"unknown_{label}"


def load_class_label_names(shard_path: Path | None = None) -> list[str]:
    """ClassLabel `names` from the parquet schema, cached locally.

    The names live in shard metadata, so they are persisted to disk on first read: the
    shards themselves are deleted after extraction and must not be re-fetched for 100 KB
    of metadata.
    """
    global _NAMES_CACHE
    cache = settings.data_dir / "vggface2_class_names.json"
    if cache.exists():
        _NAMES_CACHE = json.loads(cache.read_text())
        return _NAMES_CACHE

    import pyarrow.parquet as pq

    if shard_path is None:
        from huggingface_hub import hf_hub_download

        shard_path = Path(hf_hub_download(REPO, shard_name(0), repo_type="dataset"))
    meta = json.loads(pq.ParquetFile(shard_path).schema_arrow.metadata[b"huggingface"].decode())
    names = meta["info"]["features"]["label"]["names"]
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(names))
    _NAMES_CACHE = names
    return names


if __name__ == "__main__":
    main()
