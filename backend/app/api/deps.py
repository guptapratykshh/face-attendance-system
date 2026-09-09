"""FastAPI dependencies: DB session, current user, runtime handles."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from sqlmodel import Session, select

from app.core.org_ctx import get_current_org_id, set_current_org_id
from app.core.roles import can_manage_people, can_use_lab, is_admin, is_platform_admin, is_staff
from app.core.security import decode_access_token
from app.db.models import Organization, PlatformUser, User
from app.db.session import get_session
from app.db.tenancy import set_search_path
from app.runtime import runtime

bearer = HTTPBearer(auto_error=False)

AuthUser = User | PlatformUser


def bind_org_context(user: AuthUser) -> None:
    """Prefer the user's org; platform admin may already have X-Org-Id from middleware."""
    oid = getattr(user, "org_id", None)
    if oid is not None:
        set_current_org_id(int(oid))


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_session),
) -> AuthUser:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    try:
        payload = decode_access_token(creds.credentials)
        username = payload.get("sub")
    except PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token") from exc
    if not username:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    uid = payload.get("uid")
    org_claim = payload.get("org")
    if org_claim is not None:
        try:
            oid = int(org_claim)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc
        set_current_org_id(oid)
        set_search_path(session, oid)
        user = session.get(User, int(uid)) if uid is not None else None
        if user is None:
            user = session.exec(select(User).where(User.username == username, User.org_id == oid)).first()
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="user not found")
        bind_org_context(user)
        return user

    set_search_path(session, None)
    admin = session.get(PlatformUser, int(uid)) if uid is not None else None
    if admin is None:
        admin = session.exec(select(PlatformUser).where(PlatformUser.username == username)).first()
    if admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return admin


def require_org(
    user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Organization:
    oid = get_current_org_id()
    user_org = getattr(user, "org_id", None)
    if user_org is not None:
        oid = int(user_org)
        set_current_org_id(oid)
    elif not is_platform_admin(user) or oid is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="org_required")
    org = session.get(Organization, int(oid))
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="org_not_found")
    set_search_path(session, int(oid))
    return org


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="admin only")
    return user


def require_platform_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not is_platform_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="platform_admin_only")
    return user


def require_people(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not can_manage_people(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="people admin only")
    return user


def require_lab(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not can_use_lab(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="lab only")
    return user


def require_staff(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not is_staff(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="staff only")
    return user


def get_runtime():
    if runtime.pipeline is None or runtime.gallery is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="pipeline not ready")
    return runtime
