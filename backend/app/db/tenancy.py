"""Schema-per-org isolation on Postgres; SQLite keeps shared tables + org_id filters.

Postgres commits during a request, so SET LOCAL would reset. We SET search_path on the
borrowed connection and restore public in get_session's finally block.
"""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import settings

TENANT_TABLE_NAMES: tuple[str, ...] = (
    "person",
    "user",
    "faceembedding",
    "site",
    "offering",
    "enrollment",
    "occurrence",
    "attendance",
    "accessevent",
    "holiday",
    "spoofalert",
    "captureprobe",
    "assistchunk",
    "assistmessage",
)


def schema_name(org_id: int) -> str:
    return f"org_{int(org_id)}"


def uses_postgres_schemas(session: Session | None = None) -> bool:
    if session is not None:
        return session.get_bind().dialect.name == "postgresql"
    return not settings.is_sqlite


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower())
    slug = slug.strip("-")[:64]
    return slug or "org"


def unique_slug(session: Session, name: str, *, exclude_id: int | None = None) -> str:
    from app.db.models import Organization

    base = slugify(name)
    candidate = base
    n = 2
    while True:
        stmt = select(Organization).where(Organization.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(Organization.id != exclude_id)
        if session.exec(stmt).first() is None:
            return candidate
        suffix = f"-{n}"
        candidate = f"{base[: 64 - len(suffix)]}{suffix}"
        n += 1


def set_search_path(session: Session, org_id: int | None) -> None:
    if not uses_postgres_schemas(session):
        return
    conn = session.connection()
    if org_id is None:
        conn.exec_driver_sql("SET search_path TO public")
    else:
        name = schema_name(org_id)
        conn.exec_driver_sql(f'SET search_path TO "{name}", public')
    session.expire_all()


def reset_search_path(session: Session) -> None:
    if not uses_postgres_schemas(session):
        return
    try:
        session.connection().exec_driver_sql("SET search_path TO public")
    except Exception:
        pass


def provision_org_schema(session: Session, org_id: int) -> None:
    """Create org_{id} and clone tenant table shapes from public (Postgres only)."""
    if not uses_postgres_schemas(session):
        return
    schema = schema_name(org_id)
    conn = session.connection()
    conn.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    for table in TENANT_TABLE_NAMES:
        exists = conn.execute(
            text("SELECT to_regclass(format('%I.%I', :schema, :table))"),
            {"schema": schema, "table": table},
        ).scalar()
        if exists:
            continue
        conn.exec_driver_sql(
            f'CREATE TABLE "{schema}"."{table}" (LIKE public."{table}" INCLUDING ALL)'
        )


def copy_public_tenant_rows(session: Session, org_id: int) -> None:
    """Copy public tenant rows into org_{id} (alembic backfill). Idempotent via PK."""
    if not uses_postgres_schemas(session):
        return
    provision_org_schema(session, org_id)
    schema = schema_name(org_id)
    conn = session.connection()
    for table in TENANT_TABLE_NAMES:
        if table == "faceembedding":
            conn.execute(
                text(
                    f"""
                    INSERT INTO "{schema}".faceembedding
                    SELECT f.* FROM public.faceembedding AS f
                    WHERE f.person_id IN (
                        SELECT id FROM public.person WHERE org_id = :oid
                    )
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"oid": org_id},
            )
            continue
        conn.execute(
            text(
                f"""
                INSERT INTO "{schema}"."{table}"
                SELECT * FROM public."{table}" WHERE org_id = :oid
                ON CONFLICT DO NOTHING
                """
            ),
            {"oid": org_id},
        )
    _reset_serials(conn, schema)


def _reset_serials(conn, schema: str) -> None:
    for table in TENANT_TABLE_NAMES:
        try:
            conn.execute(
                text(
                    f"""
                    SELECT setval(
                        pg_get_serial_sequence(format('%I.%I', :schema, :table), 'id'),
                        GREATEST(COALESCE((SELECT MAX(id) FROM "{schema}"."{table}"), 1), 1),
                        true
                    )
                    """
                ),
                {"schema": schema, "table": table},
            )
        except Exception:
            continue
