"""ROC, TAR@FAR, EER, and the 10-fold LFW accuracy protocol.

All functions take cosine similarities in [-1, 1] (higher = more similar) and binary
labels (1 = genuine, 0 = impostor). Thresholds are on that same cosine scale.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

FAR_TARGETS = (1e-2, 1e-3, 1e-4)


@dataclass
class RocCurve:
    """A ROC sampled at every distinct score, plus interpolated TAR@FAR points."""

    thresholds: np.ndarray
    tar: np.ndarray
    far: np.ndarray
    n_genuine: int
    n_impostor: int

    def tar_at_far(self, far_target: float) -> tuple[float, float]:
        """Return (TAR, operating threshold) at the largest FAR that is still <= target.

        If every impostor scores below every genuine pair, FAR never rises above 0 and
        TAR is 1.0 at the lowest genuine score. If the target is below the smallest
        achievable FAR (one impostor / N), TAR is taken at that first non-zero FAR.
        """
        if far_target < 0 or far_target > 1:
            raise ValueError(f"FAR target must be in [0, 1], got {far_target}")
        if self.n_impostor == 0:
            raise ValueError("cannot compute TAR@FAR with no impostor pairs")

        far = self.far
        tar = self.tar
        thr = self.thresholds

        # Walk from high-FAR (low threshold) to low-FAR (high threshold). We want the
        # *highest* TAR whose FAR is still <= the target, which is the leftmost point
        # on the ROC that satisfies the constraint.
        eligible = np.where(far <= far_target)[0]
        if eligible.size == 0:
            # Target is stricter than the first operating point; take that point.
            idx = int(np.argmin(far))
            return float(tar[idx]), float(thr[idx])

        idx = int(eligible[np.argmax(tar[eligible])])
        return float(tar[idx]), float(thr[idx])

    def eer(self) -> tuple[float, float]:
        """Equal-error rate and the cosine threshold that realises it."""
        # EER is where FAR == FRR == 1 - TAR.
        frr = 1.0 - self.tar
        diff = self.far - frr
        # Sign change, or the closest point if they never cross.
        crossing = np.where(np.diff(np.signbit(diff)))[0]
        if crossing.size:
            i = int(crossing[0])
            # Linear interpolation between i and i+1.
            d0, d1 = float(diff[i]), float(diff[i + 1])
            if d1 == d0:
                alpha = 0.0
            else:
                alpha = d0 / (d0 - d1)
            eer = float(self.far[i] + alpha * (self.far[i + 1] - self.far[i]))
            thr = float(self.thresholds[i] + alpha * (self.thresholds[i + 1] - self.thresholds[i]))
            return eer, thr
        i = int(np.argmin(np.abs(diff)))
        return float((self.far[i] + frr[i]) / 2.0), float(self.thresholds[i])


def roc_curve(scores: np.ndarray, labels: np.ndarray) -> RocCurve:
    """Build a ROC by sweeping the cosine threshold from high (strict) to low (lax)."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int32)
    if scores.shape != labels.shape:
        raise ValueError(f"scores {scores.shape} and labels {labels.shape} differ")
    if scores.size == 0:
        raise ValueError("empty scores")

    n_genuine = int(labels.sum())
    n_impostor = int(labels.size - n_genuine)
    if n_genuine == 0 or n_impostor == 0:
        raise ValueError("need both genuine and impostor pairs")

    order = np.argsort(scores)[::-1]
    scores_s = scores[order]
    labels_s = labels[order]

    tp = np.cumsum(labels_s)
    fp = np.cumsum(1 - labels_s)
    tar = tp / n_genuine
    far = fp / n_impostor

    # Collapse runs of identical scores so each threshold is unique.
    _, first = np.unique(scores_s, return_index=True)
    # unique returns sorted ascending; we sorted descending, so reverse.
    keep = np.sort(first)
    return RocCurve(
        thresholds=scores_s[keep],
        tar=tar[keep],
        far=far[keep],
        n_genuine=n_genuine,
        n_impostor=n_impostor,
    )


def accuracy_at_threshold(scores: np.ndarray, labels: np.ndarray, threshold: float) -> float:
    pred = (scores >= threshold).astype(np.int32)
    return float(np.mean(pred == labels))


def best_accuracy_threshold(scores: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    """Threshold that maximises verification accuracy on `scores`/`labels`."""
    roc = roc_curve(scores, labels)
    accs = [
        accuracy_at_threshold(scores, labels, float(t)) for t in roc.thresholds
    ]
    i = int(np.argmax(accs))
    return float(roc.thresholds[i]), float(accs[i])


def k_fold_accuracy(
    scores: np.ndarray,
    labels: np.ndarray,
    folds: np.ndarray,
) -> dict:
    """Standard LFW View 2 protocol: pick the threshold on 9 folds, test on the held-out one."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int32)
    folds = np.asarray(folds, dtype=np.int32)
    fold_ids = np.unique(folds)
    fold_accs: list[float] = []
    fold_thresholds: list[float] = []
    for held_out in fold_ids:
        train = folds != held_out
        test = folds == held_out
        thr, _ = best_accuracy_threshold(scores[train], labels[train])
        acc = accuracy_at_threshold(scores[test], labels[test], thr)
        fold_accs.append(acc)
        fold_thresholds.append(thr)
    accs = np.asarray(fold_accs)
    return {
        "mean": float(accs.mean()),
        "std": float(accs.std(ddof=1) if len(accs) > 1 else 0.0),
        "per_fold": [float(a) for a in accs],
        "thresholds": fold_thresholds,
        "n_folds": int(len(fold_ids)),
    }


def summarize(
    scores: np.ndarray,
    labels: np.ndarray,
    folds: np.ndarray | None = None,
    far_targets: tuple[float, ...] = FAR_TARGETS,
) -> dict:
    """One evaluation payload: ROC, TAR@FAR, EER, score stats, optional 10-fold accuracy."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int32)
    roc = roc_curve(scores, labels)
    eer, eer_thr = roc.eer()
    genuine = scores[labels == 1]
    impostor = scores[labels == 0]
    tar_far = {}
    for far in far_targets:
        tar, thr = roc.tar_at_far(far)
        tar_far[f"{far:g}"] = {"tar": tar, "threshold": thr, "far_target": far}

    payload: dict = {
        "n_pairs": int(labels.size),
        "n_genuine": roc.n_genuine,
        "n_impostor": roc.n_impostor,
        "eer": eer,
        "eer_threshold": eer_thr,
        "tar_at_far": tar_far,
        "genuine": {
            "mean": float(genuine.mean()),
            "std": float(genuine.std()),
            "min": float(genuine.min()),
            "max": float(genuine.max()),
        },
        "impostor": {
            "mean": float(impostor.mean()),
            "std": float(impostor.std()),
            "min": float(impostor.min()),
            "max": float(impostor.max()),
        },
        "roc": {
            "far": roc.far.tolist(),
            "tar": roc.tar.tolist(),
            "thresholds": roc.thresholds.tolist(),
        },
    }
    if folds is not None:
        payload["accuracy"] = k_fold_accuracy(scores, labels, folds)
    return payload
