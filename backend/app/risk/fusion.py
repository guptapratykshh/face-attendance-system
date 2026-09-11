"""Fuse the four presence signals into one calibrated trust probability.

The four signals fail in different ways, which is the whole point of combining them:

- **face match** says who, and says nothing about whether the person is real or here
- **liveness / PAD** catches a photo or a screen, and is blind to an injected face swap
- **capture path** catches the injected face swap, and is blind to a real colleague punching for you
- **behaviour** catches the colleague, and is blind to a first-time attack

An attacker has to defeat all four at once. Any single one of them, deployed alone, has a
documented bypass.

Combining them is deliberately **not** a weighted average. An average lets a confident face match
outvote a failed capture path, which is exactly the attack we are trying to stop: a face swap
produces a *higher* similarity than a real user, because it is rendering an idealised face. The
requirement is conjunctive - every gate must hold - so this module does two things:

1. scores with a weighted **geometric** mean, where one near-zero signal drags the whole result
   down instead of being averaged away, and
2. applies a per-signal floor. Any signal below the floor vetoes the punch no matter how strong
   the others are, and the breakdown names which one did it.

Once scripts/evaluate_trust.py has fitted a calibrator on labelled sessions the score is mapped
through it, so `trust` really is P(genuine) and the threshold can be set from a target
false-accept rate rather than by taste.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from app.core.config import settings

CALIBRATOR_PATH = Path("weights/trust_calibrator.json")

_calibrator: dict | None = None
_calibrator_tried = False

SIGNALS = ("face", "pad", "vcd", "behaviour")


def _weights() -> dict[str, float]:
    raw = {
        "face": float(settings.trust_weight_face),
        "pad": float(settings.trust_weight_pad),
        "vcd": float(settings.trust_weight_vcd),
        "behaviour": float(settings.trust_weight_behaviour),
    }
    total = sum(raw.values())
    if total <= 0:
        return dict.fromkeys(SIGNALS, 0.25)
    return {k: v / total for k, v in raw.items()}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _geometric_mean(present: dict[str, float], weights: dict[str, float]) -> float:
    """Weighted geometric mean, so one failing gate cannot be averaged away by the others.

    Confidences are floored before the log because a signal reporting exactly zero would otherwise
    take the whole product to zero and erase the difference between "bad" and "catastrophic".
    """
    total = 0.0
    for name, confidence in present.items():
        total += weights[name] * math.log(max(confidence, 1e-4))
    return _clamp(math.exp(total))


def _face_confidence(similarity: float | None, threshold: float | None) -> float | None:
    """Map cosine similarity to [0, 1] around the operating threshold.

    A logistic centred on the calibrated threshold keeps the decision boundary where TAR@FAR put
    it, instead of inventing a second, inconsistent one.
    """
    if similarity is None:
        return None
    centre = float(threshold if threshold is not None else settings.identify_threshold)
    return _clamp(1.0 / (1.0 + math.exp(-12.0 * (float(similarity) - centre))))


def _load_calibrator() -> dict | None:
    global _calibrator, _calibrator_tried
    if _calibrator_tried:
        return _calibrator
    _calibrator_tried = True
    if not CALIBRATOR_PATH.exists():
        return None
    try:
        data = json.loads(CALIBRATOR_PATH.read_text())
        if isinstance(data, dict) and {"a", "b"} <= data.keys():
            _calibrator = data
    except (OSError, ValueError):
        _calibrator = None
    return _calibrator


def _calibrate(raw: float) -> tuple[float, bool]:
    """Platt scaling: sigmoid(a * raw + b), fitted on labelled sessions."""
    cal = _load_calibrator()
    if cal is None:
        return raw, False
    try:
        z = float(cal["a"]) * raw + float(cal["b"])
        return _clamp(1.0 / (1.0 + math.exp(-z))), True
    except (TypeError, ValueError, OverflowError):
        return raw, False


def presence_trust(
    *,
    similarity: float | None = None,
    threshold: float | None = None,
    liveness: dict[str, Any] | None = None,
    capture_path: dict[str, Any] | None = None,
    behaviour: dict[str, Any] | None = None,
) -> dict:
    """Return the fused trust probability plus a per-signal breakdown.

    Missing signals are dropped and the remaining weights renormalised, so a kiosk punch with no
    geolocation is scored on what it does have rather than being penalised for what it lacks.
    """
    weights = _weights()
    contributions: dict[str, dict[str, float | str | None]] = {}
    present: dict[str, float] = {}

    face = _face_confidence(similarity, threshold)
    if face is not None:
        present["face"] = face

    if liveness is not None:
        spoof = liveness.get("spoof_score")
        if isinstance(spoof, (int, float)):
            present["pad"] = _clamp(1.0 - float(spoof))
        elif isinstance(liveness.get("live"), bool):
            present["pad"] = 1.0 if liveness["live"] else 0.0

    if capture_path is not None:
        score = capture_path.get("score")
        if isinstance(score, (int, float)):
            present["vcd"] = _clamp(1.0 - float(score))

    if behaviour is not None:
        risk = behaviour.get("risk")
        if isinstance(risk, (int, float)):
            present["behaviour"] = _clamp(1.0 - float(risk))

    if not present:
        return {
            "trust": None,
            "decision": "unknown",
            "calibrated": False,
            "reason": "no signals available",
            "signals": {},
            "missing": list(SIGNALS),
        }

    total_weight = sum(weights[k] for k in present)
    raw = _geometric_mean(present, {k: weights[k] / total_weight for k in present})

    for name in SIGNALS:
        if name in present:
            share = weights[name] / total_weight
            contributions[name] = {
                "confidence": round(present[name], 4),
                "weight": round(share, 4),
                "vetoed": present[name] < float(settings.trust_signal_floor),
            }
        else:
            contributions[name] = {"confidence": None, "weight": 0.0, "vetoed": False}

    trust, calibrated = _calibrate(raw)

    # A single decisively failed gate blocks regardless of the score. Ordered by how directly the
    # signal proves the punch was fabricated, so the message names the most damning one.
    vetoes = [k for k in SIGNALS if k in present and present[k] < float(settings.trust_signal_floor)]
    passed = trust >= float(settings.trust_thresh) and not vetoes

    reasons = {
        "face": "face match is weak",
        "pad": "the frames look like a photo or a screen",
        "vcd": "the camera does not look like real hardware",
        "behaviour": "the punch does not fit this person's pattern",
    }
    weakest = min(present.items(), key=lambda kv: kv[1])[0]
    if passed:
        reason = "all presence signals agree"
    elif vetoes:
        reason = reasons[vetoes[0]]
    else:
        reason = reasons[weakest]

    return {
        "trust": round(trust, 4),
        "raw": round(raw, 4),
        "calibrated": calibrated,
        "decision": "accept" if passed else "review",
        "threshold": float(settings.trust_thresh),
        "floor": float(settings.trust_signal_floor),
        "reason": reason,
        "weakest_signal": weakest,
        "vetoed_by": vetoes,
        "signals": contributions,
        "missing": [k for k in SIGNALS if k not in present],
    }
