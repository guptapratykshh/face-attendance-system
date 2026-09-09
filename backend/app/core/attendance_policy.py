"""Organization type presets and attendance-kernel helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.core.clock import as_local_date, office_settings, parse_hhmm, today_local, zone
from app.core.org_ctx import get_current_org_id
from app.db.models import Attendance, Enrollment, Occurrence, Organization, Person, Site

ORG_TYPES = (
    "workplace",
    "school",
    "college",
    "training",
    "shift_ops",
    "field",
    "event",
    "membership",
    "custom",
)
KERNELS = ("daily_presence", "daily_inout", "session", "shift", "visit")

_PROFILE_FIELDS = (
    "kernel",
    "subject_label",
    "subject_label_plural",
    "staff_label",
    "group_label",
    "id_label",
    "require_checkout",
    "allow_checkout",
    "track_late",
    "track_early_leave",
    "geofence_on_self_punch",
    "auto_absent_at_close",
    "allow_multiple_present_per_day",
)

ORG_PRESETS: dict[str, dict[str, Any]] = {
    "workplace": {
        "title": "Workplace / office",
        "blurb": "People check in once per day and may check out. Late and early leave follow office hours.",
        "kernel": "daily_inout",
        "subject_label": "employee",
        "subject_label_plural": "employees",
        "staff_label": "HR",
        "group_label": "department",
        "id_label": "Employee ID",
        "require_checkout": False,
        "allow_checkout": True,
        "track_late": True,
        "track_early_leave": True,
        "geofence_on_self_punch": True,
        "auto_absent_at_close": False,
        "allow_multiple_present_per_day": False,
    },
    "school": {
        "title": "School (once a day)",
        "blurb": "Students mark once per day at the gate or homeroom. No checkout.",
        "kernel": "daily_presence",
        "subject_label": "student",
        "subject_label_plural": "students",
        "staff_label": "registrar",
        "group_label": "class",
        "id_label": "Student ID",
        "require_checkout": False,
        "allow_checkout": False,
        "track_late": True,
        "track_early_leave": False,
        "geofence_on_self_punch": False,
        "auto_absent_at_close": True,
        "allow_multiple_present_per_day": False,
    },
    "college": {
        "title": "College / university",
        "blurb": "Students mark each lecture, lab, or tutorial. Many marks per day.",
        "kernel": "session",
        "subject_label": "student",
        "subject_label_plural": "students",
        "staff_label": "registrar",
        "group_label": "course",
        "id_label": "Student ID",
        "require_checkout": False,
        "allow_checkout": False,
        "track_late": True,
        "track_early_leave": False,
        "geofence_on_self_punch": False,
        "auto_absent_at_close": False,
        "allow_multiple_present_per_day": True,
    },
    "training": {
        "title": "Training / coaching",
        "blurb": "Learners mark each batch or period on the timetable.",
        "kernel": "session",
        "subject_label": "learner",
        "subject_label_plural": "learners",
        "staff_label": "coordinator",
        "group_label": "batch",
        "id_label": "Learner ID",
        "require_checkout": False,
        "allow_checkout": False,
        "track_late": True,
        "track_early_leave": False,
        "geofence_on_self_punch": False,
        "auto_absent_at_close": False,
        "allow_multiple_present_per_day": True,
    },
    "shift_ops": {
        "title": "Shifts (factory, hospital, retail)",
        "blurb": "People clock in and out against an assigned shift. Windows may cross midnight.",
        "kernel": "shift",
        "subject_label": "employee",
        "subject_label_plural": "employees",
        "staff_label": "HR",
        "group_label": "shift",
        "id_label": "Employee ID",
        "require_checkout": False,
        "allow_checkout": True,
        "track_late": True,
        "track_early_leave": True,
        "geofence_on_self_punch": True,
        "auto_absent_at_close": False,
        "allow_multiple_present_per_day": True,
    },
    "field": {
        "title": "Field / multi-site",
        "blurb": "Daily in and out, locked to a site geofence (job sites, branches, client offices).",
        "kernel": "daily_inout",
        "subject_label": "employee",
        "subject_label_plural": "employees",
        "staff_label": "HR",
        "group_label": "site",
        "id_label": "Employee ID",
        "require_checkout": False,
        "allow_checkout": True,
        "track_late": True,
        "track_early_leave": True,
        "geofence_on_self_punch": True,
        "auto_absent_at_close": False,
        "allow_multiple_present_per_day": False,
    },
    "event": {
        "title": "Events / exams / conferences",
        "blurb": "Attendees check in at the gate or for a named session. No daily absence roster.",
        "kernel": "visit",
        "subject_label": "attendee",
        "subject_label_plural": "attendees",
        "staff_label": "staff",
        "group_label": "event",
        "id_label": "Pass ID",
        "require_checkout": False,
        "allow_checkout": False,
        "track_late": False,
        "track_early_leave": False,
        "geofence_on_self_punch": False,
        "auto_absent_at_close": False,
        "allow_multiple_present_per_day": True,
    },
    "membership": {
        "title": "Gym / club / members",
        "blurb": "Members check in (and optionally out) per visit. No expected-absent list.",
        "kernel": "visit",
        "subject_label": "member",
        "subject_label_plural": "members",
        "staff_label": "staff",
        "group_label": "plan",
        "id_label": "Member ID",
        "require_checkout": False,
        "allow_checkout": True,
        "track_late": False,
        "track_early_leave": False,
        "geofence_on_self_punch": False,
        "auto_absent_at_close": False,
        "allow_multiple_present_per_day": True,
    },
}


def kernel_of(cfg: Organization | None) -> str:
    value = getattr(cfg, "kernel", None) or "daily_inout"
    return value if value in KERNELS else "daily_inout"


def allow_checkout(cfg: Organization | None) -> bool:
    if cfg is None:
        return True
    if getattr(cfg, "allow_checkout", None) is not None:
        return bool(cfg.allow_checkout)
    return kernel_of(cfg) in {"daily_inout", "shift"}


def track_late(cfg: Organization | None) -> bool:
    if cfg is None:
        return True
    return bool(getattr(cfg, "track_late", True))


def track_early_leave(cfg: Organization | None) -> bool:
    if cfg is None:
        return True
    return bool(getattr(cfg, "track_early_leave", True))


def geofence_on_self_punch(cfg: Organization | None) -> bool:
    if cfg is None:
        return True
    return bool(getattr(cfg, "geofence_on_self_punch", True))


def profile_dict(cfg: Organization | None) -> dict[str, Any]:
    preset = ORG_PRESETS.get("workplace", {})
    org_type = getattr(cfg, "org_type", None) or "workplace"
    if org_type not in ORG_TYPES:
        org_type = "workplace"
    return {
        "org_type": org_type,
        "kernel": kernel_of(cfg),
        "subject_label": getattr(cfg, "subject_label", None) or preset["subject_label"],
        "subject_label_plural": getattr(cfg, "subject_label_plural", None) or preset["subject_label_plural"],
        "staff_label": getattr(cfg, "staff_label", None) or preset["staff_label"],
        "group_label": getattr(cfg, "group_label", None) or preset["group_label"],
        "id_label": getattr(cfg, "id_label", None) or preset["id_label"],
        "require_checkout": bool(getattr(cfg, "require_checkout", False)),
        "allow_checkout": allow_checkout(cfg),
        "track_late": track_late(cfg),
        "track_early_leave": track_early_leave(cfg),
        "geofence_on_self_punch": geofence_on_self_punch(cfg),
        "auto_absent_at_close": bool(getattr(cfg, "auto_absent_at_close", False)),
        "allow_multiple_present_per_day": bool(getattr(cfg, "allow_multiple_present_per_day", False)),
    }


def preset_catalog() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key, preset in ORG_PRESETS.items():
        item = {"org_type": key, **preset}
        out.append(item)
    out.append(
        {
            "org_type": "custom",
            "title": "Custom",
            "blurb": "Keep current labels and flags, and change the kernel yourself.",
            "kernel": "daily_inout",
        }
    )
    return out


def apply_org_type(row: Organization, org_type: str) -> None:
    if org_type not in ORG_TYPES:
        raise HTTPException(400, detail="invalid_org_type")
    row.org_type = org_type
    preset = ORG_PRESETS.get(org_type)
    if not preset:
        return
    for key in _PROFILE_FIELDS:
        setattr(row, key, preset[key])


def occurrence_window(occ: Occurrence, session: Session | None = None) -> tuple[datetime, datetime]:
    tz = zone(session)
    start = datetime.combine(occ.day, parse_hhmm(occ.start or "00:00"), tzinfo=tz)
    end = datetime.combine(occ.day, parse_hhmm(occ.end or "23:59"), tzinfo=tz)
    if bool(getattr(occ, "overnight", False)) or end <= start:
        end = end + timedelta(days=1)
    return start, end


def occurrence_is_open(occ: Occurrence, session: Session | None = None, *, lead_minutes: int = 15) -> bool:
    from app.core.clock import now_local

    now = now_local(session)
    start, end = occurrence_window(occ, session)
    return start - timedelta(minutes=lead_minutes) <= now <= end


def is_late_for(
    session: Session,
    person: Person | None = None,
    occurrence: Occurrence | None = None,
    when: datetime | None = None,
) -> bool:
    from app.core.clock import is_late, now_local

    cfg = office_settings(session)
    if not track_late(cfg):
        return False
    instant = when or now_local(session)
    if occurrence is not None:
        start, _end = occurrence_window(occurrence, session)
        threshold = start + timedelta(minutes=int(cfg.late_grace_minutes or 0))
        return instant > threshold
    return is_late(when=instant, session=session, person=person)


def todays_present(session: Session, person_id: int) -> Attendance | None:
    today = today_local(session)
    rows = session.exec(
        select(Attendance)
        .where(Attendance.person_id == person_id)
        .where(Attendance.decision == "present")
        .order_by(col(Attendance.created_at).desc())
    ).all()
    for row in rows:
        if as_local_date(row.created_at, session) == today:
            return row
    return None


def present_for_occurrence(session: Session, person_id: int, occurrence_id: int) -> Attendance | None:
    return session.exec(
        select(Attendance)
        .where(Attendance.person_id == person_id)
        .where(Attendance.occurrence_id == occurrence_id)
        .where(Attendance.decision == "present")
        .order_by(col(Attendance.created_at).desc())
    ).first()


def open_occurrences(
    session: Session,
    *,
    person_id: int | None = None,
    kind: str | None = None,
) -> list[Occurrence]:
    today = today_local(session)
    yesterday = today - timedelta(days=1)
    stmt = select(Occurrence).where(col(Occurrence.day).in_([yesterday, today]))
    oid = get_current_org_id()
    if oid is not None:
        stmt = stmt.where(Occurrence.org_id == oid)
    if kind:
        stmt = stmt.where(Occurrence.kind == kind)
    rows = list(session.exec(stmt).all())
    enrolled: set[int] | None = None
    if person_id is not None:
        enrolled = {
            int(e.offering_id)
            for e in session.exec(select(Enrollment).where(Enrollment.person_id == person_id)).all()
            if e.offering_id is not None
        }
    out: list[Occurrence] = []
    for occ in rows:
        if not occurrence_is_open(occ, session):
            continue
        if enrolled is not None and occ.offering_id is not None and int(occ.offering_id) not in enrolled:
            continue
        out.append(occ)
    out.sort(key=lambda o: (o.day, o.start or "", o.id or 0))
    return out


def resolve_occurrence(
    session: Session,
    *,
    person: Person,
    occurrence_id: int | None,
    required: bool,
) -> Occurrence | None:
    if occurrence_id is not None:
        occ = session.get(Occurrence, occurrence_id)
        if occ is None:
            raise HTTPException(404, detail="occurrence_not_found")
        oid = get_current_org_id()
        if oid is not None and occ.org_id is not None and int(occ.org_id) != int(oid):
            raise HTTPException(404, detail="occurrence_not_found")
        if occ.offering_id is not None:
            enrolled = session.exec(
                select(Enrollment)
                .where(Enrollment.person_id == person.id)
                .where(Enrollment.offering_id == occ.offering_id)
            ).first()
            if enrolled is None:
                raise HTTPException(403, detail="not_enrolled")
        return occ
    if not required:
        return None
    open_now = open_occurrences(session, person_id=int(person.id))
    if len(open_now) == 1:
        return open_now[0]
    if len(open_now) == 0:
        raise HTTPException(400, detail="no_open_session")
    raise HTTPException(400, detail="occurrence_required")


def find_existing_present(
    session: Session,
    person_id: int,
    occurrence_id: int | None = None,
) -> Attendance | None:
    cfg = office_settings(session)
    kernel = kernel_of(cfg)
    if kernel == "visit":
        if occurrence_id is None:
            return None
        return present_for_occurrence(session, person_id, occurrence_id)
    if kernel in {"session", "shift"}:
        if occurrence_id is None:
            raise HTTPException(400, detail="occurrence_required")
        return present_for_occurrence(session, person_id, occurrence_id)
    return todays_present(session, person_id)


def checkout_row(
    session: Session,
    person_id: int,
    occurrence_id: int | None = None,
) -> Attendance | None:
    cfg = office_settings(session)
    kernel = kernel_of(cfg)
    if kernel in {"session", "shift"}:
        if occurrence_id is not None:
            return present_for_occurrence(session, person_id, occurrence_id)
        open_now = open_occurrences(session, person_id=person_id)
        for occ in reversed(open_now):
            row = present_for_occurrence(session, person_id, int(occ.id))
            if row is not None and row.checked_out_at is None:
                return row
        return todays_present(session, person_id)
    if kernel == "visit":
        rows = session.exec(
            select(Attendance)
            .where(Attendance.person_id == person_id)
            .where(Attendance.decision == "present")
            .order_by(col(Attendance.created_at).desc())
        ).all()
        for row in rows:
            if as_local_date(row.created_at, session) == today_local(session) and row.checked_out_at is None:
                return row
        return None
    return todays_present(session, person_id)


def assert_punch_location(
    lat: float | None,
    lng: float | None,
    session: Session,
    site_id: int | None = None,
) -> int | None:
    from app.core.clock import assert_geofence, geofence_active

    cfg = office_settings(session)
    if not geofence_on_self_punch(cfg):
        return site_id
    if site_id is not None:
        site = session.get(Site, site_id)
        if site is None:
            raise HTTPException(404, detail="site_not_found")
        oid = get_current_org_id()
        if oid is not None and site.org_id is not None and int(site.org_id) != int(oid):
            raise HTTPException(404, detail="site_not_found")
        _assert_inside_site(lat, lng, site, session)
        return int(site.id)
    site_stmt = select(Site)
    oid = get_current_org_id()
    if oid is not None:
        site_stmt = site_stmt.where(Site.org_id == oid)
    sites = list(session.exec(site_stmt).all())
    fenced = [site for site in sites if site.lat is not None and site.lng is not None]
    if fenced:
        if lat is None or lng is None:
            raise HTTPException(400, detail="location_required")
        for site in fenced:
            if _inside_site(lat, lng, site, session):
                return int(site.id) if site.id is not None else None
        raise HTTPException(403, detail="outside_geofence")
    if geofence_active(session):
        assert_geofence(lat, lng, session)
    return None


def _inside_site(lat: float, lng: float, site: Site, session: Session | None = None) -> bool:
    from app.core.geo import point_within_site

    if session is None:
        from app.core.clock import haversine_m

        if site.lat is None or site.lng is None:
            return False
        radius = float(site.radius_m or 0)
        if radius <= 0:
            return False
        return haversine_m(float(site.lat), float(site.lng), float(lat), float(lng)) <= radius
    return point_within_site(session, lat, lng, site)


def _assert_inside_site(
    lat: float | None, lng: float | None, site: Site, session: Session | None = None
) -> None:
    if lat is None or lng is None:
        raise HTTPException(400, detail="location_required")
    if not _inside_site(lat, lng, site, session):
        raise HTTPException(403, detail="outside_geofence")


def location_gate_active(session: Session | None) -> bool:
    from app.core.clock import geofence_active

    cfg = office_settings(session)
    if not geofence_on_self_punch(cfg):
        return False
    if session is not None:
        site_stmt = select(Site)
        oid = get_current_org_id()
        if oid is not None:
            site_stmt = site_stmt.where(Site.org_id == oid)
        for site in session.exec(site_stmt).all():
            if site.lat is not None and site.lng is not None:
                return True
    return geofence_active(session)
