"""Auth: register, login, current user. Seeds an admin account on first boot."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, func, select

from app.api.deps import AuthUser, get_current_user
from app.api.routes._common import clean_optional, commit_or_conflict, ensure_unique_employee_id, ensure_unique_username
from app.api.schemas import (
    AuthConfigOut,
    LinkedPersonOut,
    LoginRequest,
    PasswordChange,
    RegisterRequest,
    SiteOut,
    Token,
    UserOut,
)
from app.core.attendance_policy import location_gate_active, profile_dict
from app.core.clock import office_settings
from app.core.config import settings
from app.core.org_ctx import get_current_org_id, set_current_org_id
from app.core.rate_limit import client_ip, login_limiter
from app.core.roles import ROLE_ADMIN, ROLE_EMPLOYEE, is_admin, is_platform_admin, normalized_role
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import FaceEmbedding, Organization, Person, PlatformUser, Site, User
from app.db.session import get_session
from app.db.tenancy import set_search_path

router = APIRouter(prefix="/auth", tags=["auth"])

DEFAULT_ADMIN = "admin"
DEFAULT_DEV_PASSWORD = "admin1234"


def seed_admin(session: Session) -> None:
    if session.exec(select(PlatformUser)).first() is not None:
        return
    leftover = session.exec(
        select(User).where(User.is_admin == True, User.org_id.is_(None), User.person_id.is_(None))  # noqa: E712
    ).first()
    if leftover is not None:
        session.add(
            PlatformUser(
                username=leftover.username,
                hashed_password=leftover.hashed_password,
                is_admin=True,
                role=ROLE_ADMIN,
            )
        )
        session.delete(leftover)
        session.commit()
        return
    password = settings.admin_password
    if not password:
        if settings.is_sqlite:
            password = DEFAULT_DEV_PASSWORD
        else:
            raise RuntimeError("FRS_ADMIN_PASSWORD is required when the database is empty")
    session.add(
        PlatformUser(
            username=settings.admin_username or DEFAULT_ADMIN,
            hashed_password=hash_password(password),
            is_admin=True,
            role=ROLE_ADMIN,
        )
    )
    session.commit()


def _org_identity(session: Session, org_id: int | None) -> tuple[str | None, str | None]:
    if org_id is None:
        return None, None
    org = session.get(Organization, int(org_id))
    if org is None:
        return None, None
    return org.name, org.slug


def _default_site_out(session: Session, org_id: int) -> SiteOut | None:
    row = session.exec(select(Site).where(Site.org_id == org_id, Site.is_default == True)).first()  # noqa: E712
    if row is None:
        row = session.exec(select(Site).where(Site.org_id == org_id).order_by(Site.id)).first()
    if row is None:
        return None
    return SiteOut(
        id=int(row.id),
        name=row.name,
        lat=row.lat,
        lng=row.lng,
        radius_m=row.radius_m,
        is_default=bool(row.is_default),
    )


def user_out(user: AuthUser, session: Session) -> UserOut:
    linked = None
    role = normalized_role(user)
    person_id = getattr(user, "person_id", None)
    if person_id is not None:
        person = session.get(Person, person_id)
        if person is not None:
            n_emb = session.exec(
                select(func.count()).select_from(FaceEmbedding).where(FaceEmbedding.person_id == person.id)
            ).one()
            n = int(n_emb or 0)
            linked = LinkedPersonOut(
                id=int(person.id),
                name=person.name,
                employee_id=person.employee_id,
                n_embeddings=n,
                face_ready=n > 0,
                is_active=bool(person.is_active),
            )
    oid = getattr(user, "org_id", None) or get_current_org_id()
    org_name, org_slug = _org_identity(session, int(oid) if oid is not None else None)
    return UserOut(
        id=int(user.id),
        username=user.username,
        is_admin=is_admin(user),
        role=role,
        org_id=getattr(user, "org_id", None),
        org_name=org_name,
        org_slug=org_slug,
        created_at=user.created_at,
        person=linked,
    )


def _org_by_slug(session: Session, slug: str) -> Organization | None:
    cleaned = slug.strip().lower()
    if not cleaned:
        return None
    return session.exec(select(Organization).where(Organization.slug == cleaned)).first()


@router.get("/config", response_model=AuthConfigOut)
def auth_config(session: Session = Depends(get_session)) -> AuthConfigOut:
    oid = get_current_org_id()
    if oid is None:
        return AuthConfigOut(
            allow_public_register=settings.allow_public_register,
            require_liveness=settings.require_liveness,
            tz=settings.tz,
            office_name="HQ",
            geofence=False,
            geo_radius_m=None,
            allow_kiosk_pin=False,
            **profile_dict(None),
        )
    set_search_path(session, int(oid))
    office = office_settings(session)
    profile = profile_dict(office)
    gated = location_gate_active(session)
    org_name, org_slug = _org_identity(session, int(oid))
    return AuthConfigOut(
        allow_public_register=settings.allow_public_register,
        require_liveness=settings.require_liveness,
        tz=office.tz,
        office_name=getattr(office, "office_name", None) or org_name or "HQ",
        geofence=gated,
        geo_radius_m=office.geo_radius_m if gated else None,
        allow_kiosk_pin=bool(getattr(office, "allow_kiosk_pin", False)),
        org_id=int(oid),
        org_name=org_name,
        org_slug=org_slug,
        default_site=_default_site_out(session, int(oid)),
        **profile,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, session: Session = Depends(get_session)) -> UserOut:
    if not settings.allow_public_register:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="public registration is disabled")
    oid = get_current_org_id()
    if body.org:
        org = _org_by_slug(session, body.org)
        if org is None or org.id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="org_not_found")
        oid = int(org.id)
    if oid is None:
        first = session.exec(select(Organization).order_by(Organization.id)).first()
        oid = int(first.id) if first is not None and first.id is not None else None
    if oid is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="org_required")
    set_current_org_id(oid)
    set_search_path(session, oid)
    ensure_unique_username(session, body.username, org_id=oid)
    try:
        hashed = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    employee_id = clean_optional(body.employee_id)
    ensure_unique_employee_id(session, employee_id)
    person = Person(
        name=body.name.strip(),
        employee_id=employee_id,
        email=clean_optional(body.email),
        org_id=oid,
    )
    session.add(person)
    commit_or_conflict(session)
    session.refresh(person)
    user = User(
        username=body.username,
        hashed_password=hashed,
        is_admin=False,
        role=ROLE_EMPLOYEE,
        person_id=person.id,
        org_id=oid,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user_out(user, session)


@router.post("/login", response_model=Token)
def login(body: LoginRequest, request: Request, session: Session = Depends(get_session)) -> Token:
    login_limiter.check(f"login:{body.username}:{client_ip(request)}")
    slug = (body.org or "").strip()
    if not slug:
        admin = session.exec(select(PlatformUser).where(PlatformUser.username == body.username)).first()
        if admin is None or not verify_password(body.password, admin.hashed_password):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="incorrect username or password")
        extra = {"uid": admin.id, "admin": True, "role": ROLE_ADMIN}
        token = create_access_token(admin.username, extra=extra)
        return Token(access_token=token, username=admin.username)

    org = _org_by_slug(session, slug)
    if org is None or org.id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="incorrect username or password")
    oid = int(org.id)
    set_search_path(session, oid)
    user = session.exec(select(User).where(User.username == body.username, User.org_id == oid)).first()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="incorrect username or password")
    extra = {"uid": user.id, "admin": is_admin(user), "role": normalized_role(user), "org": oid}
    token = create_access_token(user.username, extra=extra)
    return Token(access_token=token, username=user.username)


@router.get("/me", response_model=UserOut)
def me(user: AuthUser = Depends(get_current_user), session: Session = Depends(get_session)) -> UserOut:
    return user_out(user, session)


@router.post("/password", response_model=UserOut)
def change_password(
    body: PasswordChange,
    user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserOut:
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="current password is incorrect")
    try:
        hashed = hash_password(body.new_password)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if is_platform_admin(user):
        row = session.get(PlatformUser, user.id)
        if row is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="user not found")
        row.hashed_password = hashed
        session.add(row)
        session.commit()
        session.refresh(row)
        return user_out(row, session)
    user.hashed_password = hashed
    session.add(user)
    session.commit()
    session.refresh(user)
    return user_out(user, session)
