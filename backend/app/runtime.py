"""Process-wide handles: pipeline, gallery, calibrated thresholds, eval report."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings
from app.gallery.index import FaceGallery
from app.pipeline.face_pipeline import FacePipeline


def _load_eval_report() -> dict | None:
    path = settings.eval_report
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _encoder_from_report(report: dict | None) -> str:
    if report is None:
        return settings.encoder
    name = report.get("served_encoder") or settings.encoder
    # Config override wins when the operator set FRS_ENCODER explicitly to something
    # other than the default *and* it isn't just echoing the report.
    return name


def threshold_from_report(report: dict | None, encoder_name: str, far: str = "0.001") -> float | None:
    if not report:
        return None
    results = report.get("results") or {}
    rec = results.get(encoder_name)
    if rec is None:
        # served name may be facenet-finetuned / arcface-w600k_r50
        for key, value in results.items():
            if encoder_name in key or key in encoder_name:
                rec = value
                break
    if rec is None:
        return None
    tar = rec.get("tar_at_far") or {}
    point = tar.get(far) or tar.get("0.001")
    if not point:
        return None
    return float(point["threshold"])


@dataclass
class Runtime:
    pipeline: FacePipeline | None = None
    gallery: FaceGallery | None = None
    eval_report: dict | None = None
    verify_threshold: float = settings.verify_threshold
    identify_threshold: float = settings.identify_threshold
    encoder_name: str = settings.encoder
    extra: dict = field(default_factory=dict)

    def load_report(self) -> None:
        self.eval_report = _load_eval_report()
        if self.eval_report:
            served = _encoder_from_report(self.eval_report)
            # Honour an explicit non-default FRS_ENCODER.
            if settings.encoder in ("facenet", "arcface") and served:
                # Default config is facenet; prefer the report unless the operator
                # overrode via env. We treat any encoder other than the hardcoded
                # default as an override only when the env actually differs — the
                # settings object cannot tell, so we always prefer the report when
                # present and let FRS_ENCODER be set to the report name to pin it.
                self.encoder_name = settings.encoder if settings.encoder != "facenet" else served
            rec = (self.eval_report.get("results") or {}).get(self.encoder_name) or {}
            ckpt = rec.get("checkpoint")
            if ckpt:
                settings.facenet_checkpoint = Path(ckpt)
            thr = threshold_from_report(self.eval_report, self.encoder_name)
            if thr is not None:
                self.verify_threshold = thr
                self.identify_threshold = thr


runtime = Runtime()
