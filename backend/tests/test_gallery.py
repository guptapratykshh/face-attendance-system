"""Gallery add / search / remove."""

from __future__ import annotations

import numpy as np
from app.encoders.base import l2_normalize
from app.gallery.index import FaceGallery


def test_search_returns_nearest_centroid():
    gallery = FaceGallery(dim=4, encoder="fake")
    a = l2_normalize(np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32))
    b = l2_normalize(np.array([[0.0, 1.0, 0.0, 0.0]], dtype=np.float32))
    gallery.add_person(1, "Ada", a)
    gallery.add_person(2, "Bob", b)
    hits = gallery.search(a[0], top_k=2)
    assert hits[0].person_id == 1
    assert hits[0].similarity > hits[1].similarity
    gallery.remove_person(1)
    hits = gallery.search(a[0], top_k=2)
    assert hits[0].person_id == 2
    assert len(gallery) == 1


def test_search_respects_allowed_ids():
    gallery = FaceGallery(dim=4, encoder="fake")
    a = l2_normalize(np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32))
    b = l2_normalize(np.array([[0.0, 1.0, 0.0, 0.0]], dtype=np.float32))
    gallery.add_person(1, "Ada", a)
    gallery.add_person(2, "Bob", b)
    hits = gallery.search(a[0], top_k=2, allowed_ids={2})
    assert len(hits) == 1
    assert hits[0].person_id == 2


def test_same_person_id_in_two_orgs_does_not_clobber():
    gallery = FaceGallery(dim=4, encoder="fake")
    a = l2_normalize(np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32))
    b = l2_normalize(np.array([[0.0, 1.0, 0.0, 0.0]], dtype=np.float32))
    gallery.add_person(1, "Ada", a, org_id=10)
    gallery.add_person(1, "Bea", b, org_id=20)
    assert len(gallery) == 2
    ada = gallery.embedding_of(1, org_id=10)
    bea = gallery.embedding_of(1, org_id=20)
    assert ada is not None and bea is not None
    assert float(ada @ a[0]) > 0.99
    assert float(bea @ b[0]) > 0.99
    hits_a = gallery.search(a[0], top_k=1, org_id=10)
    hits_b = gallery.search(b[0], top_k=1, org_id=20)
    assert hits_a[0].name == "Ada"
    assert hits_b[0].name == "Bea"
    gallery.remove_person(1, org_id=10)
    assert gallery.embedding_of(1, org_id=10) is None
    assert gallery.embedding_of(1, org_id=20) is not None
