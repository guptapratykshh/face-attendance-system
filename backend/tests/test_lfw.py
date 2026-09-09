"""LFW pair parsing against the on-disk protocol file."""

from __future__ import annotations

from app.eval.lfw import load_pairs, parse_pairs


def test_parse_pairs_header():
    n_folds, n_pairs, rows = parse_pairs()
    assert n_folds == 10
    assert n_pairs == 300
    assert len(rows) == 6000


def test_load_pairs_resolves_cache():
    pairs = load_pairs()
    assert len(pairs) == 6000
    genuine = sum(p.label for p in pairs)
    assert genuine == 3000
    assert {p.fold for p in pairs} == set(range(10))
