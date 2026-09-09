"""HR Assist: natural-language attendance Q&A (language modality)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from app.api.deps import require_org, require_people
from app.api.schemas import AssistChatIn, AssistChatOut, AssistCitation, AssistMessageOut
from app.assist.service import answer_question
from app.core.config import settings
from app.core.org_ctx import get_current_org_id
from app.db.models import AssistMessage, Organization, User
from app.db.session import get_session

router = APIRouter(prefix="/assist", tags=["assist"])


@router.post("/chat", response_model=AssistChatOut)
def assist_chat(
    body: AssistChatIn,
    user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> AssistChatOut:
    if not (settings.llm_api_key or "").strip():
        raise HTTPException(503, detail="llm_not_configured")
    result = answer_question(session, user=user, message=body.message)
    citations = [
        AssistCitation(type=str(c.get("type")), id=int(c["id"]))
        for c in (result.get("citations") or [])
        if isinstance(c, dict) and c.get("id") is not None and c.get("type")
    ]
    return AssistChatOut(answer=str(result.get("answer") or "I don't know."), citations=citations)


@router.get("/history", response_model=list[AssistMessageOut])
def assist_history(
    user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
    limit: int = 40,
) -> list[AssistMessageOut]:
    limit = max(1, min(limit, 100))
    stmt = (
        select(AssistMessage)
        .where(AssistMessage.user_id == user.id)
        .order_by(col(AssistMessage.created_at).desc())
        .limit(limit)
    )
    oid = get_current_org_id()
    if oid is not None:
        stmt = stmt.where(AssistMessage.org_id == oid)
    rows = list(reversed(session.exec(stmt).all()))
    out: list[AssistMessageOut] = []
    for row in rows:
        citations = []
        if row.citations_json:
            try:
                raw = json.loads(row.citations_json)
                citations = [
                    AssistCitation(type=str(c["type"]), id=int(c["id"]))
                    for c in raw
                    if isinstance(c, dict) and "type" in c and "id" in c
                ]
            except (json.JSONDecodeError, TypeError, ValueError, KeyError):
                citations = []
        out.append(
            AssistMessageOut(
                id=int(row.id),
                role=row.role,
                content=row.content,
                citations=citations,
                created_at=row.created_at,
            )
        )
    return out
