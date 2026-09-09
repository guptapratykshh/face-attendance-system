"""Admin staff accounts: create HR / operator / admin users."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from app.api.deps import require_admin, require_org
from app.api.schemas import StaffCreate, StaffOut, StaffUpdate
from app.core.org_ctx import get_current_org_id
from app.core.roles import ROLE_ADMIN, STAFF_ROLES, is_admin, is_platform_admin, normalized_role
from app.core.security import hash_password
from app.db.models import Organization, User
from app.db.session import get_session

router = APIRouter(prefix="/users", tags=["users"])

ALLOWED = STAFF_ROLES | {"employee"}


def _out(user: User) -> StaffOut:
    return StaffOut(
        id=int(user.id),
        username=user.username,
        role=normalized_role(user),
        is_admin=is_admin(user),
        person_id=user.person_id,
        created_at=user.created_at,
    )


@router.get("", response_model=list[StaffOut])
def list_users(
    _admin: User = Depends(require_admin),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> list[StaffOut]:
    oid = get_current_org_id()
    stmt = select(User).order_by(col(User.created_at).desc())
    if oid is not None:
        stmt = stmt.where(User.org_id == oid)
    rows = session.exec(stmt).all()
    return [_out(u) for u in rows]


@router.post("", response_model=StaffOut, status_code=201)
def create_user(
    body: StaffCreate,
    _admin: User = Depends(require_admin),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> StaffOut:
    role = body.role.strip().lower()
    if role not in ALLOWED:
        raise HTTPException(400, detail="invalid_role")
    if session.exec(
        select(User).where(User.username == body.username.strip(), User.org_id == get_current_org_id())
    ).first():
        raise HTTPException(409, detail="username already in use")
    user = User(
        username=body.username.strip(),
        hashed_password=hash_password(body.password),
        role=role,
        is_admin=role == ROLE_ADMIN,
        org_id=get_current_org_id(),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _out(user)


@router.patch("/{user_id}", response_model=StaffOut)
def update_user(
    user_id: int,
    body: StaffUpdate,
    admin: User = Depends(require_admin),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> StaffOut:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(404, detail="user not found")
    oid = get_current_org_id()
    if oid is not None and user.org_id is not None and int(user.org_id) != int(oid):
        raise HTTPException(404, detail="user not found")
    if not is_platform_admin(admin) and int(user.id) == int(admin.id) and body.role and body.role.strip().lower() != ROLE_ADMIN:
        raise HTTPException(400, detail="cannot_demote_self")
    if body.role:
        role = body.role.strip().lower()
        if role not in ALLOWED:
            raise HTTPException(400, detail="invalid_role")
        user.role = role
        user.is_admin = role == ROLE_ADMIN
    if body.password:
        user.hashed_password = hash_password(body.password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return _out(user)
