"""Passive print/replay cues from crops and short bursts.

This is a lightweight heuristic, not a certified PAD system. It scores signals
that recaptured photos and phone/tablet/laptop screens tend to show: missing
high-frequency texture, periodic FFT peaks (moiré / pixel grid), oversaturated
colour, and near-identical frames (a still photo or paused video).
"""

from __future__ import annotations

import cv2
import numpy as np

from app.core.config import settings


def _gray(crop_rgb: np.ndarray) -> np.ndarray:
    if crop_rgb.ndim == 2:
        return crop_rgb
    return cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2GRAY)


def _small(gray: np.ndarray, size: int = 96) -> np.ndarray:
    h, w = gray.shape[:2]
    if max(h, w) <= size:
        return gray
    scale = size / max(h, w)
    return cv2.resize(gray, (max(8, int(w * scale)), max(8, int(h * scale))), interpolation=cv2.INTER_AREA)


def _high_freq_ratio(gray: np.ndarray) -> float:
    f = np.fft.fftshift(np.fft.fft2(gray.astype(np.float32)))
    mag = np.abs(f)
    h, w = mag.shape
    cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]
    radius = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    max_r = min(h, w) / 2
    low = mag[radius < 0.12 * max_r].mean()
    high = mag[radius > 0.30 * max_r].mean()
    return float(high / (low + 1e-6))


def _moire_peak(gray: np.ndarray) -> float:
    """Peak-to-median energy in a mid-frequency FFT ring; screens produce spikes."""
    f = np.fft.fftshift(np.fft.fft2(gray.astype(np.float32)))
    mag = np.log1p(np.abs(f))
    h, w = mag.shape
    cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]
    radius = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    max_r = min(h, w) / 2
    ring = mag[(radius > 0.15 * max_r) & (radius < 0.45 * max_r)]
    if ring.size == 0:
        return 0.0
    median = float(np.median(ring))
    peak = float(np.percentile(ring, 99))
    return float((peak - median) / (median + 1e-6))


def _grid_score(gray: np.ndarray) -> float:
    """Regular horizontal/vertical FFT peaks from phone and laptop pixels."""
    small = _small(gray, 128).astype(np.float32)
    scores = []
    for axis in (0, 1):
        profile = small.mean(axis=axis)
        profile = profile - float(profile.mean())
        if profile.size < 16:
            continue
        mag = np.abs(np.fft.rfft(profile))
        if mag.size < 6:
            continue
        body = mag[2:]
        peak = float(body.max())
        med = float(np.median(body) + 1e-6)
        scores.append(peak / med)
    if not scores:
        return 0.0
    return float(np.clip((max(scores) - 6.0) / 10.0, 0.0, 1.0))


def _saturation_term(crop_rgb: np.ndarray) -> float:
    if crop_rgb.ndim < 3 or crop_rgb.shape[2] < 3:
        return 0.0
    hsv = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2HSV)
    sat = hsv[:, :, 1].astype(np.float32).mean() / 255.0
    return float(np.clip((sat - 0.42) / 0.35, 0.0, 1.0))


def spoof_analysis(crop_rgb: np.ndarray) -> dict:
    """Return a spoof likelihood in [0, 1] plus the cues that produced it."""
    if crop_rgb.size == 0:
        return {"spoof_score": 1.0, "live": False, "reason": "empty crop"}
    gray = _gray(crop_rgb)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    hf = _high_freq_ratio(gray)
    moire = _moire_peak(gray)
    grid = _grid_score(gray)
    sat = _saturation_term(crop_rgb)

    # Live faces sit around hf ~ 0.15-0.4, blur_var > 20, moire < 1.5.
    blur_term = 1.0 / (1.0 + blur / 18.0)
    hf_term = 1.0 / (1.0 + hf / 0.12)
    moire_term = min(1.0, max(0.0, (moire - 0.8) / 2.0))
    spoof = float(
        np.clip(
            0.32 * blur_term + 0.22 * hf_term + 0.22 * moire_term + 0.16 * grid + 0.08 * sat,
            0.0,
            1.0,
        )
    )
    live = bool(spoof < settings.spoof_score_thresh)
    return {
        "spoof_score": round(spoof, 4),
        "live": live,
        "blur_var": round(blur, 2),
        "high_freq_ratio": round(hf, 4),
        "moire": round(moire, 4),
        "grid": round(grid, 4),
        "saturation": round(sat, 4),
        "reason": "looks live" if live else "texture cues look like a recapture",
    }


def _mean_frame_delta(frames: list[np.ndarray]) -> float:
    if len(frames) < 2:
        return 99.0
    deltas = []
    prev = _small(_gray(frames[0])).astype(np.float32)
    for im in frames[1:]:
        cur = _small(_gray(im)).astype(np.float32)
        if cur.shape != prev.shape:
            cur = cv2.resize(cur, (prev.shape[1], prev.shape[0]), interpolation=cv2.INTER_AREA)
        deltas.append(float(np.mean(np.abs(cur - prev))))
        prev = cur
    return float(np.mean(deltas)) if deltas else 99.0


def replay_analysis(frames: list[np.ndarray]) -> dict:
    """Combine per-frame recapture cues with freeze/replay motion."""
    usable = [im for im in frames if isinstance(im, np.ndarray) and im.size > 0]
    if not usable:
        return {"spoof_score": 1.0, "live": False, "reason": "empty crop", "frozen": 1.0}
    picks = [usable[0], usable[len(usable) // 2], usable[-1]]
    parts = [spoof_analysis(im) for im in picks]
    base = max(p["spoof_score"] for p in parts)
    delta = _mean_frame_delta(usable)
    frozen = float(np.clip((1.8 - delta) / 1.8, 0.0, 1.0)) if delta < 8 else 0.0
    spoof = float(np.clip(0.60 * base + 0.40 * frozen, 0.0, 1.0))
    if frozen >= 0.85:
        spoof = max(spoof, settings.spoof_score_thresh)
    live = bool(spoof < settings.spoof_score_thresh)
    best = max(parts, key=lambda p: p["spoof_score"])
    reason = "looks live"
    if not live:
        if frozen >= 0.65:
            reason = "frames look frozen — photo or paused video"
        else:
            reason = best.get("reason") or "texture cues look like a recapture"
    out = dict(best)
    out.update(
        {
            "spoof_score": round(spoof, 4),
            "live": live,
            "frozen": round(frozen, 4),
            "frame_delta": round(delta, 3),
            "reason": reason,
        }
    )
    return out
