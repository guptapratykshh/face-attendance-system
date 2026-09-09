"""Current organization for this request (JWT org or X-Org-Id for platform admin)."""

from __future__ import annotations

from collections.abc import Collection
from contextvars import ContextVar
from typing import Any

from fastapi import HTTPException
from sqlalchemy import false
from sqlmodel import Session, select

from app.db.models import Person

current_org_id: ContextVar[int | None] = ContextVar("current_org_id", default=None)


def get_current_org_id() -> int | None:
    return current_org_id.get()


def set_current_org_id(org_id: int | None):
    return current_org_id.set(org_id)


def reset_current_org_id(token) -> None:
    current_org_id.reset(token)


def require_org_id() -> int:
    oid = get_current_org_id()
    if oid is None:
        raise HTTPException(400, detail="org_required")
    return int(oid)


def scoped(stmt, model):
    oid = get_current_org_id()
    if oid is None:
        return stmt.where(false())
    return stmt.where(model.org_id == oid)


def org_person_ids(session: Session) -> set[int]:
    oid = get_current_org_id()
    stmt = select(Person.id)
    if oid is not None:
        stmt = stmt.where(Person.org_id == oid)
    return {int(pid) for pid in session.exec(stmt).all() if pid is not None}


def belongs_to_org(row: Any | None, *, detail: str = "not_found"):
    if row is None:
        raise HTTPException(404, detail=detail)
    oid = get_current_org_id()
    row_org = getattr(row, "org_id", None)
    if oid is not None and (row_org is None or int(row_org) != int(oid)):
        raise HTTPException(404, detail=detail)
    return row


def gallery_allowed_ids(session: Session) -> Collection[int] | None:
    oid = get_current_org_id()
    if oid is None:
        return None
    return org_person_ids(session)
