"""Tiny helpers shared by unit tests without going through conftest fixtures."""

from __future__ import annotations

import io

import numpy as np
from app.encoders.base import FaceEncoder, l2_normalize
from PIL import Image


class FakeEncoder(FaceEncoder):
    name = "fake"
    dim = 8
    input_size = 32

    def embed(self, faces: np.ndarray) -> np.ndarray:
        n = len(faces)
        out = np.zeros((n, self.dim), dtype=np.float32)
        for i, face in enumerate(faces):
            out[i, 0] = float(face.mean()) / 255.0
            out[i, 1] = float(face[:, :, 0].mean()) / 255.0
            out[i, 2] = float(face[:, :, 1].mean()) / 255.0
            out[i, 3] = 1.0
        return l2_normalize(out).astype(np.float32)


def png_bytes(color: tuple[int, int, int], size: int = 48) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, format="PNG")
    return buf.getvalue()
