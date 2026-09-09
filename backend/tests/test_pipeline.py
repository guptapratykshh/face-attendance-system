"""Alignment geometry and pipeline error mapping."""

from __future__ import annotations

import numpy as np
import pytest
from app.pipeline.align import align_arcface, align_margin
from app.pipeline.errors import ImageDecodeError
from app.pipeline.face_pipeline import decode_image

from tests.helpers import png_bytes


def test_decode_rejects_empty():
    with pytest.raises(ImageDecodeError):
        decode_image(b"")


def test_decode_png_roundtrip():
    rgb = decode_image(png_bytes((10, 20, 30), size=16))
    assert rgb.shape == (16, 16, 3)
    assert rgb[0, 0, 0] == 10


def test_margin_crop_is_square():
    image = np.zeros((80, 120, 3), dtype=np.uint8)
    image[20:60, 40:80] = 200
    crop = align_margin(image, np.array([40, 20, 80, 60], dtype=np.float32), size=32, margin=0.0)
    assert crop.shape == (32, 32, 3)


def test_arcface_align_output_size():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    image[:] = 80
    landmarks = np.array([[30, 30], [70, 30], [50, 50], [35, 75], [65, 75]], dtype=np.float32)
    crop = align_arcface(image, landmarks, size=112)
    assert crop.shape == (112, 112, 3)
    crop160 = align_arcface(image, landmarks, size=160)
    assert crop160.shape == (160, 160, 3)
