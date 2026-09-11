"""Enrolled identities: CRUD, login, CSV import, soft-deactivate."""

from __future__ import annotations

import csv
import io
import json

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, col, select

from app.api.deps import get_runtime, require_org, require_people
from app.api.routes._common import (
    clean_optional,
    commit_or_conflict,
    ensure_unique_employee_id,
    log_event,
    person_out,
    read_image,
)
from app.api.schemas import (
    AttendanceOut,
    EventOut,
    ImportResult,
    PersonCreate,
    PersonLoginIn,
    PersonOut,
    PersonTimelineOut,
    PersonUpdate,
)
from app.core.mail import notify_face_enrolled
from app.core.org_ctx import belongs_to_org, require_org_id, scoped
from app.core.security import hash_password
from app.db.models import AccessEvent, FaceEmbedding, Organization, Person, User, utcnow
from app.db.session import get_session
from app.gallery.index import vec_to_bytes
from app.runtime import Runtime

router = APIRouter(prefix="/persons", tags=["persons"])


def _person(session: Session, person_id: int) -> Person:
    return belongs_to_org(session.get(Person, person_id), detail="person not found")


@router.get("", response_model=list[PersonOut])
def list_persons(
    include_inactive: bool = False,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> list[PersonOut]:
    stmt = scoped(select(Person).order_by(Person.created_at.desc()), Person)
    if not include_inactive:
        stmt = stmt.where(Person.is_active == True)  # noqa: E712
    people = session.exec(stmt).all()
    return [person_out(p, session=session) for p in people]


@router.post("", response_model=PersonOut, status_code=201)
def create_person(
    body: PersonCreate,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> PersonOut:
    employee_id = clean_optional(body.employee_id)
    ensure_unique_employee_id(session, employee_id)
    person = Person(
        org_id=require_org_id(),
        name=body.name.strip(),
        employee_id=employee_id,
        email=clean_optional(body.email),
        notes=clean_optional(body.notes),
        department=clean_optional(body.department),
        office=clean_optional(body.office),
        shift_start=clean_optional(body.shift_start),
        shift_end=clean_optional(body.shift_end),
    )
    session.add(person)
    commit_or_conflict(session)
    session.refresh(person)
    return person_out(person, session=session)


@router.post("/import", response_model=ImportResult)
async def import_persons(
    file: UploadFile = File(...),
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> ImportResult:
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        raise HTTPException(400, detail="CSV must include a header row")
    fields = {name.strip().lower() for name in reader.fieldnames}
    if "name" not in fields:
        raise HTTPException(400, detail="CSV must include a name column")
    created = 0
    skipped = 0
    errors: list[str] = []
    for i, row in enumerate(reader, start=2):
        mapped = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        name = mapped.get("name") or ""
        if not name:
            skipped += 1
            continue
        employee_id = mapped.get("employee_id") or mapped.get("employeeid") or None
        email = mapped.get("email") or None
        if employee_id:
            existing = session.exec(
                scoped(select(Person).where(Person.employee_id == employee_id), Person)
            ).first()
            if existing is not None:
                skipped += 1
                continue
        person = Person(name=name, employee_id=employee_id or None, email=email or None, org_id=require_org_id())
        session.add(person)
        try:
            session.commit()
            created += 1
        except Exception as exc:  # pragma: no cover
            session.rollback()
            errors.append(f"row {i}: {exc}")
    return ImportResult(created=created, skipped=skipped, errors=errors)


@router.get("/{person_id}", response_model=PersonOut)
def get_person(
    person_id: int,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> PersonOut:
    person = _person(session, person_id)
    return person_out(person, session=session)


@router.get("/{person_id}/timeline", response_model=PersonTimelineOut)
def person_timeline(
    person_id: int,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> PersonTimelineOut:
    from app.db.models import Attendance

    person = _person(session, person_id)
    att_rows = session.exec(
        select(Attendance)
        .where(Attendance.person_id == person_id)
        .order_by(col(Attendance.created_at).desc())
        .limit(200)
    ).all()
    ev_rows = session.exec(
        select(AccessEvent)
        .where(AccessEvent.person_id == person_id)
        .order_by(col(AccessEvent.created_at).desc())
        .limit(200)
    ).all()
    attendance = [
        AttendanceOut(
            id=int(row.id),
            person_id=row.person_id,
            person_name=person.name,
            user_id=row.user_id,
            decision=row.decision,
            similarity=None if row.similarity is None else round(float(row.similarity), 4),
            encoder=row.encoder,
            created_at=row.created_at,
            checked_out_at=row.checked_out_at,
            source=row.source or "web",
            late=bool(row.late),
            early_leave=bool(getattr(row, "early_leave", False)),
        )
        for row in att_rows
    ]
    events = [
        EventOut(
            id=int(e.id),
            kind=e.kind,
            person_id=e.person_id,
            person_name=e.person_name,
            decision=e.decision,
            similarity=e.similarity,
            encoder=e.encoder,
            detail=e.detail,
            created_at=e.created_at,
        )
        for e in ev_rows
    ]
    return PersonTimelineOut(person=person_out(person, session=session), attendance=attendance, events=events)


@router.post("/{person_id}/login", response_model=PersonOut)
def set_person_login(
    person_id: int,
    body: PersonLoginIn,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> PersonOut:
    person = _person(session, person_id)
    username = body.username.strip()
    try:
        hashed = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    linked = session.exec(select(User).where(User.person_id == person_id)).first()
    taken = session.exec(select(User).where(User.username == username, User.org_id == person.org_id)).first()
    if linked is None:
        if taken is not None:
            raise HTTPException(409, detail="username already taken")
        session.add(
            User(
                username=username,
                hashed_password=hashed,
                is_admin=False,
                role="employee",
                person_id=person_id,
                org_id=person.org_id,
            )
        )
    else:
        if taken is not None and taken.id != linked.id:
            raise HTTPException(409, detail="username already taken")
        linked.username = username
        linked.hashed_password = hashed
        session.add(linked)
    session.commit()
    log_event(
        session,
        kind="person",
        decision="login_set",
        person=person,
        detail=f"username={username}",
    )
    return person_out(person, session=session)


@router.patch("/{person_id}", response_model=PersonOut)
def update_person(
    person_id: int,
    body: PersonUpdate,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
    rt: Runtime = Depends(get_runtime),
) -> PersonOut:
    person = _person(session, person_id)
    fields = body.model_dump(exclude_unset=True)
    if "employee_id" in fields:
        fields["employee_id"] = clean_optional(fields["employee_id"])
        ensure_unique_employee_id(session, fields["employee_id"], exclude_id=person_id)
    if "email" in fields:
        fields["email"] = clean_optional(fields["email"])
    if "notes" in fields and fields["notes"] is not None:
        fields["notes"] = fields["notes"].strip() or None
    if "name" in fields and fields["name"] is not None:
        fields["name"] = fields["name"].strip()
        if not fields["name"]:
            raise HTTPException(400, detail="name cannot be empty")
    if not fields:
        return person_out(person, session=session)

    old_name = person.name
    for key, value in fields.items():
        setattr(person, key, value)
    session.add(person)
    if person.name != old_name:
        if rt.gallery is not None:
            rt.gallery.set_name(person_id, person.name, org_id=person.org_id)
        for event in session.exec(select(AccessEvent).where(AccessEvent.person_id == person_id)).all():
            event.person_name = person.name
            session.add(event)
    commit_or_conflict(session)
    session.refresh(person)
    log_event(
        session,
        kind="person",
        decision="updated",
        person=person,
        encoder=rt.encoder_name,
        detail=", ".join(sorted(fields)),
    )
    return person_out(person, session=session)


@router.delete("/{person_id}", status_code=204)
def deactivate_person(
    person_id: int,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
    rt: Runtime = Depends(get_runtime),
) -> None:
    person = _person(session, person_id)
    person.is_active = False
    person.deactivated_at = utcnow()
    session.add(person)
    embeddings = session.exec(select(FaceEmbedding).where(FaceEmbedding.person_id == person_id)).all()
    for emb in embeddings:
        session.delete(emb)
    session.commit()
    if rt.gallery is not None:
        rt.gallery.remove_person(person_id, org_id=person.org_id)
    log_event(
        session,
        kind="person",
        decision="deactivated",
        encoder=rt.encoder_name,
        person=person,
        detail=f"deactivated {person.name} (id={person_id})",
    )


@router.post("/{person_id}/reactivate", response_model=PersonOut)
def reactivate_person(
    person_id: int,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
    rt: Runtime = Depends(get_runtime),
) -> PersonOut:
    person = _person(session, person_id)
    person.is_active = True
    person.deactivated_at = None
    session.add(person)
    session.commit()
    session.refresh(person)
    existing = session.exec(
        select(FaceEmbedding).where(
            FaceEmbedding.person_id == person_id,
            FaceEmbedding.encoder == rt.encoder_name,
        )
    ).all()
    if existing and rt.gallery is not None:
        stacked = np.stack([np.frombuffer(e.vector, dtype=np.float32) for e in existing], axis=0)
        rt.gallery.add_person(person_id, person.name, stacked, org_id=person.org_id)
    log_event(
        session,
        kind="person",
        decision="reactivated",
        encoder=rt.encoder_name,
        person=person,
        detail=f"reactivated {person.name} (id={person_id})",
    )
    return person_out(person, session=session)


@router.post("/{person_id}/enroll", response_model=PersonOut)
async def enroll(
    person_id: int,
    images: list[UploadFile] = File(...),
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
    rt: Runtime = Depends(get_runtime),
) -> PersonOut:
    person = _person(session, person_id)
    if person.is_active is False:
        raise HTTPException(400, detail="person is deactivated")
    if not images:
        raise HTTPException(400, detail="upload at least one image")
    if len(images) > 5:
        raise HTTPException(400, detail="upload at most 5 images")

    new_vecs: list[np.ndarray] = []
    for upload in images:
        face = rt.pipeline.embed_single(await read_image(upload))
        session.add(
            FaceEmbedding(
                person_id=person_id,
                encoder=rt.encoder_name,
                dim=int(face.embedding.shape[0]),
                vector=vec_to_bytes(face.embedding),
                quality_json=json.dumps(face.quality),
            )
        )
        new_vecs.append(face.embedding)

    session.commit()
    session.refresh(person)
    existing = session.exec(
        select(FaceEmbedding).where(
            FaceEmbedding.person_id == person_id,
            FaceEmbedding.encoder == rt.encoder_name,
        )
    ).all()
    stacked = np.stack(
        [np.frombuffer(e.vector, dtype=np.float32) for e in existing],
        axis=0,
    )
    rt.gallery.add_person(person_id, person.name, stacked, org_id=person.org_id)
    log_event(
        session,
        kind="enroll",
        decision="enrolled",
        person=person,
        encoder=rt.encoder_name,
        detail=f"added {len(new_vecs)} embeddings, total {len(existing)}",
    )
    notify_face_enrolled(person)
    return person_out(person, session=session)
