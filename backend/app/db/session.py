"""Database engine, migrations, and session helpers."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import PROJECT_ROOT, settings
from app.db import models as _models  # noqa: F401  — register tables
from app.db.models import (
    AccessEvent,
    AppSetting,
    Attendance,
    Enrollment,
    Holiday,
    Occurrence,
    Offering,
    Organization,
    Person,
    Site,
    SpoofAlert,
    User,
)
from app.db.tenancy import provision_org_schema, reset_search_path, set_search_path, unique_slug

engine = None
SessionLocal = None


def configure_engine(url: str | None = None) -> None:
    """(Re)bind the global engine. Tests call this with a temporary SQLite URL."""
    global engine, SessionLocal
    raw = url or settings.database_url
    parsed = make_url(raw)
    kwargs: dict = {"echo": False, "pool_pre_ping": parsed.drivername != "sqlite"}
    if parsed.drivername.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs.pop("pool_pre_ping", None)
    engine = create_engine(raw, **kwargs)
    SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


configure_engine()


def _sqlite_add_column(table: str, name: str, ddl: str) -> None:
    if engine is None:
        return
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(f'PRAGMA table_info("{table}")').fetchall()
        if not rows:
            return
        cols = {r[1] for r in rows}
        if name not in cols:
            conn.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}')
            conn.commit()


def _ensure_sqlite_columns() -> None:
    """Add columns that create_all will not attach to an existing SQLite file."""
    _sqlite_add_column("user", "person_id", "INTEGER REFERENCES person(id)")
    _sqlite_add_column("user", "role", "VARCHAR(32) DEFAULT 'employee'")
    _sqlite_add_column("person", "email", "VARCHAR(256)")
    _sqlite_add_column("person", "is_active", "BOOLEAN DEFAULT 1")
    _sqlite_add_column("person", "deactivated_at", "DATETIME")
    _sqlite_add_column("attendance", "source", "VARCHAR(32) DEFAULT 'web'")
    _sqlite_add_column("attendance", "late", "BOOLEAN DEFAULT 0")
    _sqlite_add_column("attendance", "checked_out_at", "DATETIME")
    _sqlite_add_column("person", "department", "VARCHAR(64)")
    _sqlite_add_column("person", "office", "VARCHAR(64)")
    _sqlite_add_column("person", "shift_start", "VARCHAR(8)")
    _sqlite_add_column("person", "shift_end", "VARCHAR(8)")
    _sqlite_add_column("attendance", "early_leave", "BOOLEAN DEFAULT 0")
    _sqlite_add_column("attendance", "latitude", "FLOAT")
    _sqlite_add_column("attendance", "longitude", "FLOAT")
    _sqlite_add_column("appsetting", "office_name", "VARCHAR(64) DEFAULT 'HQ'")
    _sqlite_add_column("appsetting", "geo_lat", "FLOAT")
    _sqlite_add_column("appsetting", "geo_lng", "FLOAT")
    _sqlite_add_column("appsetting", "geo_radius_m", "FLOAT")
    _sqlite_add_column("appsetting", "weekend", "VARCHAR(16) DEFAULT '6,7'")
    _sqlite_add_column("appsetting", "notify_late", "BOOLEAN DEFAULT 0")
    _sqlite_add_column("appsetting", "allow_kiosk_pin", "BOOLEAN DEFAULT 0")
    _sqlite_add_column("appsetting", "org_type", "VARCHAR(32) DEFAULT 'workplace'")
    _sqlite_add_column("appsetting", "kernel", "VARCHAR(32) DEFAULT 'daily_inout'")
    _sqlite_add_column("appsetting", "subject_label", "VARCHAR(32) DEFAULT 'employee'")
    _sqlite_add_column("appsetting", "subject_label_plural", "VARCHAR(32) DEFAULT 'employees'")
    _sqlite_add_column("appsetting", "staff_label", "VARCHAR(32) DEFAULT 'HR'")
    _sqlite_add_column("appsetting", "group_label", "VARCHAR(32) DEFAULT 'department'")
    _sqlite_add_column("appsetting", "id_label", "VARCHAR(64) DEFAULT 'Employee ID'")
    _sqlite_add_column("appsetting", "require_checkout", "BOOLEAN DEFAULT 0")
    _sqlite_add_column("appsetting", "allow_checkout", "BOOLEAN DEFAULT 1")
    _sqlite_add_column("appsetting", "track_late", "BOOLEAN DEFAULT 1")
    _sqlite_add_column("appsetting", "track_early_leave", "BOOLEAN DEFAULT 1")
    _sqlite_add_column("appsetting", "geofence_on_self_punch", "BOOLEAN DEFAULT 1")
    _sqlite_add_column("appsetting", "auto_absent_at_close", "BOOLEAN DEFAULT 0")
    _sqlite_add_column("appsetting", "allow_multiple_present_per_day", "BOOLEAN DEFAULT 0")
    _sqlite_add_column("attendance", "occurrence_id", "INTEGER REFERENCES occurrence(id)")
    _sqlite_add_column("attendance", "site_id", "INTEGER REFERENCES site(id)")
    _sqlite_add_column("user", "org_id", "INTEGER REFERENCES organization(id)")
    _sqlite_add_column("person", "org_id", "INTEGER REFERENCES organization(id)")
    _sqlite_add_column("attendance", "org_id", "INTEGER REFERENCES organization(id)")
    _sqlite_add_column("accessevent", "org_id", "INTEGER REFERENCES organization(id)")
    _sqlite_add_column("site", "org_id", "INTEGER REFERENCES organization(id)")
    _sqlite_add_column("offering", "org_id", "INTEGER REFERENCES organization(id)")
    _sqlite_add_column("enrollment", "org_id", "INTEGER REFERENCES organization(id)")
    _sqlite_add_column("occurrence", "org_id", "INTEGER REFERENCES organization(id)")
    _sqlite_add_column("holiday", "org_id", "INTEGER REFERENCES organization(id)")
    _sqlite_add_column("spoofalert", "org_id", "INTEGER REFERENCES organization(id)")
    _sqlite_add_column("organization", "slug", "VARCHAR(64)")
    _sqlite_add_column("attendance", "trust_score", "FLOAT")
    _sqlite_add_column("attendance", "trust_breakdown_json", "TEXT")
    _sqlite_username_per_org()


def _sqlite_username_per_org() -> None:
    """Drop global username unique and enforce (org_id, username) on existing SQLite files."""
    if engine is None:
        return
    with engine.connect() as conn:
        try:
            indexes = conn.exec_driver_sql('PRAGMA index_list("user")').fetchall()
        except Exception:
            return
        for idx in indexes:
            name = idx[1]
            unique = idx[2]
            if not unique:
                continue
            cols = conn.exec_driver_sql(f'PRAGMA index_info("{name}")').fetchall()
            col_names = [c[2] for c in cols]
            if col_names == ["username"]:
                conn.exec_driver_sql(f'DROP INDEX IF EXISTS "{name}"')
        conn.exec_driver_sql(
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_user_org_username ON "user"(org_id, username)'
        )
        conn.commit()


def _run_alembic() -> None:
    from alembic.config import Config

    from alembic import command

    ini = PROJECT_ROOT / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("sqlalchemy.url", str(engine.url) if engine is not None else settings.database_url)
    command.upgrade(cfg, "head")


_ORG_COPY_FIELDS = (
    "tz",
    "work_start",
    "work_end",
    "late_grace_minutes",
    "office_name",
    "geo_lat",
    "geo_lng",
    "geo_radius_m",
    "weekend",
    "notify_late",
    "allow_kiosk_pin",
    "org_type",
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


def seed_office_settings(session: Session) -> None:
    row = session.get(AppSetting, 1)
    if row is not None:
        return
    session.add(
        AppSetting(
            id=1,
            tz=settings.tz,
            work_start=settings.work_start,
            work_end=settings.work_end,
            late_grace_minutes=settings.late_grace_minutes,
        )
    )
    session.commit()


def _backfill_org_id(session: Session, org_id: int) -> None:
    for model in (
        Person,
        Attendance,
        Site,
        Offering,
        Enrollment,
        Occurrence,
        Holiday,
        SpoofAlert,
        AccessEvent,
    ):
        rows = session.exec(select(model).where(model.org_id.is_(None))).all()
        for row in rows:
            row.org_id = org_id
            session.add(row)
    for user in session.exec(select(User).where(User.org_id.is_(None))).all():
        if user.is_admin and user.person_id is None:
            continue
        user.org_id = org_id
        session.add(user)
    session.commit()


def ensure_default_site(session: Session, org: Organization) -> Site | None:
    """Create a default workplace Site for an org if none exists."""
    if org.id is None:
        return None
    set_search_path(session, int(org.id))
    existing = session.exec(select(Site).where(Site.org_id == org.id)).all()
    defaults = [row for row in existing if row.is_default]
    if defaults:
        return defaults[0]
    if existing:
        existing[0].is_default = True
        session.add(existing[0])
        session.commit()
        session.refresh(existing[0])
        return existing[0]
    row = Site(
        org_id=int(org.id),
        name=(org.office_name or org.name or "Workplace").strip() or "Workplace",
        lat=org.geo_lat,
        lng=org.geo_lng,
        radius_m=org.geo_radius_m,
        is_default=True,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def seed_default_org(session: Session) -> Organization:
    existing = session.exec(select(Organization).order_by(Organization.id)).first()
    if existing is not None:
        if existing.id is not None:
            _backfill_org_id(session, int(existing.id))
        _ensure_org_slugs(session)
        for org in session.exec(select(Organization)).all():
            if org.id is not None:
                provision_org_schema(session, int(org.id))
                ensure_default_site(session, org)
        session.commit()
        return existing
    office = session.get(AppSetting, 1)
    kwargs: dict = {
        "name": getattr(office, "office_name", None) or "HQ",
        "tz": settings.tz,
        "work_start": settings.work_start,
        "work_end": settings.work_end,
        "late_grace_minutes": settings.late_grace_minutes,
        "office_name": "HQ",
    }
    if office is not None:
        for key in _ORG_COPY_FIELDS:
            if hasattr(office, key):
                kwargs[key] = getattr(office, key)
        kwargs["name"] = office.office_name or "HQ"
    kwargs["slug"] = unique_slug(session, kwargs.get("name") or "org")
    org = Organization(**kwargs)
    session.add(org)
    session.commit()
    session.refresh(org)
    _backfill_org_id(session, int(org.id))
    provision_org_schema(session, int(org.id))
    ensure_default_site(session, org)
    session.commit()
    return org


def _ensure_org_slugs(session: Session) -> None:
    rows = session.exec(select(Organization)).all()
    for org in rows:
        if org.slug:
            continue
        org.slug = unique_slug(session, org.name or org.office_name or "org", exclude_id=org.id)
        session.add(org)
    session.commit()


def init_db() -> None:
    url = str(engine.url) if engine is not None else settings.database_url
    if url.startswith("sqlite"):
        SQLModel.metadata.create_all(engine)
        _ensure_sqlite_columns()
    else:
        _run_alembic()
    with SessionLocal() as session:
        seed_office_settings(session)
        seed_default_org(session)
    if url.startswith("sqlite"):
        _sqlite_unique_org_slug()


def _sqlite_unique_org_slug() -> None:
    if engine is None:
        return
    with engine.connect() as conn:
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ix_organization_slug ON organization(slug)")
        conn.commit()


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        try:
            yield session
        finally:
            reset_search_path(session)
