"""Access-event log."""

from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, col, select

from app.api.deps import require_org, require_staff
from app.api.schemas import EventOut
from app.core.clock import as_local_date
from app.core.org_ctx import scoped
from app.db.models import AccessEvent, Organization, User
from app.db.session import get_session

router = APIRouter(prefix="/events", tags=["events"])


def _filtered(
    session: Session,
    *,
    limit: int,
    kind: str | None,
    person_id: int | None,
    date_from: date | None,
    date_to: date | None,
) -> list[AccessEvent]:
    stmt = scoped(select(AccessEvent).order_by(col(AccessEvent.created_at).desc()).limit(limit), AccessEvent)
    if kind:
        stmt = stmt.where(AccessEvent.kind == kind)
    if person_id is not None:
        stmt = stmt.where(AccessEvent.person_id == person_id)
    rows = list(session.exec(stmt).all())
    if date_from or date_to:
        filtered: list[AccessEvent] = []
        for row in rows:
            local = as_local_date(row.created_at, session)
            if date_from and local < date_from:
                continue
            if date_to and local > date_to:
                continue
            filtered.append(row)
        return filtered
    return rows


@router.get("", response_model=list[EventOut])
def list_events(
    limit: int = Query(default=50, ge=1, le=500),
    kind: str | None = None,
    person_id: int | None = None,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    _user: User = Depends(require_staff),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> list[AccessEvent]:
    return _filtered(
        session,
        limit=limit,
        kind=kind,
        person_id=person_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/export")
def export_events(
    limit: int = Query(default=500, ge=1, le=5000),
    kind: str | None = None,
    person_id: int | None = None,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    _user: User = Depends(require_staff),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    rows = _filtered(
        session,
        limit=limit,
        kind=kind,
        person_id=person_id,
        date_from=date_from,
        date_to=date_to,
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "time", "kind", "decision", "person", "similarity", "encoder", "detail"])
    for row in rows:
        writer.writerow(
            [
                row.id,
                row.created_at.isoformat() if row.created_at else "",
                row.kind,
                row.decision,
                row.person_name or "",
                "" if row.similarity is None else f"{row.similarity:.4f}",
                row.encoder or "",
                row.detail or "",
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=events.csv"},
    )
