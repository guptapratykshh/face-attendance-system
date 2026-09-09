"""Build org-scoped context chunks from attendance, people, and FAQ snippets."""

from __future__ import annotations

import math
from dataclasses import dataclass

from sqlmodel import Session, col, select

from app.core.clock import as_local_date, today_local
from app.core.org_ctx import get_current_org_id
from app.db.models import Attendance, Person

FAQ_SNIPPETS: list[tuple[str, str]] = [
    (
        "check-in",
        "Employees check in with a live face at the camera. HR enrolls face photos before the first check-in.",
    ),
    (
        "geofence",
        "When geofence is on, phone check-in must be inside a registered site radius (PostGIS ST_DWithin).",
    ),
    (
        "late",
        "Late is computed from org work_start plus late_grace_minutes for daily kernels.",
    ),
    (
        "assist",
        "Assist answers questions from today's attendance and the people directory. It never marks attendance.",
    ),
]


@dataclass
class RetrievedChunk:
    source_type: str
    source_id: int | None
    text: str
    score: float = 0.0


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return dot / (na * nb)


def build_live_chunks(session: Session) -> list[RetrievedChunk]:
    oid = get_current_org_id()
    today = today_local(session)
    people_stmt = select(Person).where(Person.is_active == True)  # noqa: E712
    if oid is not None:
        people_stmt = people_stmt.where(Person.org_id == oid)
    people = list(session.exec(people_stmt).all())
    att_stmt = select(Attendance).where(Attendance.decision == "present").order_by(col(Attendance.created_at).desc())
    if oid is not None:
        att_stmt = att_stmt.where(Attendance.org_id == oid)
    attendance_rows = [r for r in session.exec(att_stmt).all() if as_local_date(r.created_at, session) == today]

    present_ids = {int(r.person_id) for r in attendance_rows}
    chunks: list[RetrievedChunk] = []
    for p in people:
        pid = int(p.id) if p.id is not None else None
        status = "present today" if pid in present_ids else "not checked in today"
        if not p.is_active:
            status = "deactivated"
        chunks.append(
            RetrievedChunk(
                source_type="person",
                source_id=pid,
                text=f"Person id={pid}: {p.name}"
                + (f" (employee_id={p.employee_id})" if p.employee_id else "")
                + f" - {status}.",
            )
        )
    for r in attendance_rows:
        late = "late" if r.late else "on time"
        chunks.append(
            RetrievedChunk(
                source_type="attendance",
                source_id=int(r.id) if r.id is not None else None,
                text=(
                    f"Attendance id={r.id}: person_id={r.person_id} decision={r.decision} "
                    f"{late} at {r.created_at.isoformat()} source={r.source}."
                ),
            )
        )
    for i, (key, text) in enumerate(FAQ_SNIPPETS, start=1):
        chunks.append(RetrievedChunk(source_type="faq", source_id=i, text=f"FAQ ({key}): {text}"))
    return chunks


def rank_chunks(
    chunks: list[RetrievedChunk],
    query_embedding: list[float],
    chunk_embeddings: list[list[float]],
    *,
    top_k: int = 12,
) -> list[RetrievedChunk]:
    scored: list[RetrievedChunk] = []
    for chunk, emb in zip(chunks, chunk_embeddings, strict=True):
        scored.append(
            RetrievedChunk(
                source_type=chunk.source_type,
                source_id=chunk.source_id,
                text=chunk.text,
                score=_cosine(query_embedding, emb),
            )
        )
    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:top_k]


def keyword_fallback(chunks: list[RetrievedChunk], query: str, *, top_k: int = 12) -> list[RetrievedChunk]:
    q = query.lower()
    tokens = [t for t in q.replace("?", " ").split() if len(t) > 2]
    scored: list[RetrievedChunk] = []
    for chunk in chunks:
        text = chunk.text.lower()
        score = sum(1.0 for t in tokens if t in text)
        if "late" in q and "late" in text:
            score += 2
        if ("not" in q or "absent" in q or "still" in q) and "not checked" in text:
            score += 2
        if score > 0:
            scored.append(
                RetrievedChunk(chunk.source_type, chunk.source_id, chunk.text, score=score)
            )
    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:top_k] if scored else chunks[: min(top_k, len(chunks))]
