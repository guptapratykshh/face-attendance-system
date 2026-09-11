"""Employee attendance check-in, check-out, kiosk punch, and reports."""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlmodel import Session, col, select

from app.api.deps import get_current_user, get_runtime, require_org, require_people, require_staff
from app.api.routes._common import face_info, log_event, read_image
from app.api.schemas import AttendanceManualIn, AttendanceOut, AttendanceUpdate
from app.core.attendance_policy import (
    allow_checkout,
    assert_punch_location,
    checkout_row,
    find_existing_present,
    is_late_for,
    kernel_of,
    present_for_occurrence,
    resolve_occurrence,
    todays_present,
    track_early_leave,
    track_late,
)
from app.core.clock import as_local_date, is_early_leave, now_local, office_settings, today_local
from app.core.config import settings
from app.core.mail import notify_fail_streak, notify_late_arrival
from app.core.org_ctx import belongs_to_org, gallery_allowed_ids, get_current_org_id, scoped
from app.core.rate_limit import checkin_limiter, client_ip
from app.core.roles import is_staff
from app.db.models import Attendance, Occurrence, Organization, Person, User
from app.db.session import get_session
from app.encoders.base import FaceEncoder
from app.liveness.service import liveness_service
from app.risk.behaviour import behaviour_features, behaviour_risk
from app.risk.fusion import presence_trust
from app.runtime import Runtime

log = logging.getLogger(__name__)

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _attendance_out(
    row: Attendance,
    person: Person,
    *,
    already_marked: bool = False,
    threshold: float | None = None,
    face=None,
    session: Session | None = None,
) -> AttendanceOut:
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
        already_marked=already_marked,
        created_at=row.created_at,
        checked_out_at=row.checked_out_at,
        source=row.source or "web",
        late=bool(row.late),
        early_leave=bool(getattr(row, "early_leave", False)),
        threshold=threshold,
        face=face,
        occurrence_id=getattr(row, "occurrence_id", None),
        occurrence_title=title,
        site_id=getattr(row, "site_id", None),
        trust_score=None if row.trust_score is None else round(float(row.trust_score), 4),
        trust=_trust_breakdown(row),
    )


def _trust_breakdown(row: Attendance) -> dict | None:
    raw = getattr(row, "trust_breakdown_json", None)
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _todays_present(session: Session, person_id: int) -> Attendance | None:
    return todays_present(session, person_id)


def _require_live(challenge_id: str | None, user_id: int) -> None:
    if not settings.require_liveness:
        return
    if not challenge_id:
        raise HTTPException(400, detail="liveness_required")
    if not liveness_service.consume_live(challenge_id, user_id):
        raise HTTPException(400, detail="liveness_required")


def _score_trust(
    session: Session,
    row: Attendance,
    *,
    challenge_id: str | None,
    threshold: float,
) -> dict | None:
    """Attach the fused presence-trust score to a saved punch.

    Advisory for now: it records and explains risk for HR review rather than blocking, because the
    behaviour weights are tuned on synthetic fraud until a site has real labelled history.
    """
    if row.id is None or row.person_id is None:
        return None
    liveness = liveness_service.result_for(challenge_id)
    try:
        behaviour = behaviour_risk(
            behaviour_features(
                session,
                person_id=int(row.person_id),
                at=row.created_at,
                lat=row.latitude,
                lng=row.longitude,
                site_id=row.site_id,
                similarity=row.similarity,
            )
        )
        trust = presence_trust(
            similarity=row.similarity,
            threshold=threshold,
            liveness=liveness.get("texture") if isinstance(liveness.get("texture"), dict) else None,
            capture_path=liveness.get("capture_path")
            if isinstance(liveness.get("capture_path"), dict)
            else None,
            behaviour=behaviour,
        )
    except Exception:
        log.exception("could not score presence trust")
        return None

    trust["behaviour"] = behaviour
    row.trust_score = trust.get("trust")
    row.trust_breakdown_json = json.dumps(trust)
    session.add(row)
    session.commit()
    session.refresh(row)
    return trust


