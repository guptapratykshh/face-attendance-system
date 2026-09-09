"""Ops home: today's roster, pending faces, recent punches."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlmodel import Session, col, func, select

from app.api.deps import require_org, require_people, require_staff
from app.api.schemas import AbsenceStreakOut, AttendanceOut, BoardPersonOut, OpsSummaryOut, SessionTodayOut, SpoofAlertOut
from app.core.attendance_policy import allow_checkout, kernel_of, occurrence_is_open, profile_dict
from app.core.clock import as_local_date, expected_workday, now_local, office_settings, parse_hhmm, today_local
from app.core.mail import notify_absence
from app.core.org_ctx import belongs_to_org, get_current_org_id, scoped
from app.db.models import AccessEvent, Attendance, Enrollment, FaceEmbedding, Occurrence, Offering, Organization, Person, SpoofAlert, User, utcnow
from app.db.session import get_session

router = APIRouter(prefix="/ops", tags=["ops"])


def _as_out(row: Attendance, person: Person, session: Session | None = None) -> AttendanceOut:
    title = None
    if getattr(row, "occurrence_id", None) and session is not None:
        occ = session.get(Occurrence, row.occurrence_id)
        if occ is not None:
            title = occ.title
    return AttendanceOut(
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
        occurrence_id=getattr(row, "occurrence_id", None),
        occurrence_title=title,
        site_id=getattr(row, "site_id", None),
    )


def _present_on(session: Session, person_id: int, day) -> bool:
    rows = session.exec(
        select(Attendance)
        .where(Attendance.person_id == person_id)
        .where(Attendance.decision == "present")
    ).all()
    return any(as_local_date(row.created_at, session) == day for row in rows)


def _maybe_notify_absentees(session: Session, expected: list[Person], present_ids: set[int], workday: bool) -> None:
    office = office_settings(session)
    if not workday or not office.notify_late:
        return
    today = today_local(session)
    now = now_local(session)
    start = datetime.combine(today, parse_hhmm(office.work_start), tzinfo=now.tzinfo)
    grace = start + timedelta(minutes=int(office.late_grace_minutes or 0))
    grace = start + timedelta(minutes=int(office.late_grace_minutes or 0))
    if now < grace:
        return
    marker = f"absent_digest:{today.isoformat()}"
    already = session.exec(
        scoped(select(AccessEvent).where(AccessEvent.kind == "notify").where(AccessEvent.detail == marker), AccessEvent)
    ).first()
    if already is not None:
        return
    missing = [p for p in expected if int(p.id) not in present_ids]
    for person in missing:
        notify_absence(person)
    session.add(AccessEvent(kind="notify", decision="absent_digest", detail=marker, org_id=get_current_org_id()))
    session.commit()


def _maybe_auto_absent(session: Session, expected: list[Person], present_ids: set[int], workday: bool) -> None:
    office = office_settings(session)
    if not workday or not bool(getattr(office, "auto_absent_at_close", False)):
        return
    today = today_local(session)
    now = now_local(session)
    end = datetime.combine(today, parse_hhmm(office.work_end), tzinfo=now.tzinfo)
    if now < end:
        return
    marker = f"auto_absent:{today.isoformat()}"
    already = session.exec(
        scoped(select(AccessEvent).where(AccessEvent.kind == "notify").where(AccessEvent.detail == marker), AccessEvent)
    ).first()
    if already is not None:
        return
    for person in expected:
        if int(person.id) in present_ids:
            continue
        if _present_on(session, int(person.id), today):
            continue
        linked = session.exec(select(User).where(User.person_id == person.id)).first()
        session.add(
            Attendance(
                org_id=person.org_id or get_current_org_id(),
                person_id=int(person.id),
                user_id=int(linked.id) if linked is not None else None,
                decision="absent",
                source="hr",
            )
        )
    session.add(AccessEvent(kind="notify", decision="auto_absent", detail=marker, org_id=get_current_org_id()))
    session.commit()


@router.get("/summary", response_model=OpsSummaryOut)
def summary(
    _admin: User = Depends(require_staff),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> OpsSummaryOut:
    office = office_settings(session)
    today = today_local(session)
    workday = expected_workday(today, session)
    active = session.exec(scoped(select(Person).where(Person.is_active == True), Person)).all()  # noqa: E712
    pending = 0
    awaiting_login = 0
    expected_people: list[Person] = []
    for person in active:
        n_emb = int(
            session.exec(
                select(func.count()).select_from(FaceEmbedding).where(FaceEmbedding.person_id == person.id)
            ).one()
            or 0
        )
        linked = session.exec(select(User).where(User.person_id == person.id)).first()
        if n_emb == 0:
            pending += 1
        if linked is None:
            awaiting_login += 1
        if n_emb > 0:
            expected_people.append(person)

    rows = session.exec(scoped(select(Attendance).order_by(col(Attendance.created_at).desc()).limit(800), Attendance)).all()
    present_ids: set[int] = set()
    late_ids: set[int] = set()
    failed_today = 0
    recent: list[AttendanceOut] = []
    first_in: dict[int, Attendance] = {}
    latest_present: dict[int, Attendance] = {}
    for row in rows:
        if as_local_date(row.created_at, session) != today:
            continue
        person = session.get(Person, row.person_id)
        if person is None:
            continue
        if len(recent) < 12:
            recent.append(_as_out(row, person, session))
        if row.decision == "present":
            pid = int(row.person_id)
            present_ids.add(pid)
            if pid not in latest_present:
                latest_present[pid] = row
            prev = first_in.get(pid)
            if prev is None or row.created_at < prev.created_at:
                first_in[pid] = row
            if row.late:
                late_ids.add(pid)
        elif row.decision == "failed":
            failed_today += 1

    still_out_ids = {pid for pid, rec in latest_present.items() if rec.checked_out_at is None}
    if not allow_checkout(office):
        still_out_ids = set()
    late_today = len(late_ids)

    kernel = kernel_of(office)
    roster_kernel = kernel not in {"visit"}

    in_now: list[BoardPersonOut] = []
    for pid in still_out_ids:
        person = session.get(Person, pid)
        row = first_in.get(pid)
        if person is None or row is None:
            continue
        in_now.append(
            BoardPersonOut(
                person_id=pid,
                person_name=person.name,
                office=person.office,
                checked_in_at=row.created_at,
                late=bool(row.late),
                source=row.source or "web",
            )
        )
    in_now.sort(key=lambda p: p.checked_in_at or today, reverse=True)

    waiting: list[BoardPersonOut] = []
    if workday and roster_kernel:
        for person in expected_people:
            if int(person.id) in present_ids:
                continue
            waiting.append(
                BoardPersonOut(
                    person_id=int(person.id),
                    person_name=person.name,
                    office=person.office,
                )
            )
        waiting.sort(key=lambda p: p.person_name.lower())

    expected_n = len(expected_people) if workday and roster_kernel else 0
    absent_today = max(expected_n - len(present_ids), 0) if workday and roster_kernel else 0

    streaks: list[AbsenceStreakOut] = []
    if workday and roster_kernel:
        for person in expected_people:
            if int(person.id) in present_ids:
                continue
            days = 0
            cursor = today
            for _ in range(21):
                if not expected_workday(cursor, session):
                    cursor -= timedelta(days=1)
                    continue
                if _present_on(session, int(person.id), cursor):
                    break
                days += 1
                cursor -= timedelta(days=1)
            if days >= 2:
                streaks.append(AbsenceStreakOut(person_id=int(person.id), person_name=person.name, days=days))
        streaks.sort(key=lambda s: s.days, reverse=True)

    _maybe_notify_absentees(session, expected_people, present_ids, workday and roster_kernel)
    _maybe_auto_absent(session, expected_people, present_ids, workday and roster_kernel)

    sessions_today: list[SessionTodayOut] = []
    if kernel in {"session", "shift", "visit"}:
        occs = session.exec(
            scoped(select(Occurrence).where(Occurrence.day == today).order_by(col(Occurrence.start)), Occurrence)
        ).all()
        for occ in occs:
            expected = 0
            offering_name = None
            if occ.offering_id is not None:
                offering = session.get(Offering, occ.offering_id)
                offering_name = offering.name if offering is not None else None
                expected = int(
                    session.exec(
                        select(func.count()).select_from(Enrollment).where(Enrollment.offering_id == occ.offering_id)
                    ).one()
                    or 0
                )
            present_n = int(
                session.exec(
                    select(func.count())
                    .select_from(Attendance)
                    .where(Attendance.occurrence_id == occ.id)
                    .where(Attendance.decision == "present")
                ).one()
                or 0
            )
            sessions_today.append(
                SessionTodayOut(
                    id=int(occ.id),
                    title=occ.title,
                    kind=occ.kind,
                    start=occ.start,
                    end=occ.end,
                    overnight=bool(occ.overnight),
                    room=occ.room,
                    offering_id=occ.offering_id,
                    offering_name=offering_name,
                    expected=expected,
                    present=present_n,
                    open=occurrence_is_open(occ, session),
                )
            )

    visits_today = sum(1 for row in rows if as_local_date(row.created_at, session) == today and row.decision == "present")

    spoof_rows = session.exec(
        scoped(select(SpoofAlert).order_by(col(SpoofAlert.created_at).desc()).limit(200), SpoofAlert)
    ).all()
    spoof_today = sum(1 for row in spoof_rows if as_local_date(row.created_at, session) == today)
    profile = profile_dict(office)

    return OpsSummaryOut(
        pending_faces=pending,
        present_today=len(present_ids) if kernel != "visit" else visits_today,
        late_today=late_today,
        failed_today=failed_today,
        absent_today=absent_today,
        awaiting_login=awaiting_login,
        still_out=len(still_out_ids),
        workday=workday,
        tz=office.tz,
        work_start=office.work_start,
        work_end=office.work_end,
        office_name=getattr(office, "office_name", None) or "HQ",
        recent=recent,
        consecutive_absent=streaks[:12],
        in_now=in_now,
        waiting=waiting,
        spoof_today=spoof_today,
        org_type=profile["org_type"],
        kernel=kernel,
        sessions_today=sessions_today,
        visits_today=visits_today,
    )


def _spoof_out(row: SpoofAlert) -> SpoofAlertOut:
    return SpoofAlertOut(
        id=int(row.id),
        actor_username=row.actor_username,
        person_id=row.person_id,
        person_name=row.person_name,
        source=row.source,
        reason=row.reason,
        similarity=None if row.similarity is None else round(float(row.similarity), 4),
        seen=row.seen_at is not None,
        created_at=row.created_at,
    )


@router.get("/spoof-alerts", response_model=list[SpoofAlertOut])
def list_spoof_alerts(
    limit: int = 50,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> list[SpoofAlertOut]:
    rows = session.exec(
        scoped(select(SpoofAlert).order_by(col(SpoofAlert.created_at).desc()).limit(min(limit, 200)), SpoofAlert)
    ).all()
    return [_spoof_out(row) for row in rows]


@router.get("/spoof-alerts/{alert_id}/image")
def spoof_alert_image(
    alert_id: int,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> Response:
    row = belongs_to_org(session.get(SpoofAlert, alert_id), detail="alert_not_found")
    if not row.image:
        raise HTTPException(404, detail="alert_not_found")
    return Response(content=row.image, media_type="image/jpeg")


@router.post("/spoof-alerts/{alert_id}/seen", response_model=SpoofAlertOut)
def mark_spoof_seen(
    alert_id: int,
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> SpoofAlertOut:
    row = belongs_to_org(session.get(SpoofAlert, alert_id), detail="alert_not_found")
    if row.seen_at is None:
        row.seen_at = utcnow()
        session.add(row)
        session.commit()
        session.refresh(row)
    return _spoof_out(row)
