"""Staff vs employee role checks."""

from __future__ import annotations

from app.db.models import PlatformUser, User

ROLE_ADMIN = "admin"
ROLE_HR = "hr"
ROLE_OPERATOR = "operator"
ROLE_EMPLOYEE = "employee"
STAFF_ROLES = frozenset({ROLE_ADMIN, ROLE_HR, ROLE_OPERATOR})
PEOPLE_ROLES = frozenset({ROLE_ADMIN, ROLE_HR})
LAB_ROLES = frozenset({ROLE_ADMIN, ROLE_OPERATOR})


def normalized_role(user: User) -> str:
    if user.is_admin:
        return ROLE_ADMIN
    role = (user.role or ROLE_EMPLOYEE).strip().lower()
    if role in STAFF_ROLES or role == ROLE_EMPLOYEE:
        return role
    return ROLE_EMPLOYEE


def is_admin(user: User) -> bool:
    return normalized_role(user) == ROLE_ADMIN


def is_platform_admin(user: User) -> bool:
    if isinstance(user, PlatformUser):
        return True
    return is_admin(user) and getattr(user, "org_id", None) is None


def is_staff(user: User) -> bool:
    return normalized_role(user) in STAFF_ROLES


def can_manage_people(user: User) -> bool:
    return normalized_role(user) in PEOPLE_ROLES


def can_use_lab(user: User) -> bool:
    return normalized_role(user) in LAB_ROLES
