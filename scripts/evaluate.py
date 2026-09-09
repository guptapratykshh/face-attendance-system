"""Run the LFW View 2 protocol for one or more encoders and write TAR@FAR reports.

Embeds each unique LFW crop once, then scores the 6,000 protocol pairs. Crops are the
cached aligned arrays, so FaceNet and ArcFace differ only by the encoder.

Usage:
    python scripts/evaluate.py
    python scripts/evaluate.py --encoders facenet arcface
    python scripts/evaluate.py --encoders facenet --checkpoint checkpoints/facenet_arcface.pt
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from _common import PROJECT_ROOT
from app.core.config import settings
from app.encoders import get_encoder
from app.eval.lfw import load_crops, load_pairs, score_pairs, unique_indices
from app.eval.metrics import FAR_TARGETS, summarize
from app.eval.report import write_report

ENC_SIZE = {"facenet": 160, "arcface": 112, "facenet-finetuned": 160}


def embed_unique(encoder, crops: np.ndarray, indices: np.ndarray, batch_size: int = 32) -> np.ndarray:
    """Embed `crops[indices]` and scatter them back into a (N, dim) table keyed by crop index."""
    table = np.zeros((len(crops), encoder.dim), dtype=np.float32)
    n = len(indices)
    for start in range(0, n, batch_size):
        chunk = indices[start : start + batch_size]
        batch = np.asarray(crops[chunk])
        table[chunk] = encoder.embed(batch)
        done = min(start + batch_size, n)
        print(f"\r  embedding {done}/{n}", end="", flush=True)
    print()
    return table


def downsample_roc(far, tar, n: int = 400) -> tuple[list[float], list[float]]:
    """Keep the ROC JSON payload small enough for the dashboard without losing shape."""
    if len(far) <= n:
        return [float(x) for x in far], [float(x) for x in tar]
    idx = np.linspace(0, len(far) - 1, n).astype(int)
    return [float(far[i]) for i in idx], [float(tar[i]) for i in idx]


def histogram_bins(genuine: np.ndarray, impostor: np.ndarray, bins: int = 40) -> dict:
    lo = float(min(genuine.min(), impostor.min()))
    hi = float(max(genuine.max(), impostor.max()))
    edges = np.linspace(lo, hi, bins + 1)
    g, _ = np.histogram(genuine, bins=edges, density=True)
    i, _ = np.histogram(impostor, bins=edges, density=True)
    centers = 0.5 * (edges[:-1] + edges[1:])
    return {
        "bin_centers": [float(x) for x in centers],
        "genuine": [float(x) for x in g],
        "impostor": [float(x) for x in i],
    }


def plot_encoder(name: str, scores: np.ndarray, labels: np.ndarray, summary: dict, out_dir: Path) -> None:
    genuine = scores[labels == 1]
    impostor = scores[labels == 0]
    roc = summary["roc"]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    fig.suptitle(f"{name} — LFW View 2", fontsize=12)

    ax = axes[0]
    ax.plot(roc["far"], roc["tar"], color="#2563eb", lw=2)
    ax.set_xscale("log")
    ax.set_xlim(1e-4, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("FAR")
    ax.set_ylabel("TAR")
    ax.set_title("ROC")
    ax.grid(True, which="both", alpha=0.3)
    for far, rec in summary["tar_at_far"].items():
        ax.axvline(float(far), color="#94a3b8", ls="--", lw=0.8)
        ax.scatter([float(far)], [rec["tar"]], color="#dc2626", zorder=5, s=20)

    ax = axes[1]
    ax.hist(impostor, bins=40, density=True, alpha=0.6, label="impostor", color="#f97316")
    ax.hist(genuine, bins=40, density=True, alpha=0.6, label="genuine", color="#16a34a")
    ax.set_xlabel("cosine similarity")
    ax.set_ylabel("density")
    ax.set_title("Score distributions")
    ax.legend(frameon=False)

    ax = axes[2]
    fars = list(summary["tar_at_far"].keys())
    tars = [summary["tar_at_far"][f]["tar"] for f in fars]
    ax.bar([f"FAR={f}" for f in fars], tars, color="#2563eb")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("TAR")
    ax.set_title("TAR@FAR")
    for i, t in enumerate(tars):
        ax.text(i, t + 0.02, f"{t:.3f}", ha="center", fontsize=9)

    fig.tight_layout()
    dest = out_dir / f"{name.replace('/', '_')}_lfw.png"
    fig.savefig(dest, dpi=140)
    plt.close(fig)


def plot_comparison(results: dict, out_dir: Path) -> None:
    names = list(results.keys())
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    fig.suptitle("Encoder comparison on LFW View 2", fontsize=12)

    ax = axes[0]
    for name, rec in results.items():
        roc = rec["roc"]
        ax.plot(roc["far"], roc["tar"], lw=2, label=name)
    ax.set_xscale("log")
    ax.set_xlim(1e-4, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("FAR")
    ax.set_ylabel("TAR")
    ax.set_title("ROC")
    ax.legend(frameon=False)
    ax.grid(True, which="both", alpha=0.3)

    ax = axes[1]
    fars = [f"{f:g}" for f in FAR_TARGETS]
    x = np.arange(len(fars))
    width = 0.8 / max(len(names), 1)
    for i, name in enumerate(names):
        tars = [results[name]["tar_at_far"][f]["tar"] for f in fars]
        ax.bar(x + i * width, tars, width, label=name)
    ax.set_xticks(x + width * (len(names) - 1) / 2)
    ax.set_xticklabels([f"FAR={f}" for f in fars])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("TAR")
    ax.set_title("TAR@FAR")
    ax.legend(frameon=False)

    fig.tight_layout()
    fig.savefig(out_dir / "comparison_lfw.png", dpi=140)
    plt.close(fig)


def evaluate_encoder(name: str, checkpoint: Path | None, pairs, batch_size: int) -> tuple[dict, np.ndarray, np.ndarray]:
    size = ENC_SIZE.get(name, 160)
    print(f"== {name} (crop {size}px) ==")
    encoder = get_encoder(name, checkpoint=checkpoint)
    crops = load_crops(size)
    indices = unique_indices(pairs)
    print(f"  {len(indices)} unique images, {len(pairs)} pairs, encoder={encoder}")
    embeddings = embed_unique(encoder, crops, indices, batch_size=batch_size)
    scores, labels, folds = score_pairs(embeddings, pairs)
    summary = summarize(scores, labels, folds)
    roc_far, roc_tar = downsample_roc(np.asarray(summary["roc"]["far"]), np.asarray(summary["roc"]["tar"]))
    summary["roc"] = {"far": roc_far, "tar": roc_tar}
    summary["score_histogram"] = histogram_bins(scores[labels == 1], scores[labels == 0])
    summary["encoder"] = encoder.name
    summary["dim"] = encoder.dim
    summary["input_size"] = encoder.input_size
    if checkpoint is not None:
        summary["checkpoint"] = str(checkpoint)
    acc = summary["accuracy"]
    print(
        f"  LFW accuracy {acc['mean'] * 100:.2f}% ± {acc['std'] * 100:.2f}%  "
        f"EER {summary['eer'] * 100:.2f}%"
    )
    for far, rec in summary["tar_at_far"].items():
        print(f"  TAR@FAR={far}: {rec['tar'] * 100:.2f}%  (thr={rec['threshold']:.4f})")
    return summary, scores, labels


def merge_reports(existing: dict | None, incoming: dict) -> dict:
    if not existing:
        return incoming
    merged = dict(existing)
    merged["generated_at"] = incoming["generated_at"]
    merged["protocol"] = incoming["protocol"]
    results = dict(existing.get("results", {}))
    results.update(incoming["results"])
    merged["results"] = results
    if "served_encoder" in incoming:
        merged["served_encoder"] = incoming["served_encoder"]
    return merged


def pick_served_encoder(results: dict) -> str:
    """Serve the encoder with the highest TAR at FAR=1e-3 (ties break toward facenet)."""
    best_name = None
    best_tar = -1.0
    for name, rec in results.items():
        tar = rec.get("tar_at_far", {}).get("0.001", {}).get("tar", -1.0)
        if tar > best_tar or (tar == best_tar and name == "facenet"):
            best_tar = tar
            best_name = name
    return best_name or "facenet"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--encoders", nargs="+", default=["facenet", "arcface"])
    ap.add_argument("--checkpoint", type=Path, default=None, help="FaceNet fine-tune weights")
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--merge", action="store_true", help="merge into existing evaluation.json")
    args = ap.parse_args()

    settings.ensure_dirs()
    figures = settings.reports_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    pairs = load_pairs()
    results: dict[str, dict] = {}
    score_cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for name in args.encoders:
        ckpt = args.checkpoint if name in ("facenet", "facenet-finetuned") else None
        summary, scores, labels = evaluate_encoder(name, ckpt, pairs, args.batch_size)
        key = summary["encoder"]
        results[key] = summary
        score_cache[key] = (scores, labels)
        plot_encoder(key, scores, labels, summary, figures)

    plot_comparison({k: v for k, v in results.items()}, figures)

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol": {
            "name": "LFW View 2",
            "n_folds": 10,
            "pairs_per_fold": 600,
            "n_pairs": len(pairs),
            "far_targets": list(FAR_TARGETS),
            "metric": "cosine similarity on L2-normalised embeddings",
        },
        "results": results,
        "served_encoder": pick_served_encoder(results),
        "figures": [str(p.relative_to(PROJECT_ROOT)) for p in sorted(figures.glob("*.png"))],
    }

    dest = settings.eval_report
    if args.merge and dest.exists():
        existing = json.loads(dest.read_text())
        payload = merge_reports(existing, payload)
        payload["served_encoder"] = pick_served_encoder(payload["results"])

    dest.write_text(json.dumps(payload, indent=2))
    md = write_report(payload)
    print(f"\nWrote {dest}")
    print(f"Wrote {md}")
    print(f"Served encoder (best TAR@FAR=1e-3): {payload['served_encoder']}")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
