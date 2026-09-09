"""LFW verification protocol and TAR@FAR / ROC metrics."""

from app.eval.lfw import load_crops, load_pairs, score_pairs, unique_indices
from app.eval.metrics import FAR_TARGETS, RocCurve, k_fold_accuracy, roc_curve, summarize

__all__ = [
    "FAR_TARGETS",
    "RocCurve",
    "k_fold_accuracy",
    "load_crops",
    "load_pairs",
    "roc_curve",
    "score_pairs",
    "summarize",
    "unique_indices",
]
