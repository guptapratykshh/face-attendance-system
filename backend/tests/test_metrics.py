"""Metric helpers against analytically known ROCs."""

from __future__ import annotations

import numpy as np
from app.eval.metrics import accuracy_at_threshold, k_fold_accuracy, roc_curve, summarize


def test_perfect_separation_tar_and_eer():
    scores = np.array([0.95, 0.90, 0.85, 0.10, 0.05, 0.00])
    labels = np.array([1, 1, 1, 0, 0, 0])
    roc = roc_curve(scores, labels)
    tar, thr = roc.tar_at_far(1e-3)
    assert tar == 1.0
    assert thr >= 0.85
    eer, _ = roc.eer()
    assert eer == 0.0
    assert accuracy_at_threshold(scores, labels, 0.5) == 1.0


def test_tar_at_far_with_one_false_accept():
    # 100 genuine at 0.9, 99 impostors at 0.1, one impostor at 0.95.
    genuine = np.full(100, 0.9)
    impostor = np.concatenate([np.full(99, 0.1), np.array([0.95])])
    scores = np.concatenate([genuine, impostor])
    labels = np.concatenate([np.ones(100, dtype=np.int32), np.zeros(100, dtype=np.int32)])
    roc = roc_curve(scores, labels)
    tar_loose, _ = roc.tar_at_far(0.02)
    tar_strict, _ = roc.tar_at_far(0.005)
    assert tar_loose == 1.0
    assert tar_strict == 0.0  # cannot admit any genuine without taking the high impostor


def test_k_fold_accuracy_two_folds():
    scores = np.array([0.9, 0.2, 0.85, 0.15, 0.88, 0.1, 0.92, 0.05])
    labels = np.array([1, 0, 1, 0, 1, 0, 1, 0])
    folds = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    rec = k_fold_accuracy(scores, labels, folds)
    assert rec["n_folds"] == 2
    # A threshold that is optimal on one fold can sit between the other fold's genuine
    # scores, so mean accuracy is 0.875 rather than 1.0 — that is the protocol.
    assert rec["mean"] >= 0.75
    assert rec["per_fold"][0] >= 0.5


def test_summarize_payload_keys():
    rng = np.random.default_rng(0)
    genuine = rng.normal(0.7, 0.1, 200)
    impostor = rng.normal(0.2, 0.1, 200)
    scores = np.concatenate([genuine, impostor])
    labels = np.concatenate([np.ones(200, dtype=np.int32), np.zeros(200, dtype=np.int32)])
    folds = np.repeat(np.arange(10), 40)
    rec = summarize(scores, labels, folds)
    assert rec["n_pairs"] == 400
    assert "0.001" in rec["tar_at_far"]
    assert rec["accuracy"]["n_folds"] == 10
    assert 0 <= rec["eer"] <= 0.5
