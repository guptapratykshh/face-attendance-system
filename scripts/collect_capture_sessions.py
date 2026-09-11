#!/usr/bin/env python3
"""Export capture-path probe sessions and fit the virtual-camera detector.

Collection is manual and deliberately so - the whole point of the study is that the attack is
cheap, so the dataset has to be built by actually running it:

    1. Sit in front of a real webcam and check in normally, several times, across every browser
       and machine you can get hold of. These are the `bonafide` negatives.
    2. Install OBS Studio (free). Start its Virtual Camera and point it at a still photo of a
       face, then check in again. Label those `virtual_static`.
    3. Point the Virtual Camera at a pre-recorded video of a face. Label `virtual_replay`.
    4. If you can run a real-time face swap into OBS, label those `virtual_faceswap`. This is the
       case that defeats blink detection, so it matters most.

Label a session by passing `label` alongside the probe on POST /liveness/check, or by tagging rows
afterwards with `--tag`.

    python scripts/collect_capture_sessions.py --export data/vcd_sessions.jsonl
    python scripts/collect_capture_sessions.py --tag virtual_faceswap --since 2026-09-11T14:00
    python scripts/collect_capture_sessions.py --fit weights/vcd_model.joblib

Fitting needs scikit-learn, which is already a dependency via the evaluation stack.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from _common import PROJECT_ROOT  # noqa: F401  (puts backend/ on sys.path)
from app.core.config import settings
from app.db.models import CaptureProbe
from app.liveness.capture_path import FEATURE_ORDER, extract_features
from sqlmodel import Session, col, create_engine, select

ATTACK_LABELS = ("virtual_static", "virtual_replay", "virtual_faceswap")
BONAFIDE_LABEL = "bonafide"


def _engine():
    return create_engine(settings.database_url, echo=False)


def _rows(session: Session, since: datetime | None) -> list[CaptureProbe]:
    stmt = select(CaptureProbe).order_by(col(CaptureProbe.created_at))
    if since is not None:
        stmt = stmt.where(col(CaptureProbe.created_at) >= since)
    return list(session.exec(stmt).all())


def export(path: Path, since: datetime | None) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with _engine().connect() as conn, Session(bind=conn) as session, path.open("w") as fh:
        for row in _rows(session, since):
            if not row.report_json:
                continue
            try:
                report = json.loads(row.report_json)
            except ValueError:
                continue
            fh.write(
                json.dumps(
                    {
                        "id": row.id,
                        "label": row.label,
                        "source": row.source,
                        "created_at": row.created_at.isoformat(),
                        "features": extract_features(report),
                        "report": report,
                    }
                )
                + "\n"
            )
            written += 1
    print(f"wrote {written} sessions to {path}")
    return written


def tag(label: str, since: datetime | None, only_untagged: bool) -> int:
    with _engine().connect() as conn, Session(bind=conn) as session:
        rows = _rows(session, since)
        touched = 0
        for row in rows:
            if only_untagged and row.label:
                continue
            row.label = label
            session.add(row)
            touched += 1
        session.commit()
    print(f"tagged {touched} sessions as {label}")
    return touched


def fit(out: Path, data: Path | None) -> None:
    """Train the gradient-boosting detector on labelled sessions."""
    try:
        import joblib
        import numpy as np
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import StratifiedKFold, cross_val_predict
    except ImportError as exc:  # pragma: no cover - depends on the optional extra
        raise SystemExit(f"fitting needs scikit-learn and joblib: {exc}") from exc

    records: list[dict] = []
    if data is not None:
        with data.open() as fh:
            records = [json.loads(line) for line in fh if line.strip()]
    else:
        with _engine().connect() as conn, Session(bind=conn) as session:
            for row in _rows(session, None):
                if not row.report_json or not row.label:
                    continue
                records.append({"label": row.label, "features": extract_features(json.loads(row.report_json))})

    labelled = [r for r in records if r.get("label") in (BONAFIDE_LABEL, *ATTACK_LABELS)]
    if len(labelled) < 40:
        raise SystemExit(
            f"only {len(labelled)} labelled sessions; collect more before fitting "
            "(the rule-based scorer stays in use until then)"
        )

    x = np.array(
        [[np.nan if r["features"].get(k) is None else float(r["features"][k]) for k in FEATURE_ORDER] for r in labelled]
    )
    y = np.array([0 if r["label"] == BONAFIDE_LABEL else 1 for r in labelled])
    if len(set(y.tolist())) < 2:
        raise SystemExit("need both bonafide and attack sessions to fit")

    model = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, random_state=0)
    folds = min(5, int(min(y.sum(), len(y) - y.sum())))
    if folds >= 2:
        probs = cross_val_predict(
            model, x, y, cv=StratifiedKFold(folds, shuffle=True, random_state=0), method="predict_proba"
        )[:, 1]
        print(f"cross-validated ROC-AUC: {roc_auc_score(y, probs):.4f}  (n={len(y)}, attacks={int(y.sum())})")
    else:
        print(f"too few per class for cross-validation (n={len(y)}); reporting training fit only")

    model.fit(x, y)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out)
    print(f"saved {out} - app.liveness.capture_path will pick it up on next start")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export", type=Path, help="write all probe sessions to a JSONL file")
    ap.add_argument("--tag", choices=[BONAFIDE_LABEL, *ATTACK_LABELS], help="label stored sessions")
    ap.add_argument("--since", help="ISO timestamp; limit --export/--tag to sessions after it")
    ap.add_argument("--all", action="store_true", help="with --tag, overwrite labels that are already set")
    ap.add_argument("--fit", type=Path, help="train the detector and save it here")
    ap.add_argument("--data", type=Path, help="fit from a JSONL export instead of the database")
    args = ap.parse_args()

    since = datetime.fromisoformat(args.since) if args.since else None
    if args.export:
        export(args.export, since)
    if args.tag:
        tag(args.tag, since, only_untagged=not args.all)
    if args.fit:
        fit(args.fit, args.data)
    if not (args.export or args.tag or args.fit):
        ap.error("pick at least one of --export, --tag, --fit")


if __name__ == "__main__":
    main()
