"""Shared helpers for the recognition routes."""

from __future__ import annotations

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.api.schemas import FaceInfo, PersonOut
from app.core.config import settings
from app.core.org_ctx import get_current_org_id
from app.db.models import AccessEvent, FaceEmbedding, Person, User
from app.pipeline.face_pipeline import FaceResult


async def read_image(upload: UploadFile) -> bytes:
    data = await upload.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="empty upload")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="image too large")
    return data


def face_info(result: FaceResult) -> FaceInfo:
    d = result.as_dict()
    return FaceInfo(
        bbox=d["bbox"],
        score=d["score"],
        landmarks=d["landmarks"],
        quality=d.get("quality") or {},
    )


def person_status(person: Person, n_embeddings: int, username: str | None) -> str:
    if not person.is_active:
        return "Inactive"
    if n_embeddings <= 0:
        return "No face"
    if not username:
        return "No login"
    return "Active"


def person_out(person: Person, n_embeddings: int | None = None, session: Session | None = None) -> PersonOut:
    if n_embeddings is None and session is not None and person.id is not None:
        n_embeddings = session.exec(
            select(func.count()).select_from(FaceEmbedding).where(FaceEmbedding.person_id == person.id)
        ).one()
    n_embeddings = int(n_embeddings or 0)
    username = None
    if session is not None and person.id is not None:
        linked = session.exec(select(User).where(User.person_id == person.id)).first()
        if linked is not None:
            username = linked.username
    return PersonOut(
        id=int(person.id),
        name=person.name,
        employee_id=person.employee_id,
        email=person.email,
        notes=person.notes,
        department=person.department,
        office=person.office,
        shift_start=person.shift_start,
        shift_end=person.shift_end,
        created_at=person.created_at,
        n_embeddings=n_embeddings,
        username=username,
        is_active=bool(person.is_active),
        status=person_status(person, n_embeddings, username),
    )


def clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def ensure_unique_username(
    session: Session,
    username: str,
    *,
    org_id: int | None,
    exclude_id: int | None = None,
) -> None:
    stmt = select(User).where(User.username == username)
    if org_id is not None:
        stmt = stmt.where(User.org_id == org_id)
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    if session.exec(stmt).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="username already taken")


def ensure_unique_employee_id(session: Session, employee_id: str | None, *, exclude_id: int | None = None) -> None:
    if not employee_id:
        return
    stmt = select(Person).where(Person.employee_id == employee_id)
    oid = get_current_org_id()
    if oid is not None:
        stmt = stmt.where(Person.org_id == oid)
    if exclude_id is not None:
        stmt = stmt.where(Person.id != exclude_id)
    if session.exec(stmt).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="employee_id already in use")


def commit_or_conflict(session: Session, message: str = "employee_id already in use") -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=message) from exc


def log_event(
    session: Session,
    *,
    kind: str,
    decision: str,
    person: Person | None = None,
    similarity: float | None = None,
    encoder: str | None = None,
    detail: str | None = None,
) -> None:
    session.add(
        AccessEvent(
            org_id=get_current_org_id() or (person.org_id if person is not None else None),
            kind=kind,
            person_id=int(person.id) if person is not None else None,
            person_name=person.name if person is not None else None,
            decision=decision,
            similarity=similarity,
            encoder=encoder,
            detail=detail,
        )
    )
    session.commit()
