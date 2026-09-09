"""Render reports/TAR_FAR_REPORT.md from evaluation.json."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings


def _pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def write_report(report: dict | None = None, dest: Path | None = None) -> Path:
    dest = dest or (settings.reports_dir / "TAR_FAR_REPORT.md")
    if report is None:
        report = json.loads(settings.eval_report.read_text())
    proto = report.get("protocol") or {}
    lines: list[str] = []
    lines.append("# TAR@FAR Report")
    lines.append("")
    lines.append(f"Generated: {report.get('generated_at', datetime.now(UTC).isoformat())}")
    lines.append(f"Protocol: {proto.get('name', 'LFW View 2')} — {proto.get('n_pairs', 6000)} pairs, "
                 f"{proto.get('n_folds', 10)}-fold accuracy.")
    lines.append("")
    lines.append("Grounding paper: Schroff, Kalenichenko, Philbin. "
                 "*FaceNet: A Unified Embedding for Face Recognition and Clustering*. CVPR 2015.")
    lines.append("")
    lines.append("Embeddings are L2-normalised; the score is cosine similarity. "
                 "The operating threshold served by the API is the cosine value that realises FAR = 1e-3 "
                 "on this protocol.")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| Encoder | LFW acc. (10-fold) | EER | TAR@FAR=1e-2 | TAR@FAR=1e-3 | TAR@FAR=1e-4 | Threshold (FAR=1e-3) |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for name, rec in report.get("results", {}).items():
        acc = rec.get("accuracy") or {}
        tar = rec.get("tar_at_far") or {}
        acc_s = f"{_pct(acc.get('mean', 0))} ± {_pct(acc.get('std', 0))}" if acc else "—"
        t01 = tar.get("0.01") or tar.get("0.010") or {}
        t001 = tar.get("0.001") or {}
        t0001 = tar.get("0.0001") or {}
        lines.append(
            f"| `{name}` | {acc_s} | {_pct(rec.get('eer', 0))} | "
            f"{_pct(t01.get('tar', 0))} | {_pct(t001.get('tar', 0))} | {_pct(t0001.get('tar', 0))} | "
            f"{t001.get('threshold', float('nan')):.4f} |"
        )
    lines.append("")
    served = report.get("served_encoder")
    if served:
        lines.append(f"**Served encoder:** `{served}` (highest TAR at FAR = 1e-3).")
        lines.append("")
    lines.append("## Score statistics")
    lines.append("")
    for name, rec in report.get("results", {}).items():
        g, i = rec.get("genuine") or {}, rec.get("impostor") or {}
        lines.append(f"### {name}")
        lines.append("")
        lines.append(f"- Genuine cosine: mean {g.get('mean', 0):.3f} ± {g.get('std', 0):.3f} "
                     f"[{g.get('min', 0):.3f}, {g.get('max', 0):.3f}]")
        lines.append(f"- Impostor cosine: mean {i.get('mean', 0):.3f} ± {i.get('std', 0):.3f} "
                     f"[{i.get('min', 0):.3f}, {i.get('max', 0):.3f}]")
        lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- FaceNet is the vendored Inception-ResNet-v1 checkpoint trained on VGGFace2 "
                 "(`20180402-114759-vggface2.pt`).")
    lines.append("- ArcFace is InsightFace `w600k_r50` (ResNet-50, WebFace600K) used as a published "
                 "reference, not trained here.")
    lines.append("- Fine-tuning uses an ArcFace head on a 402-identity VGGFace2 subset with LFW-overlapping "
                 "identities excluded. With only 402 classes the fine-tune is expected to trail the published "
                 "weights on LFW; that gap is the result, not a bug.")
    lines.append("- FAR = 1e-4 is below 1/3000 impostor pairs, so TAR@FAR=1e-4 is limited by protocol size.")
    lines.append("")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines))
    return dest
