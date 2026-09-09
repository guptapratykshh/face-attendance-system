"""LFW View 2 verification protocol over the cached aligned crops.

`pairs.txt` is 10 folds of 300 genuine + 300 impostor pairs. Image paths in the cache
index are `{name}/{name}_{idx:04d}.jpg`, matching the LFW funneled layout.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.core.config import settings


@dataclass(frozen=True)
class Pair:
    fold: int
    label: int  # 1 genuine, 0 impostor
    idx_a: int
    idx_b: int
    path_a: str
    path_b: str


def _image_key(name: str, idx: int) -> str:
    return f"{name}/{name}_{idx:04d}.jpg"


def parse_pairs(pairs_path: Path | None = None) -> tuple[int, int, list[tuple]]:
    """Parse `pairs.txt`. Returns (n_folds, pairs_per_set, raw rows).

    Each raw row is either `(name, i, j)` (genuine) or `(name1, i, name2, j)` (impostor).
    """
    path = pairs_path or settings.lfw_pairs
    lines = path.read_text().splitlines()
    header = lines[0].split()
    n_folds, pairs_per_set = int(header[0]), int(header[1])
    rows: list[tuple] = []
    for line in lines[1:]:
        parts = line.split()
        if not parts:
            continue
        if len(parts) == 3:
            rows.append((parts[0], int(parts[1]), int(parts[2])))
        elif len(parts) == 4:
            rows.append((parts[0], int(parts[1]), parts[2], int(parts[3])))
        else:
            raise ValueError(f"unrecognised pairs.txt row: {line!r}")
    expected = n_folds * pairs_per_set * 2
    if len(rows) != expected:
        raise ValueError(f"expected {expected} pairs, parsed {len(rows)}")
    return n_folds, pairs_per_set, rows


def load_index(index_path: Path | None = None) -> dict[str, int]:
    path = index_path or (settings.data_dir / "cache" / "lfw_index.json")
    meta = json.loads(path.read_text())
    return {p: i for i, p in enumerate(meta["paths"])}


def load_pairs(
    pairs_path: Path | None = None,
    index_path: Path | None = None,
) -> list[Pair]:
    """Resolve protocol pairs onto crop-cache indices."""
    n_folds, pairs_per_set, rows = parse_pairs(pairs_path)
    lookup = load_index(index_path)
    pairs: list[Pair] = []
    missing: list[str] = []
    cursor = 0
    for fold in range(n_folds):
        genuine = rows[cursor : cursor + pairs_per_set]
        impostor = rows[cursor + pairs_per_set : cursor + 2 * pairs_per_set]
        cursor += 2 * pairs_per_set
        for name, i, j in genuine:
            ka, kb = _image_key(name, i), _image_key(name, j)
            if ka not in lookup or kb not in lookup:
                missing.append(f"{ka} | {kb}")
                continue
            pairs.append(Pair(fold, 1, lookup[ka], lookup[kb], ka, kb))
        for name1, i, name2, j in impostor:
            ka, kb = _image_key(name1, i), _image_key(name2, j)
            if ka not in lookup or kb not in lookup:
                missing.append(f"{ka} | {kb}")
                continue
            pairs.append(Pair(fold, 0, lookup[ka], lookup[kb], ka, kb))
    if missing:
        raise FileNotFoundError(
            f"{len(missing)} LFW pair images are absent from the crop cache "
            f"(first: {missing[0]})"
        )
    return pairs


def load_crops(size: int) -> np.ndarray:
    path = settings.data_dir / "cache" / f"lfw_crops_{size}.npy"
    if not path.exists():
        raise FileNotFoundError(
            f"missing {path}; run `python scripts/prepare_crops.py --lfw` first"
        )
    return np.load(path, mmap_mode="r")


def unique_indices(pairs: list[Pair]) -> np.ndarray:
    ids = {p.idx_a for p in pairs} | {p.idx_b for p in pairs}
    return np.fromiter(sorted(ids), dtype=np.int64)


def score_pairs(embeddings: np.ndarray, pairs: list[Pair]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cosine scores, labels, and fold ids for `pairs`, given a full crop-cache embedding table.

    `embeddings` is indexed the same way as the crop cache (row i = image i).
    """
    scores = np.empty(len(pairs), dtype=np.float64)
    labels = np.empty(len(pairs), dtype=np.int32)
    folds = np.empty(len(pairs), dtype=np.int32)
    for i, p in enumerate(pairs):
        scores[i] = float(np.dot(embeddings[p.idx_a], embeddings[p.idx_b]))
        labels[i] = p.label
        folds[i] = p.fold
    return scores, labels, folds
