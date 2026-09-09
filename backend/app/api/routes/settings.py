"""Office hours, weekends, geofence, late-notify flags, and org attendance profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user, require_org, require_people
from app.api.schemas import OfficeSettingsOut, OfficeSettingsUpdate, OrgPresetOut
from app.core.attendance_policy import KERNELS, apply_org_type, preset_catalog, profile_dict
from app.core.clock import office_settings
from app.db.models import Organization, User, utcnow
from app.db.session import get_session

router = APIRouter(prefix="/settings", tags=["settings"])


def _out(row: Organization) -> OfficeSettingsOut:
    profile = profile_dict(row)
    return OfficeSettingsOut(
        tz=row.tz,
        work_start=row.work_start,
        work_end=row.work_end,
        late_grace_minutes=row.late_grace_minutes,
        office_name=getattr(row, "office_name", None) or "HQ",
        geo_lat=getattr(row, "geo_lat", None),
        geo_lng=getattr(row, "geo_lng", None),
        geo_radius_m=getattr(row, "geo_radius_m", None),
        weekend=getattr(row, "weekend", None) or "6,7",
        notify_late=bool(getattr(row, "notify_late", False)),
        allow_kiosk_pin=bool(getattr(row, "allow_kiosk_pin", False)),
        **profile,
    )


@router.get("/presets", response_model=list[OrgPresetOut])
def list_org_presets(_user: User = Depends(get_current_user)) -> list[OrgPresetOut]:
    return [OrgPresetOut(**item) for item in preset_catalog()]


@router.get("", response_model=OfficeSettingsOut)
def read_office_settings(
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> OfficeSettingsOut:
    return _out(office_settings(session))


@router.patch("", response_model=OfficeSettingsOut)
def update_office_settings(
    body: OfficeSettingsUpdate,
    _user: User = Depends(require_people),
    org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> OfficeSettingsOut:
    row = org
    fields = body.model_dump(exclude_unset=True)
    org_type = fields.pop("org_type", None)
    if org_type is not None:
        apply_org_type(row, org_type)
    kernel = fields.get("kernel")
    if kernel is not None and kernel not in KERNELS:
        raise HTTPException(400, detail="invalid_kernel")
    for key, value in fields.items():
        setattr(row, key, value)
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _out(row)
