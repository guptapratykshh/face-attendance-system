"""Virtual-camera detection from browser constraint-probe telemetry.

Blink and texture checks read the *content* of a stream. Neither can tell that OBS or ManyCam
replaced the webcam, because a real person driving a face swap blinks on cue. This module reads
the *source* instead: the frontend asks the track to change resolution and frame rate several
times, and we score how it reacted.

Real hardware negotiates with a driver. It clamps out-of-range requests, applies standard modes
faster than exotic ones, and the pixel dimensions the browser reports track what the video element
actually renders. Virtual cameras usually either accept everything (including impossible values) or
sit frozen at whatever the operator configured, and their response times are suspiciously uniform
because nothing is really being reconfigured.

The scorer is a transparent weighted rule set by default. If a trained gradient-boosting model has
been fitted by scripts/collect_capture_sessions.py it is used instead, and the rules become the
fallback for missing or malformed telemetry. That mirrors arXiv 2512.10653, which found data
quality mattered more than model choice.

Camera labels are deliberately ignored. The same paper found they are routinely renamed or blanked
by the attack tooling, so they look discriminative on collected data and fail in the wild.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from app.core.config import settings

MODEL_PATH = Path("weights/vcd_model.joblib")

# Heights a real sensor should manage, plus one it should refuse.
IN_RANGE_HEIGHTS = (240, 480, 720)
OVERSHOOT_HEIGHT = 3001
# 200 fps is beyond any commodity webcam; 1 fps is awkward for software cameras to honour.
OVERSHOOT_FPS = 200

_model: Any | None = None
_model_tried = False

FEATURE_ORDER = (
    "n_steps",
    "apply_fail_rate",
    "height_exact_rate",
    "height_distinct_reported",
    "height_max_reported",
    "height_overshoot_accepted",
    "height_actual_mismatch_rate",
    "height_resp_mean",
    "height_resp_cv",
    "fps_distinct_reported",
    "fps_max_reported",
    "fps_overshoot_accepted",
    "fps_reported_actual_gap",
    "fps_resp_mean",
    "fps_resp_cv",
    "resp_cv_all",
    "device_count",
    "duration_ms",
)


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return None if math.isnan(float(value)) or math.isinf(float(value)) else float(value)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _cv(values: list[float]) -> float | None:
    """Coefficient of variation. Near zero means every probe cost the same, which real drivers do not."""
    if len(values) < 2:
        return None
    mu = sum(values) / len(values)
    if mu <= 0:
        return None
    var = sum((v - mu) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var) / mu


def extract_features(report: dict) -> dict[str, float | None]:
    """Flatten a CaptureProbeReport into the numeric vector the scorer consumes."""
    steps = report.get("steps")
    steps = [s for s in steps if isinstance(s, dict)] if isinstance(steps, list) else []
    heights = [s for s in steps if s.get("kind") == "height"]
    fps_steps = [s for s in steps if s.get("kind") == "fps"]

    feats: dict[str, float | None] = dict.fromkeys(FEATURE_ORDER)
    feats["n_steps"] = float(len(steps))
    if steps:
        feats["apply_fail_rate"] = sum(0.0 if s.get("applied", True) else 1.0 for s in steps) / len(steps)

    # --- resolution ladder -------------------------------------------------
    h_reported = [r for r in (_num(s.get("reported")) for s in heights) if r is not None]
    if heights:
        in_range = [s for s in heights if s.get("requested") in IN_RANGE_HEIGHTS]
        if in_range:
            exact = sum(1.0 for s in in_range if _num(s.get("reported")) == _num(s.get("requested")))
            feats["height_exact_rate"] = exact / len(in_range)
        mismatches = [
            s
            for s in heights
            if _num(s.get("reported")) is not None and _num(s.get("actual")) is not None
        ]
        if mismatches:
            bad = sum(1.0 for s in mismatches if _num(s.get("reported")) != _num(s.get("actual")))
            feats["height_actual_mismatch_rate"] = bad / len(mismatches)
        over = next((s for s in heights if s.get("requested") == OVERSHOOT_HEIGHT), None)
        if over is not None:
            reported = _num(over.get("reported"))
            # A sensor that claims to deliver 3001 rows is not a sensor.
            feats["height_overshoot_accepted"] = 1.0 if reported is not None and reported >= OVERSHOOT_HEIGHT else 0.0
    if h_reported:
        feats["height_distinct_reported"] = float(len(set(h_reported)))
        feats["height_max_reported"] = max(h_reported)

    h_resp = [r for r in (_num(s.get("response_ms")) for s in heights) if r is not None]
    feats["height_resp_mean"] = _mean(h_resp)
    feats["height_resp_cv"] = _cv(h_resp)

    # --- frame-rate ladder -------------------------------------------------
    f_reported = [r for r in (_num(s.get("reported")) for s in fps_steps) if r is not None]
    if f_reported:
        feats["fps_distinct_reported"] = float(len(set(f_reported)))
        feats["fps_max_reported"] = max(f_reported)
    over_fps = next((s for s in fps_steps if s.get("requested") == OVERSHOOT_FPS), None)
    if over_fps is not None:
        reported = _num(over_fps.get("reported"))
        feats["fps_overshoot_accepted"] = 1.0 if reported is not None and reported >= 100 else 0.0

    gaps = [
        abs(_num(s.get("reported")) - _num(s.get("actual")))  # type: ignore[operator]
        for s in fps_steps
        if _num(s.get("reported")) is not None and _num(s.get("actual")) is not None
    ]
    feats["fps_reported_actual_gap"] = _mean(gaps)

    f_resp = [r for r in (_num(s.get("response_ms")) for s in fps_steps) if r is not None]
    feats["fps_resp_mean"] = _mean(f_resp)
    feats["fps_resp_cv"] = _cv(f_resp)
    feats["resp_cv_all"] = _cv(h_resp + f_resp)

    context = report.get("context") if isinstance(report.get("context"), dict) else {}
    feats["device_count"] = _num(context.get("device_count"))
    feats["duration_ms"] = _num(report.get("duration_ms"))
    return feats


def _rule_score(f: dict[str, float | None]) -> tuple[float, list[str]]:
    """Weighted evidence that the stream came from software. Returns [0, 1] and the cues that fired."""
    score = 0.0
    cues: list[str] = []

    if f.get("height_overshoot_accepted") == 1.0:
        score += 0.34
        cues.append("accepted an impossible resolution")
    if f.get("fps_overshoot_accepted") == 1.0:
        score += 0.26
        cues.append("accepted an impossible frame rate")

    distinct_h = f.get("height_distinct_reported")
    if distinct_h is not None and distinct_h <= 1 and (f.get("n_steps") or 0) >= 4:
        score += 0.20
        cues.append("resolution never changed")

    distinct_f = f.get("fps_distinct_reported")
    if distinct_f is not None and distinct_f <= 1 and (f.get("n_steps") or 0) >= 4:
        score += 0.12
        cues.append("frame rate never changed")

    cv = f.get("resp_cv_all")
    if cv is not None and cv < 0.12:
        # Real reconfiguration costs different amounts of time for different modes.
        score += 0.16
        cues.append("reconfiguration timings were unnaturally uniform")

    mismatch = f.get("height_actual_mismatch_rate")
    if mismatch is not None and mismatch >= 0.5:
        score += 0.14
        cues.append("reported resolution did not match the rendered frame")

    gap = f.get("fps_reported_actual_gap")
    if gap is not None and gap >= 25:
        score += 0.10
        cues.append("delivered frame rate did not match the reported one")

    return min(score, 1.0), cues


def _load_model() -> Any | None:
    global _model, _model_tried
    if _model_tried:
        return _model
    _model_tried = True
    if not MODEL_PATH.exists():
        return None
    try:
        import joblib

        _model = joblib.load(MODEL_PATH)
    except Exception:
        _model = None
    return _model


def _model_score(f: dict[str, float | None]) -> float | None:
    model = _load_model()
    if model is None:
        return None
    try:
        import numpy as np

        row = np.array([[float("nan") if f.get(k) is None else float(f[k]) for k in FEATURE_ORDER]])
        return float(model.predict_proba(row)[0][1])
    except Exception:
        # A broken artefact must not take check-in down; the rules still hold the line.
        return None


def analyse_capture_path(report: dict | str | None) -> dict | None:
    """Score one probe report. Returns None when no usable telemetry was supplied."""
    if isinstance(report, str):
        try:
            report = json.loads(report)
        except (ValueError, TypeError):
            return None
    if not isinstance(report, dict):
        return None

    features = extract_features(report)
    if not features.get("n_steps"):
        return None

    rule_score, cues = _rule_score(features)
    score = _model_score(features)
    source = "model"
    if score is None:
        score, source = rule_score, "rules"

    live = bool(score < settings.vcd_score_thresh)
    if live:
        reason = "capture path looks like real hardware"
    elif cues:
        reason = "virtual camera suspected: " + ", ".join(cues)
    else:
        reason = "virtual camera suspected"

    return {
        "live": live,
        "score": round(float(score), 4),
        "rule_score": round(float(rule_score), 4),
        "scored_by": source,
        "reason": reason,
        "cues": cues,
        "features": {k: (None if v is None else round(v, 4)) for k, v in features.items()},
    }
