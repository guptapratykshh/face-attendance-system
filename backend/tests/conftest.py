"""Shared test fixtures: temp SQLite, fake pipeline, FastAPI client."""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from app.core.config import settings
from app.core.security import hash_password
from app.db import session as db_session
from app.db.models import Organization, PlatformUser
from app.db.session import configure_engine, init_db
from app.gallery.index import FaceGallery
from app.pipeline.detector import Detection
from app.pipeline.face_pipeline import FaceResult, decode_image
from app.runtime import runtime
from fastapi.testclient import TestClient
from sqlmodel import select

from tests.helpers import FakeEncoder


class FakePipeline:
    def __init__(self):
        self.encoder = FakeEncoder()

    @property
    def encoder_name(self) -> str:
        return self.encoder.name

    def embed_single(self, image, **_kwargs) -> FaceResult:
        rgb = decode_image(image) if isinstance(image, bytes | bytearray) else image
        crop = cv2.resize(rgb, (32, 32), interpolation=cv2.INTER_AREA)
        embedding = self.encoder.embed_one(crop)
        h, w = rgb.shape[:2]
        det = Detection(
            bbox=np.array([1.0, 1.0, w - 1.0, h - 1.0], dtype=np.float32),
            score=0.99,
            landmarks=np.array(
                [[w * 0.3, h * 0.3], [w * 0.7, h * 0.3], [w * 0.5, h * 0.5], [w * 0.35, h * 0.75], [w * 0.65, h * 0.75]],
                dtype=np.float32,
            ),
        )
        return FaceResult(
            embedding=embedding,
            detection=det,
            crop=rgb,
            quality={"det_score": 0.99, "face_pixels": min(h, w), "blur_var": 40.0, "brightness": 120.0},
        )


@pytest.fixture
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    settings.require_liveness = False
    settings.allow_public_register = True
    settings.rate_limit = False
    configure_engine(url)
    init_db()
    with db_session.SessionLocal() as session:
        session.add(
            PlatformUser(
                username="admin",
                hashed_password=hash_password("admin1234"),
                is_admin=True,
                role="admin",
            )
        )
        session.commit()
    return url


@pytest.fixture
def client(db_url):
    runtime.verify_threshold = 0.8
    runtime.identify_threshold = 0.8
    from app.main import create_app

    runtime.pipeline = FakePipeline()
    runtime.gallery = FaceGallery(dim=8, encoder="fake")
    runtime.encoder_name = "fake"
    runtime.eval_report = {
        "served_encoder": "fake",
        "results": {
            "fake": {
                "eer": 0.02,
                "accuracy": {"mean": 0.99, "std": 0.01, "per_fold": [0.99] * 10},
                "tar_at_far": {"0.001": {"tar": 0.95, "threshold": 0.8, "far_target": 0.001}},
                "roc": {"far": [0.0, 1.0], "tar": [0.0, 1.0]},
                "genuine": {"mean": 0.9, "std": 0.05, "min": 0.7, "max": 1.0},
                "impostor": {"mean": 0.1, "std": 0.05, "min": 0.0, "max": 0.3},
            }
        },
        "protocol": {"name": "synthetic"},
    }

    with TestClient(create_app(boot=False)) as c:
        yield c
    runtime.pipeline = None
    runtime.gallery = None
    runtime.eval_report = None


@pytest.fixture
def default_org_id(db_url) -> int:
    with db_session.SessionLocal() as session:
        org = session.exec(select(Organization).order_by(Organization.id)).first()
        assert org is not None and org.id is not None
        return int(org.id)


@pytest.fixture
def token(client) -> str:
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture
def auth(token, default_org_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Org-Id": str(default_org_id)}