def _parse_coord(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise HTTPException(400, detail="invalid_location") from exc


def _notify_enabled(session: Session) -> bool:
    return bool(office_settings(session).notify_late)


def _failed_today(session: Session, person_id: int) -> int:
    today = today_local(session)
    rows = session.exec(
        select(Attendance).where(Attendance.person_id == person_id).where(Attendance.decision == "failed")
    ).all()
    return sum(1 for row in rows if as_local_date(row.created_at, session) == today)


def _linked_person(session: Session, user: User) -> Person:
    if is_staff(user) and user.person_id is None:
        raise HTTPException(403, detail="admins mark attendance from the employee account")
    if user.person_id is None:
        raise HTTPException(400, detail="no linked identity — register again or ask an admin")
    person = session.get(Person, user.person_id)
    if person is None:
        raise HTTPException(400, detail="linked identity is missing")
    if person.is_active is False:
        raise HTTPException(403, detail="account_deactivated")
    return person


@router.get("/today", response_model=AttendanceOut | None)
def today_status(
    occurrence_id: int | None = None,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AttendanceOut | None:
    if user.person_id is None:
        return None
    person = session.get(Person, user.person_id)
    if person is None:
        return None
    if occurrence_id is not None:
        row = present_for_occurrence(session, int(person.id), occurrence_id)
    else:
        row = _todays_present(session, int(person.id))
    if row is None:
        return None
    return _attendance_out(row, person, already_marked=True, session=session)


@router.post("/check-in", response_model=AttendanceOut)
async def check_in(
    request: Request,
    image: UploadFile = File(...),
    challenge_id: str | None = Form(default=None),
    latitude: str | None = Form(default=None),
    longitude: str | None = Form(default=None),
    occurrence_id: str | None = Form(default=None),
    site_id: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    rt: Runtime = Depends(get_runtime),
) -> AttendanceOut:
    checkin_limiter.check(f"checkin:{user.id}:{client_ip(request)}")
    person = _linked_person(session, user)
    probe = rt.gallery.embedding_of(int(person.id), org_id=person.org_id)
    if probe is None:
        raise HTTPException(400, detail="face_not_enrolled")

    cfg = office_settings(session)
    kernel = kernel_of(cfg)
    occ_id = int(occurrence_id) if occurrence_id and str(occurrence_id).isdigit() else None
    requested_site = int(site_id) if site_id and str(site_id).isdigit() else None
    occurrence = None
    if kernel in {"session", "shift"}:
        occurrence = resolve_occurrence(session, person=person, occurrence_id=occ_id, required=True)
        occ_id = int(occurrence.id) if occurrence is not None else None
    elif kernel == "visit" and occ_id is not None:
        occurrence = resolve_occurrence(session, person=person, occurrence_id=occ_id, required=False)

    existing = find_existing_present(session, int(person.id), occ_id)
    if existing is not None:
        return _attendance_out(existing, person, already_marked=True, threshold=rt.verify_threshold, session=session)

    lat = _parse_coord(latitude)
    lng = _parse_coord(longitude)
    site = assert_punch_location(lat, lng, session, requested_site or getattr(occurrence, "site_id", None))
    _require_live(challenge_id, int(user.id))

    face = rt.pipeline.embed_single(await read_image(image))
    similarity = float(FaceEncoder.similarity(face.embedding[None], probe[None])[0])
    match = similarity >= rt.verify_threshold
    late = bool(match and is_late_for(session, person=person, occurrence=occurrence))
    row = Attendance(
        org_id=person.org_id or get_current_org_id(),
        person_id=int(person.id),
        user_id=int(user.id),
        occurrence_id=occ_id,
        site_id=site,
        decision="present" if match else "failed",
        similarity=similarity,
        encoder=rt.encoder_name,
        source="web",
        late=late,
        latitude=lat,
        longitude=lng,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    if row.id is not None and lat is not None and lng is not None:
        from app.core.geo import set_punch_geom

        set_punch_geom(session, int(row.id), lat, lng)
        session.commit()
    _score_trust(session, row, challenge_id=challenge_id, threshold=rt.verify_threshold)
    log_event(
        session,
        kind="attendance",
        decision="present" if match else "failed",
        person=person,
        similarity=similarity,
        encoder=rt.encoder_name,
        detail="check-in" + (" late" if late else ""),
    )
    if match and late and _notify_enabled(session):
        notify_late_arrival(person)
    if not match and _notify_enabled(session) and _failed_today(session, int(person.id)) >= 3:
        notify_fail_streak(person, _failed_today(session, int(person.id)))
    return _attendance_out(
        row,
        person,
        threshold=rt.verify_threshold,
        face=face_info(face),
        session=session,
    )


@router.post("/check-out", response_model=AttendanceOut)
async def check_out(
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    rt: Runtime = Depends(get_runtime),
) -> AttendanceOut:
    cfg = office_settings(session)
    if not allow_checkout(cfg):
        raise HTTPException(400, detail="checkout_disabled")
    person = _linked_person(session, user)
    existing = checkout_row(session, int(person.id))
    if existing is None:
        raise HTTPException(400, detail="not_checked_in")
    if existing.checked_out_at is not None:
        return _attendance_out(existing, person, already_marked=True, session=session)

    image_bytes: bytes | None = None
    challenge_id: str | None = None
    ctype = request.headers.get("content-type", "")
    if "multipart/form-data" in ctype:
        form = await request.form()
        challenge_id = str(form.get("challenge_id") or "") or None
        upload = form.get("image")
        if upload is not None and hasattr(upload, "read"):
            image_bytes = await upload.read()
            if not image_bytes:
                image_bytes = None

    face = None
    if image_bytes:
        probe = rt.gallery.embedding_of(int(person.id), org_id=person.org_id)
        if probe is None:
            raise HTTPException(400, detail="face_not_enrolled")
        _require_live(challenge_id, int(user.id))
        face = rt.pipeline.embed_single(image_bytes)
        similarity = float(FaceEncoder.similarity(face.embedding[None], probe[None])[0])
        if similarity < rt.verify_threshold:
            log_event(
                session,
                kind="attendance",
                decision="failed",
                person=person,
                similarity=similarity,
                encoder=rt.encoder_name,
                detail="check-out face mismatch",
            )
            raise HTTPException(400, detail="face_mismatch")
        existing.similarity = similarity

    existing.checked_out_at = now_local(session)
    existing.early_leave = bool(track_early_leave(cfg) and is_early_leave(session=session, person=person))
    session.add(existing)
    session.commit()
    session.refresh(existing)
    log_event(
        session,
        kind="attendance",
        decision="checked_out",
        person=person,
        detail="check-out" + (" early" if existing.early_leave else ""),
    )
    return _attendance_out(existing, person, face=face_info(face) if face is not None else None, session=session)


@router.post("/kiosk", response_model=AttendanceOut)
async def kiosk_punch(
    request: Request,
    staff: User = Depends(require_staff),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
    rt: Runtime = Depends(get_runtime),
) -> AttendanceOut:
    form = await request.form()
    pin_code = str(form.get("pin") or "").strip()
    challenge_id = str(form.get("challenge_id") or "") or None
    lat = _parse_coord(str(form.get("latitude") or "") or None)
    lng = _parse_coord(str(form.get("longitude") or "") or None)
    occ_raw = str(form.get("occurrence_id") or "").strip()
    occ_id = int(occ_raw) if occ_raw.isdigit() else None
    site_raw = str(form.get("site_id") or "").strip()
    requested_site = int(site_raw) if site_raw.isdigit() else None
    # Kiosk sits at the office; GPS is not required here unless a site fence is active.

    person: Person | None = None
    similarity: float | None = None
    face = None
    if pin_code:
        office = office_settings(session)
        if not office or not getattr(office, "allow_kiosk_pin", False):
            raise HTTPException(403, detail="kiosk_pin_disabled")
        person = session.exec(
            scoped(select(Person).where(Person.employee_id == pin_code), Person)
        ).first()
        if person is None or person.is_active is False:
            raise HTTPException(404, detail="face_not_recognized")
    else:
        upload = form.get("image")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(400, detail="image_or_pin_required")
        _require_live(challenge_id, int(staff.id))
        image_bytes = await upload.read()
        if not image_bytes:
            raise HTTPException(400, detail="image_or_pin_required")
        face = rt.pipeline.embed_single(image_bytes)
        matches = rt.gallery.search(face.embedding, top_k=1, allowed_ids=gallery_allowed_ids(session))
        identified = bool(matches) and matches[0].similarity >= rt.identify_threshold
        if not identified:
            log_event(
                session,
                kind="attendance",
                decision="failed",
                similarity=matches[0].similarity if matches else None,
                encoder=rt.encoder_name,
                detail="kiosk unidentified",
            )
            raise HTTPException(404, detail="face_not_recognized")
        hit = matches[0]
        person = session.get(Person, hit.person_id)
        if person is None or person.is_active is False:
            raise HTTPException(404, detail="face_not_recognized")
        similarity = float(hit.similarity)

    cfg = office_settings(session)
    kernel = kernel_of(cfg)
    occurrence = None
    if kernel in {"session", "shift"}:
        if occ_id is None:
            raise HTTPException(400, detail="occurrence_required")
        occurrence = belongs_to_org(session.get(Occurrence, occ_id), detail="occurrence_not_found")
    elif kernel == "visit" and occ_id is not None:
        occurrence = belongs_to_org(session.get(Occurrence, occ_id), detail="occurrence_not_found")

    existing = find_existing_present(session, int(person.id), occ_id)
    if existing is not None:
        return _attendance_out(
            existing,
            person,
            already_marked=True,
            threshold=rt.identify_threshold,
            face=face_info(face) if face is not None else None,
            session=session,
        )
    linked = session.exec(select(User).where(User.person_id == person.id)).first()
    late = is_late_for(session, person=person, occurrence=occurrence)
    row = Attendance(
        org_id=person.org_id or get_current_org_id(),
        person_id=int(person.id),
        user_id=int(linked.id) if linked is not None else None,
        occurrence_id=occ_id,
        site_id=requested_site or getattr(occurrence, "site_id", None),
        decision="present",
        similarity=similarity,
        encoder=rt.encoder_name,
        source="kiosk" if not pin_code else "pin",
        late=late,
        latitude=lat,
        longitude=lng,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    if row.id is not None and lat is not None and lng is not None:
        from app.core.geo import set_punch_geom

        set_punch_geom(session, int(row.id), lat, lng)
        session.commit()
    _score_trust(session, row, challenge_id=challenge_id, threshold=rt.identify_threshold)
    log_event(
        session,
        kind="attendance",
        decision="present",
        person=person,
        similarity=similarity,
        encoder=rt.encoder_name,
        detail=("kiosk pin" if pin_code else "kiosk") + (" late" if late else ""),
    )
    if late and _notify_enabled(session):
        notify_late_arrival(person)
    return _attendance_out(
        row,
        person,
        threshold=rt.identify_threshold,
        face=face_info(face) if face is not None else None,
        session=session,
    )


@router.get("/me", response_model=list[AttendanceOut])
def my_attendance(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[AttendanceOut]:
    rows = session.exec(
        select(Attendance).where(Attendance.user_id == user.id).order_by(col(Attendance.created_at).desc())
    ).all()
    out: list[AttendanceOut] = []
    for row in rows:
        person = session.get(Person, row.person_id)
        if person is None:
            continue
        out.append(_attendance_out(row, person, session=session))
    return out


def _filtered_rows(
    session: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    person_id: int | None,
    decision: str | None,
    limit: int,
) -> list[tuple[Attendance, Person]]:
    stmt = scoped(select(Attendance).order_by(col(Attendance.created_at).desc()).limit(limit), Attendance)
    if person_id is not None:
        stmt = stmt.where(Attendance.person_id == person_id)
    if decision:
        stmt = stmt.where(Attendance.decision == decision)
    rows = list(session.exec(stmt).all())
    out: list[tuple[Attendance, Person]] = []
    for row in rows:
        person = session.get(Person, row.person_id)
        if person is None:
            continue
        local = as_local_date(row.created_at, session)
        if date_from and local < date_from:
            continue
        if date_to and local > date_to:
            continue
        out.append((row, person))
    return out


@router.get("", response_model=list[AttendanceOut])
def list_attendance(
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    person_id: int | None = None,
    decision: str | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
    _admin: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> list[AttendanceOut]:
    pairs = _filtered_rows(
        session,
        date_from=date_from,
        date_to=date_to,
        person_id=person_id,
        decision=decision,
        limit=limit,
    )
    return [_attendance_out(row, person, session=session) for row, person in pairs]


_DECISIONS = frozenset({"present", "failed", "absent", "excused"})


def _apply_decision(row: Attendance, decision: str) -> None:
    if decision not in _DECISIONS:
        raise HTTPException(400, detail="invalid_decision")
    row.decision = decision
    if decision != "present":
        row.late = False
        row.early_leave = False
        row.checked_out_at = None


@router.post("/manual", response_model=AttendanceOut)
def manual_attendance(
    body: AttendanceManualIn,
    staff: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> AttendanceOut:
    person = belongs_to_org(session.get(Person, body.person_id), detail="person not found")
    decision = (body.decision or "present").strip().lower()
    if decision not in _DECISIONS:
        raise HTTPException(400, detail="invalid_decision")
    existing = (
        find_existing_present(session, int(person.id), body.occurrence_id) if decision == "present" else None
    )
    linked = session.exec(select(User).where(User.person_id == person.id)).first()
    if existing is not None:
        row = existing
        _apply_decision(row, decision)
        row.late = bool(body.late) if decision == "present" and track_late(office_settings(session)) else False
        row.early_leave = (
            bool(body.early_leave) if decision == "present" and track_early_leave(office_settings(session)) else False
        )
        row.source = "hr"
        if body.occurrence_id is not None:
            row.occurrence_id = body.occurrence_id
    else:
        row = Attendance(
            org_id=person.org_id or get_current_org_id(),
            person_id=int(person.id),
            user_id=int(linked.id) if linked is not None else int(staff.id),
            occurrence_id=body.occurrence_id,
            decision=decision,
            source="hr",
            late=bool(body.late) if decision == "present" else False,
            early_leave=bool(body.early_leave) if decision == "present" else False,
        )
        session.add(row)
    session.commit()
    session.refresh(row)
    note = (body.note or "").strip()
    log_event(
        session,
        kind="attendance",
        decision=decision,
        person=person,
        detail="hr override" + (f": {note}" if note else ""),
    )
    return _attendance_out(row, person, session=session)


@router.patch("/{attendance_id}", response_model=AttendanceOut)
def update_attendance(
    attendance_id: int,
    body: AttendanceUpdate,
    _staff: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> AttendanceOut:
    row = belongs_to_org(session.get(Attendance, attendance_id), detail="attendance not found")
    person = session.get(Person, row.person_id)
    if person is None:
        raise HTTPException(404, detail="person not found")
    fields = body.model_dump(exclude_unset=True)
    if "decision" in fields and fields["decision"] is not None:
        _apply_decision(row, str(fields["decision"]).strip().lower())
    if "late" in fields and fields["late"] is not None and row.decision == "present":
        row.late = bool(fields["late"])
    if "early_leave" in fields and fields["early_leave"] is not None and row.decision == "present":
        row.early_leave = bool(fields["early_leave"])
    if "checked_out" in fields and fields["checked_out"] is not None:
        if fields["checked_out"]:
            if not allow_checkout(office_settings(session)):
                raise HTTPException(400, detail="checkout_disabled")
            row.checked_out_at = now_local(session)
            if row.decision == "present":
                row.early_leave = bool(
                    track_early_leave(office_settings(session)) and is_early_leave(session=session, person=person)
                )
        else:
            row.checked_out_at = None
            row.early_leave = False
    row.source = "hr"
    session.add(row)
    session.commit()
    session.refresh(row)
    log_event(
        session,
        kind="attendance",
        decision=row.decision,
        person=person,
        detail="hr edited attendance",
    )
    return _attendance_out(row, person, session=session)


@router.get("/export")
def export_attendance(
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    person_id: int | None = None,
    decision: str | None = None,
    _admin: User = Depends(require_people),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    pairs = _filtered_rows(
        session,
        date_from=date_from,
        date_to=date_to,
        person_id=person_id,
        decision=decision,
        limit=5000,
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "person",
            "employee_id",
            "decision",
            "late",
            "early_leave",
            "source",
            "checked_in",
            "checked_out",
            "similarity",
            "occurrence",
            "site_id",
        ]
    )
    for row, person in pairs:
        occ_title = ""
        if getattr(row, "occurrence_id", None):
            occ = session.get(Occurrence, row.occurrence_id)
            occ_title = occ.title if occ is not None else str(row.occurrence_id)
        writer.writerow(
            [
                row.id,
                person.name,
                person.employee_id or "",
                row.decision,
                row.late,
                getattr(row, "early_leave", False),
                row.source,
                row.created_at.isoformat() if row.created_at else "",
                row.checked_out_at.isoformat() if row.checked_out_at else "",
                "" if row.similarity is None else f"{row.similarity:.4f}",
                occ_title,
                getattr(row, "site_id", None) or "",
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance.csv"},
    )
