"""Identity-leakage guard between the VGGFace2 training pool and the LFW test set.

LFW is the benchmark, so any identity that appears in both the training subset and LFW
would inflate the reported accuracy. This resolves VGGFace2 class IDs (n000001) to real
names via VGGFace2's identity_meta.csv, normalises both name sets, and writes the
colliding class IDs to data/excluded_identities.txt so the downloader can skip them.

Run standalone to audit, or let download_vggface2_subset.py invoke it automatically.
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from pathlib import Path

from _common import PROJECT_ROOT  # noqa: F401  (path bootstrap)
from app.core.config import settings

VGGFACE2_META_REPO = "ProgramComputer/VGGFace2"
VGGFACE2_META_FILE = "meta/identity_meta.csv"


def normalise(name: str) -> str:
    """Fold a person name to a comparable key: ascii, lowercase, alphanumeric tokens only."""
    name = name.strip().strip('"').replace("_", " ")
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^a-zA-Z0-9 ]", " ", name)
    return " ".join(name.lower().split())


def load_vggface2_names() -> dict[str, str]:
    """class_id -> raw name, downloaded from the VGGFace2 metadata mirror."""
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(VGGFACE2_META_REPO, VGGFACE2_META_FILE, repo_type="dataset")
    mapping: dict[str, str] = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        reader = csv.reader(fh, skipinitialspace=True)
        next(reader, None)  # header
        for row in reader:
            if len(row) < 2:
                continue
            mapping[row[0].strip()] = row[1].strip().strip('"')
    return mapping


def load_lfw_names() -> list[str]:
    """Identity directory names from LFW, e.g. Aaron_Eckhart."""
    if settings.lfw_images_dir.exists():
        return sorted(d.name for d in settings.lfw_images_dir.iterdir() if d.is_dir())
    if settings.lfw_people.exists():
        names = []
        for line in settings.lfw_people.read_text().splitlines()[1:]:
            parts = line.split("\t")
            if parts and parts[0].strip():
                names.append(parts[0].strip())
        return names
    raise SystemExit("LFW not found. Run scripts/download_lfw.py first.")


def compute_excluded() -> tuple[set[str], dict[str, str]]:
    """Return (colliding vggface2 class_ids, class_id -> matched lfw name)."""
    vgg = load_vggface2_names()
    lfw = load_lfw_names()
    lfw_index: dict[str, str] = {}
    for name in lfw:
        lfw_index.setdefault(normalise(name), name)

    excluded: set[str] = set()
    matches: dict[str, str] = {}
    for class_id, raw in vgg.items():
        key = normalise(raw)
        if key and key in lfw_index:
            excluded.add(class_id)
            matches[class_id] = lfw_index[key]
    return excluded, matches


def exclusion_file() -> Path:
    return settings.data_dir / "excluded_identities.txt"


def write_exclusions(excluded: set[str], matches: dict[str, str]) -> Path:
    out = exclusion_file()
    out.parent.mkdir(parents=True, exist_ok=True)
    vgg = load_vggface2_names()
    with out.open("w") as fh:
        fh.write("# VGGFace2 class IDs whose identity also appears in LFW. Excluded from training.\n")
        fh.write("# class_id\tvggface2_name\tlfw_name\n")
        for class_id in sorted(excluded):
            fh.write(f"{class_id}\t{vgg.get(class_id, '?')}\t{matches.get(class_id, '?')}\n")
    return out


def load_exclusions() -> set[str]:
    """Read the exclusion list, computing it on first use."""
    path = exclusion_file()
    if not path.exists():
        excluded, matches = compute_excluded()
        write_exclusions(excluded, matches)
        return excluded
    return {
        line.split("\t")[0].strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--show", type=int, default=15, help="how many collisions to print")
    args = ap.parse_args()

    vgg = load_vggface2_names()
    lfw = load_lfw_names()
    excluded, matches = compute_excluded()
    out = write_exclusions(excluded, matches)

    print(f"VGGFace2 identities: {len(vgg)}")
    print(f"LFW identities:      {len(lfw)}")
    print(f"Overlapping:         {len(excluded)}  ({100 * len(excluded) / len(vgg):.1f}% of VGGFace2)")
    print(f"\nExclusion list -> {out}")
    if excluded:
        print(f"\nFirst {args.show} collisions:")
        for class_id in sorted(excluded)[: args.show]:
            print(f"  {class_id}  {vgg[class_id]:<32} == LFW/{matches[class_id]}")


if __name__ == "__main__":
    main()
