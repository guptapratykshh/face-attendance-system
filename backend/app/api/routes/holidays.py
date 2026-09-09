"""Company holidays so expected attendance skips those days."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from app.api.deps import require_admin, require_org, require_people
from app.api.schemas import HolidayIn, HolidayOut
from app.core.org_ctx import belongs_to_org, require_org_id, scoped
from app.db.models import Holiday, Organization, User
from app.db.session import get_session

router = APIRouter(prefix="/holidays", tags=["holidays"])


def _out(row: Holiday) -> HolidayOut:
    return HolidayOut(id=int(row.id), day=row.day.isoformat(), name=row.name)


@router.get("", response_model=list[HolidayOut])
def list_holidays(
    _user: User = Depends(require_people),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> list[HolidayOut]:
    rows = session.exec(scoped(select(Holiday).order_by(col(Holiday.day).desc()), Holiday)).all()
    return [_out(r) for r in rows]


@router.post("", response_model=HolidayOut, status_code=201)
def create_holiday(
    body: HolidayIn,
    _user: User = Depends(require_admin),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> HolidayOut:
    try:
        day = date.fromisoformat(body.day)
    except ValueError as exc:
        raise HTTPException(400, detail="invalid_date") from exc
    if session.exec(scoped(select(Holiday).where(Holiday.day == day), Holiday)).first() is not None:
        raise HTTPException(409, detail="holiday already exists")
    row = Holiday(day=day, name=body.name.strip(), org_id=require_org_id())
    session.add(row)
    session.commit()
    session.refresh(row)
    return _out(row)


@router.delete("/{holiday_id}", status_code=204)
def delete_holiday(
    holiday_id: int,
    _user: User = Depends(require_admin),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> None:
    row = belongs_to_org(session.get(Holiday, holiday_id), detail="holiday not found")
    session.delete(row)
    session.commit()
