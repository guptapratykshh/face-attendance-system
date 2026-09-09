"""Offerings, enrollments, occurrences, and sites for session/shift/visit kernels."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, func, select

from app.api.deps import get_current_user, require_org, require_people, require_staff
from app.api.schemas import (
    EnrollmentIn,
    EnrollmentOut,
    OccurrenceIn,
    OccurrenceOut,
    OfferingIn,
    OfferingOut,
    OfferingStatsOut,
    SiteIn,
    SiteOut,
)
from app.core.attendance_policy import kernel_of, occurrence_is_open, present_for_occurrence
from app.core.clock import office_settings, today_local
from app.core.org_ctx import belongs_to_org, require_org_id, scoped
from app.db.models import Attendance, Enrollment, Occurrence, Offering, Organization, Person, Site, User
from app.db.session import get_session

router = APIRouter(prefix="/schedule", tags=["schedule"])


def _parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(400, detail="invalid_date") from exc


def _enrolled_count(session: Session, offering_id: int) -> int:
    n = session.exec(select(func.count()).select_from(Enrollment).where(Enrollment.offering_id == offering_id)).one()
    return int(n or 0)


def _offering_out(session: Session, row: Offering) -> OfferingOut:
    return OfferingOut(
        id=int(row.id),
        name=row.name,
        code=row.code,
        kind=row.kind,
        default_start=row.default_start,
        default_end=row.default_end,
        room=row.room,
        site_id=row.site_id,
        min_percent=int(row.min_percent or 75),
        is_active=bool(row.is_active),
        enrolled=_enrolled_count(session, int(row.id)),
    )


def _occurrence_out(
    session: Session,
    row: Occurrence,
    *,
    person_id: int | None = None,
) -> OccurrenceOut:
    offering_name = None
    expected = 0
    if row.offering_id is not None:
        offering = session.get(Offering, row.offering_id)
        offering_name = offering.name if offering is not None else None
        expected = _enrolled_count(session, int(row.offering_id))
    present = session.exec(
        select(func.count())
        .select_from(Attendance)
        .where(Attendance.occurrence_id == row.id)
        .where(Attendance.decision == "present")
    ).one()
    already = False
    if person_id is not None:
        already = present_for_occurrence(session, person_id, int(row.id)) is not None
    return OccurrenceOut(
        id=int(row.id),
        offering_id=row.offering_id,
        offering_name=offering_name,
        kind=row.kind,
        title=row.title,
        day=row.day.isoformat(),
        start=row.start,
        end=row.end,
        overnight=bool(row.overnight),
        room=row.room,
        site_id=row.site_id,
        open=occurrence_is_open(row, session),
        expected=expected,
        present=int(present or 0),
        already_marked=already,
    )


@router.get("/sites", response_model=list[SiteOut])
def list_sites(
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> list[SiteOut]:
    rows = session.exec(scoped(select(Site).order_by(col(Site.name)), Site)).all()
    return [
        SiteOut(id=int(r.id), name=r.name, lat=r.lat, lng=r.lng, radius_m=r.radius_m, is_default=bool(r.is_default))
        for r in rows
    ]


@router.post("/sites", response_model=SiteOut, status_code=201)
def create_site(
    body: SiteIn,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> SiteOut:
    from app.core.geo import sync_site_geom

    row = Site(
        org_id=require_org_id(),
        name=body.name.strip(),
        lat=body.lat,
        lng=body.lng,
        radius_m=body.radius_m,
        is_default=body.is_default,
    )
    if body.is_default:
        for other in session.exec(scoped(select(Site), Site)).all():
            other.is_default = False
            session.add(other)
    session.add(row)
    session.commit()
    session.refresh(row)
    sync_site_geom(session, row)
    session.commit()
    return SiteOut(id=int(row.id), name=row.name, lat=row.lat, lng=row.lng, radius_m=row.radius_m, is_default=bool(row.is_default))


@router.patch("/sites/{site_id}", response_model=SiteOut)
def update_site(
    site_id: int,
    body: SiteIn,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> SiteOut:
    from app.core.geo import sync_site_geom

    row = belongs_to_org(session.get(Site, site_id), detail="site_not_found")
    row.name = body.name.strip()
    row.lat = body.lat
    row.lng = body.lng
    row.radius_m = body.radius_m
    row.is_default = body.is_default
    if body.is_default:
        for other in session.exec(scoped(select(Site).where(Site.id != site_id), Site)).all():
            other.is_default = False
            session.add(other)
    session.add(row)
    session.commit()
    session.refresh(row)
    sync_site_geom(session, row)
    session.commit()
    return SiteOut(id=int(row.id), name=row.name, lat=row.lat, lng=row.lng, radius_m=row.radius_m, is_default=bool(row.is_default))


@router.delete("/sites/{site_id}", status_code=204)
def delete_site(
    site_id: int,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> None:
    row = belongs_to_org(session.get(Site, site_id), detail="site_not_found")
    session.delete(row)
    session.commit()


@router.get("/offerings", response_model=list[OfferingOut])
def list_offerings(
    include_inactive: bool = False,
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> list[OfferingOut]:
    stmt = scoped(select(Offering).order_by(col(Offering.name)), Offering)
    if not include_inactive:
        stmt = stmt.where(Offering.is_active == True)  # noqa: E712
    return [_offering_out(session, row) for row in session.exec(stmt).all()]


@router.post("/offerings", response_model=OfferingOut, status_code=201)
def create_offering(
    body: OfferingIn,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> OfferingOut:
    row = Offering(
        org_id=require_org_id(),
        name=body.name.strip(),
        code=(body.code or "").strip() or None,
        kind=(body.kind or "course").strip() or "course",
        default_start=body.default_start,
        default_end=body.default_end,
        room=body.room,
        site_id=body.site_id,
        min_percent=body.min_percent,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _offering_out(session, row)


@router.patch("/offerings/{offering_id}", response_model=OfferingOut)
def update_offering(
    offering_id: int,
    body: OfferingIn,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> OfferingOut:
    row = belongs_to_org(session.get(Offering, offering_id), detail="offering_not_found")
    row.name = body.name.strip()
    row.code = (body.code or "").strip() or None
    row.kind = (body.kind or row.kind).strip() or row.kind
    row.default_start = body.default_start
    row.default_end = body.default_end
    row.room = body.room
    row.site_id = body.site_id
    row.min_percent = body.min_percent
    session.add(row)
    session.commit()
    session.refresh(row)
    return _offering_out(session, row)


@router.delete("/offerings/{offering_id}", status_code=204)
def archive_offering(
    offering_id: int,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> None:
    row = belongs_to_org(session.get(Offering, offering_id), detail="offering_not_found")
    row.is_active = False
    session.add(row)
    session.commit()


@router.get("/offerings/{offering_id}/enrollments", response_model=list[EnrollmentOut])
def list_enrollments(
    offering_id: int,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> list[EnrollmentOut]:
    offering = belongs_to_org(session.get(Offering, offering_id), detail="offering_not_found")
    rows = session.exec(select(Enrollment).where(Enrollment.offering_id == offering_id)).all()
    out: list[EnrollmentOut] = []
    for row in rows:
        person = session.get(Person, row.person_id)
        if person is None:
            continue
        out.append(
            EnrollmentOut(
                id=int(row.id),
                person_id=int(row.person_id),
                person_name=person.name,
                offering_id=int(row.offering_id),
                offering_name=offering.name,
            )
        )
    return out


@router.post("/offerings/{offering_id}/enrollments", response_model=EnrollmentOut, status_code=201)
def enroll_person(
    offering_id: int,
    body: EnrollmentIn,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> EnrollmentOut:
    offering = belongs_to_org(session.get(Offering, offering_id), detail="offering_not_found")
    person = belongs_to_org(session.get(Person, body.person_id), detail="person not found")
    existing = session.exec(
        select(Enrollment).where(Enrollment.offering_id == offering_id).where(Enrollment.person_id == body.person_id)
    ).first()
    if existing is not None:
        return EnrollmentOut(
            id=int(existing.id),
            person_id=int(existing.person_id),
            person_name=person.name,
            offering_id=int(existing.offering_id),
            offering_name=offering.name,
        )
    row = Enrollment(person_id=int(person.id), offering_id=int(offering.id), org_id=require_org_id())
    session.add(row)
    session.commit()
    session.refresh(row)
    return EnrollmentOut(
        id=int(row.id),
        person_id=int(row.person_id),
        person_name=person.name,
        offering_id=int(row.offering_id),
        offering_name=offering.name,
    )


@router.delete("/enrollments/{enrollment_id}", status_code=204)
def drop_enrollment(
    enrollment_id: int,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> None:
    row = belongs_to_org(session.get(Enrollment, enrollment_id), detail="enrollment_not_found")
    session.delete(row)
    session.commit()


@router.get("/offerings/{offering_id}/stats", response_model=OfferingStatsOut)
def offering_stats(
    offering_id: int,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> OfferingStatsOut:
    offering = belongs_to_org(session.get(Offering, offering_id), detail="offering_not_found")
    meetings = list(session.exec(select(Occurrence).where(Occurrence.offering_id == offering_id)).all())
    enrolled = list(session.exec(select(Enrollment).where(Enrollment.offering_id == offering_id)).all())
    expected = len(meetings) * len(enrolled)
    present_marks = 0
    per_person: dict[int, int] = {int(e.person_id): 0 for e in enrolled}
    for occ in meetings:
        rows = session.exec(
            select(Attendance)
            .where(Attendance.occurrence_id == occ.id)
            .where(Attendance.decision == "present")
        ).all()
        present_marks += len(rows)
        for row in rows:
            if row.person_id in per_person:
                per_person[row.person_id] += 1
    percent = (100.0 * present_marks / expected) if expected else 0.0
    min_pct = int(offering.min_percent or 75)
    below: list[dict] = []
    n_meet = max(len(meetings), 1)
    for pid, marks in per_person.items():
        pct = 100.0 * marks / n_meet if meetings else 0.0
        if pct + 1e-9 < min_pct:
            person = session.get(Person, pid)
            below.append({"person_id": pid, "person_name": person.name if person else "", "percent": round(pct, 1), "present": marks, "meetings": len(meetings)})
    return OfferingStatsOut(
        offering=_offering_out(session, offering),
        meetings=len(meetings),
        present_marks=present_marks,
        expected_marks=expected,
        percent=round(percent, 1),
        below_min=below,
    )


@router.get("/occurrences", response_model=list[OccurrenceOut])
def list_occurrences(
    day: str | None = None,
    offering_id: int | None = None,
    open_now: bool = False,
    _staff: User = Depends(require_staff),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> list[OccurrenceOut]:
    stmt = scoped(select(Occurrence).order_by(col(Occurrence.day).desc(), col(Occurrence.start)), Occurrence)
    if day:
        stmt = stmt.where(Occurrence.day == _parse_day(day))
    if offering_id is not None:
        stmt = stmt.where(Occurrence.offering_id == offering_id)
    rows = list(session.exec(stmt).all())
    if open_now:
        rows = [r for r in rows if occurrence_is_open(r, session)]
    return [_occurrence_out(session, row) for row in rows]


@router.get("/mine", response_model=list[OccurrenceOut])
def my_schedule(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[OccurrenceOut]:
    if user.person_id is None:
        return []
    today = today_local(session)
    enrolled_ids = {
        int(e.offering_id)
        for e in session.exec(select(Enrollment).where(Enrollment.person_id == user.person_id)).all()
    }
    stmt = scoped(select(Occurrence).where(Occurrence.day == today).order_by(col(Occurrence.start)), Occurrence)
    rows = list(session.exec(stmt).all())
    out: list[OccurrenceOut] = []
    for row in rows:
        if row.offering_id is not None and int(row.offering_id) not in enrolled_ids:
            continue
        out.append(_occurrence_out(session, row, person_id=int(user.person_id)))
    return out


@router.post("/occurrences", response_model=OccurrenceOut, status_code=201)
def create_occurrence(
    body: OccurrenceIn,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> OccurrenceOut:
    cfg = office_settings(session)
    offering = None
    if body.offering_id is not None:
        offering = belongs_to_org(session.get(Offering, body.offering_id), detail="offering_not_found")
    kind = (body.kind or (offering.kind if offering and offering.kind in {"session", "shift", "visit", "event"} else None) or kernel_of(cfg))
    if kind == "daily_inout" or kind == "daily_presence":
        kind = "session"
    title = (body.title or "").strip() or (offering.name if offering is not None else "Session")
    row = Occurrence(
        org_id=require_org_id(),
        offering_id=body.offering_id,
        kind=kind if kind in {"session", "shift", "visit", "event"} else "session",
        title=title,
        day=_parse_day(body.day),
        start=body.start or (offering.default_start if offering else None) or "09:00",
        end=body.end or (offering.default_end if offering else None) or "10:00",
        overnight=body.overnight,
        room=body.room or (offering.room if offering else None),
        site_id=body.site_id if body.site_id is not None else (offering.site_id if offering else None),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _occurrence_out(session, row)


@router.delete("/occurrences/{occurrence_id}", status_code=204)
def delete_occurrence(
    occurrence_id: int,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> None:
    row = belongs_to_org(session.get(Occurrence, occurrence_id), detail="occurrence_not_found")
    session.delete(row)
    session.commit()
