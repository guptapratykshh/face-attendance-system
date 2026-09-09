"""Answer HR questions from retrieved org data + LLM (never mutates attendance)."""

from __future__ import annotations

import json

from sqlmodel import Session

from app.assist.llm import chat_completion, embed_texts, parse_assist_json
from app.assist.retrieve import build_live_chunks, keyword_fallback, rank_chunks
from app.core.config import settings
from app.core.org_ctx import get_current_org_id
from app.db.models import AssistMessage, User

SYSTEM_PROMPT = """You are Sentinel Assist for workplace/school attendance.
Answer ONLY using the CONTEXT chunks. If the answer is not in CONTEXT, say you don't know.
Never invent people or times. Never mark attendance or change records.
Return strict JSON: {"answer": string, "citations": [{"type": "attendance"|"person"|"faq", "id": number}]}
Include citations for every factual claim when an id is available.
"""


def answer_question(session: Session, *, user: User, message: str) -> dict:
    text = (message or "").strip()
    if not text:
        return {"answer": "Ask a question about today's attendance or people.", "citations": []}

    chunks = build_live_chunks(session)
    selected = keyword_fallback(chunks, text)
    if (settings.llm_api_key or "").strip():
        try:
            embeddings = embed_texts([text] + [c.text for c in chunks])
            if embeddings:
                q_emb, *chunk_embs = embeddings
                if len(chunk_embs) == len(chunks):
                    selected = rank_chunks(chunks, q_emb, chunk_embs)
        except Exception:
            selected = keyword_fallback(chunks, text)

        context_lines = []
        for i, c in enumerate(selected, start=1):
            context_lines.append(
                f"[{i}] type={c.source_type} id={c.source_id} :: {c.text}"
            )
        context = "\n".join(context_lines) if context_lines else "(no rows)"
        raw = chat_completion(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"CONTEXT:\n{context}\n\nQUESTION: {text}",
                },
            ]
        )
        result = parse_assist_json(raw)
    else:
        # Deterministic grounded summary when no API key (still useful in tests via monkeypatch).
        # Production without a key returns 503 from the route before calling this for chat
        # when configured to require LLM — route decides.
        lines = [c.text for c in selected[:8]]
        result = {
            "answer": "Here is what I found:\n" + "\n".join(f"- {line}" for line in lines)
            if lines
            else "I don't know.",
            "citations": [
                {"type": c.source_type, "id": c.source_id}
                for c in selected[:8]
                if c.source_id is not None
            ],
        }

    oid = get_current_org_id()
    session.add(
        AssistMessage(
            org_id=oid,
            user_id=int(user.id) if user.id is not None else None,
            role="user",
            content=text,
        )
    )
    session.add(
        AssistMessage(
            org_id=oid,
            user_id=int(user.id) if user.id is not None else None,
            role="assistant",
            content=str(result["answer"]),
            citations_json=json.dumps(result.get("citations") or []),
        )
    )
    session.commit()
    return result
