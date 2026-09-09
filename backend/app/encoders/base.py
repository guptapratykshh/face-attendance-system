"""Encoder interface shared by the FaceNet and ArcFace backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


def l2_normalize(x: np.ndarray, axis: int = -1, eps: float = 1e-10) -> np.ndarray:
    """Scale rows to unit length so cosine similarity reduces to a dot product."""
    norm = np.linalg.norm(x, axis=axis, keepdims=True)
    return x / np.maximum(norm, eps)


class FaceEncoder(ABC):
    """Maps aligned face crops to unit-norm embeddings.

    Implementations must return L2-normalised float32 rows. Everything downstream
    (FAISS inner-product search, cosine thresholds, centroid enrolment) depends on that
    invariant, so it is asserted in the tests rather than assumed.
    """

    name: str
    dim: int
    input_size: int  # square edge length expected by `embed`

    @abstractmethod
    def embed(self, faces: np.ndarray) -> np.ndarray:
        """Embed a batch of aligned RGB uint8 crops shaped (N, input_size, input_size, 3)."""

    def embed_one(self, face: np.ndarray) -> np.ndarray:
        return self.embed(face[None, ...])[0]

    @staticmethod
    def similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Cosine similarity between unit-norm embeddings, in [-1, 1]."""
        return np.sum(a * b, axis=-1)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r}, dim={self.dim})"
