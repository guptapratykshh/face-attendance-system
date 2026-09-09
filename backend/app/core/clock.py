"""Office clock, late/early leave, holidays, and geofence helpers."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.core.config import settings
from app.core.org_ctx import get_current_org_id
from app.db.models import Holiday, Organization, Person


def _zoneinfo(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def office_settings(session: Session | None = None) -> Organization:
    if session is not None:
        oid = get_current_org_id()
        if oid is not None:
            row = session.get(Organization, oid)
            if row is not None:
                return row
    return Organization(
        name="HQ",
        slug="hq",
        tz=settings.tz,
        work_start=settings.work_start,
        work_end=settings.work_end,
        late_grace_minutes=settings.late_grace_minutes,
        office_name="HQ",
    )


def zone(session: Session | None = None) -> ZoneInfo:
    return _zoneinfo(office_settings(session).tz or settings.tz)


def now_local(session: Session | None = None) -> datetime:
    return datetime.now(zone(session))


def today_local(session: Session | None = None) -> date:
    return now_local(session).date()


def as_local_date(dt: datetime, session: Session | None = None) -> date:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(zone(session)).date()


def parse_hhmm(value: str) -> time:
    parts = (value or "09:00").split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return time(hour=hour % 24, minute=minute % 60)


def _start_for(person: Person | None, cfg: Organization) -> str:
    if person is not None and person.shift_start:
        return person.shift_start
    return cfg.work_start


def _end_for(person: Person | None, cfg: Organization) -> str:
    if person is not None and person.shift_end:
        return person.shift_end
    return cfg.work_end


def is_late(
    when: datetime | None = None,
    session: Session | None = None,
    person: Person | None = None,
) -> bool:
    cfg = office_settings(session)
    tz = _zoneinfo(cfg.tz)
    instant = when or datetime.now(tz)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    local = instant.astimezone(tz)
    start = datetime.combine(local.date(), parse_hhmm(_start_for(person, cfg)), tzinfo=tz)
    threshold = start + timedelta(minutes=int(cfg.late_grace_minutes or 0))
    return local > threshold


def is_early_leave(
    when: datetime | None = None,
    session: Session | None = None,
    person: Person | None = None,
) -> bool:
    cfg = office_settings(session)
    tz = _zoneinfo(cfg.tz)
    instant = when or datetime.now(tz)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    local = instant.astimezone(tz)
    end = datetime.combine(local.date(), parse_hhmm(_end_for(person, cfg)), tzinfo=tz)
    return local < end


def is_weekend(day: date, session: Session | None = None) -> bool:
    cfg = office_settings(session)
    raw = cfg.weekend or "6,7"
    days = {int(p) for p in raw.split(",") if p.strip().isdigit()}
    return day.isoweekday() in days


def is_holiday(day: date, session: Session | None = None) -> bool:
    if session is None:
        return False
    stmt = select(Holiday).where(Holiday.day == day)
    oid = get_current_org_id()
    if oid is not None:
        stmt = stmt.where(Holiday.org_id == oid)
    row = session.exec(stmt).first()
    return row is not None


def expected_workday(day: date, session: Session | None = None) -> bool:
    return not is_weekend(day, session) and not is_holiday(day, session)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def geofence_active(session: Session | None = None) -> bool:
    cfg = office_settings(session)
    return cfg.geo_lat is not None and cfg.geo_lng is not None and float(cfg.geo_radius_m or 0) > 0


def assert_geofence(lat: float | None, lng: float | None, session: Session | None) -> None:
    from fastapi import HTTPException

    from app.core.geo import point_within_office

    if not geofence_active(session):
        return
    cfg = office_settings(session)
    if lat is None or lng is None:
        raise HTTPException(400, detail="location_required")
    if session is not None:
        if not point_within_office(session, float(lat), float(lng), cfg):
            raise HTTPException(403, detail="outside_geofence")
        return
    dist = haversine_m(float(cfg.geo_lat), float(cfg.geo_lng), float(lat), float(lng))
    if dist > float(cfg.geo_radius_m):
        raise HTTPException(403, detail="outside_geofence")
