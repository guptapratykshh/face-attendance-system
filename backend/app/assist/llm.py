"""OpenAI-compatible embeddings and chat completions."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings

log = logging.getLogger(__name__)


def _headers() -> dict[str, str]:
    key = (settings.llm_api_key or "").strip()
    if not key:
        raise HTTPException(503, detail="llm_not_configured")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _base() -> str:
    return settings.llm_base_url.rstrip("/")


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    with httpx.Client(timeout=60.0) as client:
        res = client.post(
            f"{_base()}/embeddings",
            headers=_headers(),
            json={"model": settings.embed_model, "input": texts},
        )
    if res.status_code >= 400:
        log.warning("embed failed: %s %s", res.status_code, res.text[:300])
        raise HTTPException(502, detail="llm_embed_failed")
    data = res.json().get("data") or []
    data = sorted(data, key=lambda row: int(row.get("index", 0)))
    return [list(row["embedding"]) for row in data]


def chat_completion(messages: list[dict[str, str]], *, temperature: float = 0.1) -> str:
    with httpx.Client(timeout=90.0) as client:
        res = client.post(
            f"{_base()}/chat/completions",
            headers=_headers(),
            json={
                "model": settings.llm_model,
                "temperature": temperature,
                "messages": messages,
                "response_format": {"type": "json_object"},
            },
        )
    if res.status_code >= 400:
        log.warning("chat failed: %s %s", res.status_code, res.text[:300])
        raise HTTPException(502, detail="llm_chat_failed")
    try:
        return str(res.json()["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(502, detail="llm_bad_response") from exc


def parse_assist_json(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"answer": raw.strip() or "I don't know.", "citations": []}
    if not isinstance(data, dict):
        return {"answer": "I don't know.", "citations": []}
    answer = str(data.get("answer") or "I don't know.").strip()
    citations = data.get("citations") or []
    if not isinstance(citations, list):
        citations = []
    clean = []
    for c in citations:
        if not isinstance(c, dict):
            continue
        ctype = str(c.get("type") or "")
        cid = c.get("id")
        if ctype and cid is not None:
            try:
                clean.append({"type": ctype, "id": int(cid)})
            except (TypeError, ValueError):
                continue
    return {"answer": answer, "citations": clean}
