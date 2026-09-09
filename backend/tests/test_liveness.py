"""Liveness heuristics that do not require a camera."""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from app.core.config import settings
from app.liveness.blink import (
    _EYE_HEIGHT_FRAC,
    _EYE_WIDTH_FRAC,
    blink_from_ears,
    ear_from_image,
    timed_blink,
)
from app.liveness.texture import replay_analysis, spoof_analysis
from app.pipeline.detector import get_detector

LFW_FACE = settings.lfw_images_dir / "Aaron_Peirsol" / "Aaron_Peirsol_0001.jpg"


def test_blink_detects_open_closed_open():
    ears = [0.32, 0.30, 0.12, 0.10, 0.29, 0.31]
    rec = blink_from_ears(ears)
    assert rec["blink"] is True


def test_blink_rejects_always_open():
    rec = blink_from_ears([0.3, 0.31, 0.29, 0.32])
    assert rec["blink"] is False


def test_webcam_partial_blink_is_detected():
    """Real webcam blinks only dip ~10–15% on the appearance score."""
    ears = [0.4581, 0.4604, 0.4722, 0.4186, 0.4078, 0.4644, 0.4205, 0.4283, 0.4726, 0.4216]
    rec = blink_from_ears(ears)
    assert rec["blink"] is True


def test_texture_on_noisy_crop_is_finite():
    rng = np.random.default_rng(0)
    crop = rng.integers(0, 255, size=(112, 112, 3), dtype=np.uint8)
    rec = spoof_analysis(crop)
    assert 0.0 <= rec["spoof_score"] <= 1.0
    assert "live" in rec


def _load_lfw() -> np.ndarray:
    if not LFW_FACE.exists():
        pytest.skip(f"LFW image missing: {LFW_FACE}")
    bgr = cv2.imread(str(LFW_FACE))
    assert bgr is not None
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _paint_closed_eyes(image_rgb: np.ndarray) -> np.ndarray:
    """Fill both eye ellipses with nearby skin so lids look shut."""
    detections = get_detector().detect(image_rgb, max_num=1)
    if not detections:
        pytest.skip("detector found no face on LFW sample")
    det = detections[0]
    closed = image_rgb.copy()
    for eye in det.landmarks[:2]:
        w = max(10.0, det.width * _EYE_WIDTH_FRAC)
        h = max(8.0, det.height * _EYE_HEIGHT_FRAC)
        x1, y1 = int(eye[0] - w / 2), int(eye[1] - h / 2)
        x2, y2 = int(eye[0] + w / 2), int(eye[1] + h / 2)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(closed.shape[1], x2), min(closed.shape[0], y2)
        sy = max(0, y1 - 10)
        skin = closed[sy:y1, x1:x2].mean(axis=(0, 1)) if y1 > sy else closed[y1:y2, x1:x2].mean(axis=(0, 1))
        yy, xx = np.ogrid[y1:y2, x1:x2]
        cy, cx = (y1 + y2) / 2.0, (x1 + x2) / 2.0
        ry, rx = max((y2 - y1) / 2.0, 1.0), max((x2 - x1) / 2.0, 1.0)
        mask = ((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 <= 1.0
        closed[y1:y2, x1:x2][mask] = skin
    return closed


def test_open_lfw_face_has_finite_openness():
    image = _load_lfw()
    ear = ear_from_image(image)
    assert ear is not None
    assert 0.05 < ear < 0.95


def test_still_photo_burst_is_not_a_blink():
    image = _load_lfw()
    ears = [ear_from_image(image) for _ in range(8)]
    rec = blink_from_ears(ears)
    assert rec["blink"] is False


def test_synthetic_blink_sequence_is_detected():
    open_im = _load_lfw()
    closed_im = _paint_closed_eyes(open_im)
    open_ear = ear_from_image(open_im)
    closed_ear = ear_from_image(closed_im)
    assert open_ear is not None and closed_ear is not None
    assert closed_ear < open_ear
    ears = [open_ear, open_ear, closed_ear, closed_ear, open_ear, open_ear, open_ear, open_ear]
    rec = blink_from_ears(ears)
    assert rec["blink"] is True


def test_timed_blink_requires_prompt_then_blink():
    hold = [0.32, 0.31, 0.30, 0.31, 0.32]
    action = [0.32, 0.30, 0.12, 0.10, 0.29, 0.31]
    rec = timed_blink(hold, action)
    assert rec["blink"] is True
    assert rec["timed_ok"] is True


def test_timed_blink_accepts_early_blink():
    """A live person often blinks while waiting; that is not a still photo."""
    hold = [0.32, 0.12, 0.10, 0.30]
    action = [0.32, 0.31, 0.30, 0.31]
    rec = timed_blink(hold, action)
    assert rec["blink"] is True
    assert rec["reason"] == "blink detected"


def test_timed_blink_accepts_blink_spanning_hold_and_action():
    hold = [0.32, 0.31, 0.12]
    action = [0.10, 0.29, 0.31]
    rec = timed_blink(hold, action)
    assert rec["blink"] is True


def test_timed_blink_rejects_still_photo():
    hold = [0.31, 0.31, 0.30, 0.31]
    action = [0.31, 0.30, 0.31, 0.30]
    rec = timed_blink(hold, action)
    assert rec["blink"] is False


def test_replay_analysis_flags_frozen_frames():
    rng = np.random.default_rng(1)
    frame = rng.integers(40, 200, size=(96, 96, 3), dtype=np.uint8)
    rec = replay_analysis([frame, frame, frame, frame, frame, frame])
    assert rec["frozen"] >= 0.65
    assert rec["live"] is False


def test_replay_analysis_moving_noise_is_not_frozen():
    rng = np.random.default_rng(2)
    frames = [rng.integers(0, 255, size=(96, 96, 3), dtype=np.uint8) for _ in range(6)]
    rec = replay_analysis(frames)
    assert rec["frozen"] < 0.5
    assert type(rec["live"]) is bool
