"""LFW pair parsing against the on-disk protocol file."""

from __future__ import annotations

import json

import pytest
from app.core.config import settings
from app.eval.lfw import load_pairs, parse_pairs


def _require_protocol():
    if not settings.lfw_pairs.exists():
        pytest.skip("LFW protocol data not downloaded")


def test_parse_pairs_header():
    _require_protocol()
    n_folds, n_pairs, rows = parse_pairs()
    assert n_folds == 10
    assert n_pairs == 300
    assert len(rows) == 6000


def test_load_pairs_resolves_cache(tmp_path):
    _require_protocol()
    _, _, protocol = parse_pairs()
    paths = set()
    for row in protocol:
        if len(row) == 3:
            name, first, second = row
            paths.update((f"{name}/{name}_{first:04d}.jpg", f"{name}/{name}_{second:04d}.jpg"))
        else:
            first_name, first, second_name, second = row
            paths.update(
                (
                    f"{first_name}/{first_name}_{first:04d}.jpg",
                    f"{second_name}/{second_name}_{second:04d}.jpg",
                )
            )
    index = tmp_path / "lfw_index.json"
    index.write_text(json.dumps({"paths": sorted(paths)}))
    pairs = load_pairs(index_path=index)
    assert len(pairs) == 6000
    genuine = sum(p.label for p in pairs)
    assert genuine == 3000
    assert {p.fold for p in pairs} == set(range(10))
