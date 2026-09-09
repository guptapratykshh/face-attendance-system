"""Blink detector from eye-patch appearance (vertical texture + pupil darkness).

MediaPipe Face Landmarker 1.x aborts on Apple Silicon Metal, and 106-point
landmark regressors still predict open eyelids on closed eyes. The blink
challenge therefore scores the two eye crops from SCRFD's 5-point landmarks:
open eyes have strong vertical gradients (iris / lid) and a dark pupil;
closed lids are smoother and more uniform. `blink_from_ears` then looks for
an open → closed → open transition, with a relative-drop fallback so the
same logic works when absolute EAR-style thresholds do not match the scale.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.core.config import settings

# Webcam blinks only move this appearance score ~10–15% (the crop still contains
# lid/skin texture). 22% was rejecting real blinks; still photos stay at ~0%.
_MIN_RELATIVE_DROP = 0.10
_MIN_VALLEY_DROP = 0.08
# Tight crop around SCRFD eye centres so a blink actually changes the score.
_EYE_WIDTH_FRAC = 0.24
_EYE_HEIGHT_FRAC = 0.14


def _eye_openness(gray: np.ndarray, eye_xy: np.ndarray, face_width: float, face_height: float) -> float | None:
    w = max(10.0, face_width * _EYE_WIDTH_FRAC)
    h = max(8.0, face_height * _EYE_HEIGHT_FRAC)
    cx, cy = float(eye_xy[0]), float(eye_xy[1])
    x1, y1 = int(cx - w / 2), int(cy - h / 2)
    x2, y2 = int(cx + w / 2), int(cy + h / 2)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(gray.shape[1], x2), min(gray.shape[0], y2)
    patch = gray[y1:y2, x1:x2]
    if patch.size < 40:
        return None
    yy, xx = np.ogrid[: patch.shape[0], : patch.shape[1]]
    mask = ((yy - patch.shape[0] / 2.0) / max(patch.shape[0] / 2.0, 1.0)) ** 2 + (
        (xx - patch.shape[1] / 2.0) / max(patch.shape[1] / 2.0, 1.0)
    ) ** 2 <= 1.0
    if int(mask.sum()) < 20:
        return None
    gy = cv2.Sobel(patch, cv2.CV_64F, 0, 1, ksize=3)
    mag = float(np.mean(np.abs(gy)[mask]))
    sobel_term = mag / (mag + 18.0)
    values = patch.astype(np.float64)
    cy_i, cx_i = patch.shape[0] // 2, patch.shape[1] // 2
    r = max(2, min(cy_i, cx_i) // 2)
    center = float(values[cy_i - r : cy_i + r, cx_i - r : cx_i + r].mean())
    surround = float(values[mask].mean())
    darkness = max(0.0, (surround - center) / (surround + 1e-6))
    # Open pupils are darker than the lid; invert brightness of the centre.
    brightness_term = 1.0 - float(np.clip(center / 180.0, 0.0, 1.0))
    return float(0.50 * sobel_term + 0.30 * darkness + 0.20 * brightness_term)


def ear_from_image(image_rgb: np.ndarray) -> float | None:
    """Openness in roughly the same 0–1 range as classic EAR, or None if no face."""
    from app.pipeline.detector import get_detector

    if image_rgb.dtype != np.uint8:
        image_rgb = np.clip(image_rgb, 0, 255).astype(np.uint8)
    detections = get_detector().detect(image_rgb, max_num=1)
    if not detections:
        return None
    det = detections[0]
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    scores = []
    for eye in det.landmarks[:2]:
        score = _eye_openness(gray, eye, det.width, det.height)
        if score is not None:
            scores.append(score)
    if not scores:
        return None
    return float(sum(scores) / len(scores))


def _transition(values: list[float], closed_t: float, open_t: float) -> bool:
    saw_open = False
    saw_closed = False
    blinked = False
    for ear in values:
        if ear >= open_t:
            if saw_closed:
                blinked = True
            saw_open = True
        elif ear <= closed_t and saw_open:
            saw_closed = True
    return blinked


def _has_valley(values: list[float], min_drop: float) -> bool:
    """True if a trough sits between higher frames on both sides (a real blink)."""
    if len(values) < 4:
        return False
    arr = np.asarray(values, dtype=np.float64)
    baseline = float(np.percentile(arr, 75))
    trough = float(arr.min())
    if baseline < 1e-6:
        return False
    if (baseline - trough) / baseline < min_drop:
        return False
    i = int(arr.argmin())
    left = arr[:i]
    right = arr[i + 1 :]
    if left.size == 0 or right.size == 0:
        return False
    recover = trough + 0.45 * (baseline - trough)
    return float(left.max()) >= recover and float(right.max()) >= recover


def blink_from_ears(
    ears: list[float | None],
    closed_thresh: float | None = None,
    open_thresh: float | None = None,
) -> dict:
    """Detect an open -> closed -> open transition in a short EAR sequence."""
    closed_thresh = settings.ear_closed_thresh if closed_thresh is None else closed_thresh
    open_thresh = settings.ear_open_thresh if open_thresh is None else open_thresh
    values = [e for e in ears if e is not None]
    if len(values) < 3:
        return {
            "blink": False,
            "reason": "need at least 3 frames with a detectable face",
            "n_valid": len(values),
            "min_ear": None,
            "max_ear": None,
        }

    blinked = _transition(values, closed_thresh, open_thresh)
    vmax, vmin = max(values), min(values)
    drop = (vmax - vmin) / vmax if vmax > 1e-6 else 0.0
    if not blinked and drop >= _MIN_RELATIVE_DROP:
        mid_low = vmin + 0.35 * (vmax - vmin)
        mid_high = vmin + 0.65 * (vmax - vmin)
        blinked = _transition(values, mid_low, mid_high)
    if not blinked:
        blinked = _has_valley(values, _MIN_VALLEY_DROP)
    return {
        "blink": blinked,
        "reason": "blink detected" if blinked else "no open-closed-open transition",
        "n_valid": len(values),
        "min_ear": float(vmin),
        "max_ear": float(vmax),
        "ears": [None if e is None else round(float(e), 4) for e in ears],
    }


def timed_blink(hold_ears: list[float | None], action_ears: list[float | None]) -> dict:
    """Detect a blink in the challenge clip.

    A still photo never blinks. A live person often blinks a little early while
    waiting for the prompt; that is not a replay. Photo/screen recapture is the
    texture/frozen check, not blink timing.
    """
    hold = blink_from_ears(hold_ears)
    action = blink_from_ears(action_ears)
    combined = blink_from_ears([*hold_ears, *action_ears])
    if action["blink"]:
        reason = "blink after prompt"
    elif hold["blink"] or combined["blink"]:
        reason = "blink detected"
    else:
        return {
            "blink": False,
            "timed_ok": False,
            "reason": action.get("reason") or "no blink after the prompt",
            "hold": hold,
            "action": action,
            "min_ear": action.get("min_ear"),
            "max_ear": action.get("max_ear"),
        }
    return {
        "blink": True,
        "timed_ok": bool(action["blink"]),
        "reason": reason,
        "hold": hold,
        "action": action,
        "min_ear": action.get("min_ear"),
        "max_ear": action.get("max_ear"),
    }
