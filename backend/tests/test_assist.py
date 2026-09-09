"""LLM Assist API: config gate, role gate, mocked OpenAI responses."""

from __future__ import annotations

import json

import pytest
from app.core.config import settings
from app.db.models import Organization
from app.db.session import SessionLocal
from sqlmodel import select


def _default_slug() -> str:
    with SessionLocal() as session:
        org = session.exec(select(Organization).order_by(Organization.id)).first()
        assert org is not None and org.slug
        return org.slug


def _login(client, username: str, password: str = "password1"):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, "org": _default_slug()},
    )


@pytest.fixture
def llm_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    yield
    monkeypatch.setattr(settings, "llm_api_key", None)


def test_assist_requires_llm_key(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", None)
    res = client.post("/api/v1/assist/chat", headers=auth, json={"message": "Who is late?"})
    assert res.status_code == 503
    assert res.json()["detail"] == "llm_not_configured"


def test_assist_forbidden_for_employee(client, auth, llm_key):
    client.post(
        "/api/v1/auth/register",
        json={"username": "empassist", "password": "password1", "name": "Emp Assist", "org": _default_slug()},
    )
    token = _login(client, "empassist").json()["access_token"]
    emp = {"Authorization": f"Bearer {token}"}
    res = client.post("/api/v1/assist/chat", headers=emp, json={"message": "Who is late?"})
    assert res.status_code == 403


def test_assist_chat_with_mocked_llm(client, auth, llm_key, monkeypatch):
    from app.assist import service as assist_service

    def fake_embed(texts):
        return [[0.1] * 8 for _ in texts]

    def fake_chat(messages, temperature=0.1):
        return json.dumps(
            {
                "answer": "Nobody is marked late in the retrieved rows.",
                "citations": [{"type": "faq", "id": 3}],
            }
        )

    monkeypatch.setattr(assist_service, "embed_texts", fake_embed)
    monkeypatch.setattr(assist_service, "chat_completion", fake_chat)

    res = client.post("/api/v1/assist/chat", headers=auth, json={"message": "Who is late today?"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert "late" in body["answer"].lower() or "Nobody" in body["answer"]
    assert body["citations"]
    assert body["citations"][0]["type"] == "faq"

    hist = client.get("/api/v1/assist/history", headers=auth)
    assert hist.status_code == 200
    rows = hist.json()
    assert len(rows) >= 2
    assert rows[-1]["role"] == "assistant"
