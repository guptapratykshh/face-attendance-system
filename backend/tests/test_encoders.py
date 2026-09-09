"""Encoder contract: unit-norm rows, cosine = inner product."""

from __future__ import annotations

import numpy as np
from app.encoders.base import FaceEncoder, l2_normalize

from tests.helpers import FakeEncoder


def test_l2_normalize_unit_rows():
    x = np.array([[3.0, 4.0], [0.0, 2.0]], dtype=np.float32)
    y = l2_normalize(x)
    norms = np.linalg.norm(y, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-6)


def test_fake_encoder_unit_norm_and_batch():
    enc = FakeEncoder()
    faces = np.random.default_rng(0).integers(0, 255, size=(4, 32, 32, 3), dtype=np.uint8)
    emb = enc.embed(faces)
    assert emb.shape == (4, 8)
    np.testing.assert_allclose(np.linalg.norm(emb, axis=1), 1.0, atol=1e-5)
    one = enc.embed_one(faces[0])
    np.testing.assert_allclose(one, emb[0], atol=1e-5)


def test_similarity_is_cosine():
    a = l2_normalize(np.array([[1.0, 0.0, 0.0]], dtype=np.float32))
    b = l2_normalize(np.array([[1.0, 1.0, 0.0]], dtype=np.float32))
    sim = FaceEncoder.similarity(a, b)[0]
    np.testing.assert_allclose(sim, np.sqrt(0.5), atol=1e-5)
