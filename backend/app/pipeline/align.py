"""Face alignment to a canonical geometry.

Two modes are provided because the two encoders were trained on different crops:

- "arcface": a 5-point similarity transform onto the canonical ArcFace template. This
  cancels in-plane rotation and fixes inter-ocular distance, which is what w600k_r50 saw.
- "margin": a square bbox crop with a fixed margin, closer to the MTCNN-style crops the
  published FaceNet weights were trained on.

InsightFace's `estimate_norm` asserts the output edge is a multiple of 112 or 128, so
requests for other sizes (FaceNet's 160) are aligned at a legal size and then resized.
"""

from __future__ import annotations

import cv2
import numpy as np

ALIGN_MODES = ("arcface", "margin")


def _legal_align_size(size: int) -> int:
    """Smallest allowed transform size that is >= `size`, so any resize is a downscale."""
    if size % 112 == 0 or size % 128 == 0:
        return size
    return 112 * (size // 112 + 1)


def align_arcface(image_rgb: np.ndarray, landmarks: np.ndarray, size: int = 112) -> np.ndarray:
    """Similarity-transform a face onto the canonical 5-point template."""
    from insightface.utils.face_align import estimate_norm

    if landmarks.shape != (5, 2):
        raise ValueError(f"expected 5 landmarks, got {landmarks.shape}")
    work = _legal_align_size(size)
    matrix = estimate_norm(landmarks.astype(np.float32), image_size=work, mode="arcface")
    crop = cv2.warpAffine(image_rgb, matrix, (work, work), borderValue=0.0)
    if work != size:
        crop = cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)
    return crop


def align_margin(
    image_rgb: np.ndarray, bbox: np.ndarray, size: int = 160, margin: float = 0.25
) -> np.ndarray:
    """Square crop around the bbox expanded by `margin`, edge-replicated if out of frame."""
    h, w = image_rgb.shape[:2]
    x1, y1, x2, y2 = (float(v) for v in bbox[:4])
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    side = max(x2 - x1, y2 - y1) * (1.0 + margin)
    half = side / 2

    left, top = int(round(cx - half)), int(round(cy - half))
    right, bottom = int(round(cx + half)), int(round(cy + half))

    pad_l, pad_t = max(0, -left), max(0, -top)
    pad_r, pad_b = max(0, right - w), max(0, bottom - h)
    crop = image_rgb[max(0, top) : min(h, bottom), max(0, left) : min(w, right)]
    if crop.size == 0:
        raise ValueError("bbox does not overlap the image")
    if pad_l or pad_t or pad_r or pad_b:
        crop = cv2.copyMakeBorder(
            crop, pad_t, pad_b, pad_l, pad_r, borderType=cv2.BORDER_REPLICATE
        )
    interp = cv2.INTER_AREA if crop.shape[0] > size else cv2.INTER_CUBIC
    return cv2.resize(crop, (size, size), interpolation=interp)


def align(
    image_rgb: np.ndarray,
    *,
    landmarks: np.ndarray | None = None,
    bbox: np.ndarray | None = None,
    size: int = 112,
    mode: str = "arcface",
    margin: float = 0.25,
) -> np.ndarray:
    """Align one face; falls back to a margin crop when landmarks are unavailable."""
    if mode not in ALIGN_MODES:
        raise ValueError(f"unknown align mode {mode!r}; expected one of {ALIGN_MODES}")
    if mode == "arcface":
        if landmarks is None:
            if bbox is None:
                raise ValueError("arcface alignment needs landmarks or a bbox fallback")
            return align_margin(image_rgb, bbox, size=size, margin=margin)
        return align_arcface(image_rgb, landmarks, size=size)
    if bbox is None:
        raise ValueError("margin alignment needs a bbox")
    return align_margin(image_rgb, bbox, size=size, margin=margin)
