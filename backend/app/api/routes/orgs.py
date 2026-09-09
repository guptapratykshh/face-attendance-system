"""Platform-admin organization CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from app.api.deps import require_platform_admin
from app.api.schemas import OrgCreate, OrgOut, OrgUpdate
from app.core.attendance_policy import KERNELS, apply_org_type
from app.db.models import Organization, Person, User, utcnow
from app.db.session import ensure_default_site, get_session
from app.db.tenancy import provision_org_schema, set_search_path, slugify, unique_slug

router = APIRouter(prefix="/orgs", tags=["orgs"])


def _out(session: Session, row: Organization) -> OrgOut:
    if row.id is not None:
        set_search_path(session, int(row.id))
    n = session.exec(select(func.count()).select_from(Person).where(Person.org_id == row.id)).one()
    set_search_path(session, None)
    return OrgOut(
        id=int(row.id),
        name=row.name,
        slug=row.slug,
        org_type=row.org_type,
        kernel=row.kernel,
        people_count=int(n or 0),
        office_name=row.office_name or row.name,
        tz=row.tz,
        work_start=row.work_start,
        work_end=row.work_end,
        subject_label=row.subject_label,
        subject_label_plural=row.subject_label_plural,
        created_at=row.created_at,
    )


@router.get("", response_model=list[OrgOut])
def list_orgs(
    _admin: User = Depends(require_platform_admin),
    session: Session = Depends(get_session),
) -> list[OrgOut]:
    rows = session.exec(select(Organization).order_by(Organization.name)).all()
    return [_out(session, row) for row in rows]


@router.post("", response_model=OrgOut, status_code=201)
def create_org(
    body: OrgCreate,
    _admin: User = Depends(require_platform_admin),
    session: Session = Depends(get_session),
) -> OrgOut:
    name = body.name.strip()
    requested = slugify(body.slug) if body.slug else unique_slug(session, name)
    if body.slug:
        taken = session.exec(select(Organization).where(Organization.slug == requested)).first()
        if taken is not None:
            raise HTTPException(409, detail="slug already in use")
    row = Organization(
        name=name,
        slug=requested,
        office_name=(body.office_name or body.name).strip(),
    )
    apply_org_type(row, body.org_type)
    if body.tz:
        row.tz = body.tz
    if body.work_start:
        row.work_start = body.work_start
    if body.work_end:
        row.work_end = body.work_end
    if body.late_grace_minutes is not None:
        row.late_grace_minutes = body.late_grace_minutes
    session.add(row)
    session.commit()
    session.refresh(row)
    provision_org_schema(session, int(row.id))
    session.commit()
    ensure_default_site(session, row)
    return _out(session, row)


@router.get("/{org_id}", response_model=OrgOut)
def get_org(
    org_id: int,
    _admin: User = Depends(require_platform_admin),
    session: Session = Depends(get_session),
) -> OrgOut:
    row = session.get(Organization, org_id)
    if row is None:
        raise HTTPException(404, detail="org_not_found")
    return _out(session, row)


@router.patch("/{org_id}", response_model=OrgOut)
def update_org(
    org_id: int,
    body: OrgUpdate,
    _admin: User = Depends(require_platform_admin),
    session: Session = Depends(get_session),
) -> OrgOut:
    row = session.get(Organization, org_id)
    if row is None:
        raise HTTPException(404, detail="org_not_found")
    fields = body.model_dump(exclude_unset=True)
    org_type = fields.pop("org_type", None)
    if org_type is not None:
        apply_org_type(row, org_type)
    kernel = fields.get("kernel")
    if kernel is not None and kernel not in KERNELS:
        raise HTTPException(400, detail="invalid_kernel")
    if "name" in fields and fields["name"]:
        fields["name"] = fields["name"].strip()
    if "slug" in fields and fields["slug"]:
        fields["slug"] = slugify(fields["slug"])
        taken = session.exec(
            select(Organization).where(Organization.slug == fields["slug"], Organization.id != org_id)
        ).first()
        if taken is not None:
            raise HTTPException(409, detail="slug already in use")
    for key, value in fields.items():
        setattr(row, key, value)
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _out(session, row)
