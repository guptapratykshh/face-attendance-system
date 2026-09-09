"""Organization slugs, platform_user catalog, and schema-per-org on Postgres.

Revision ID: 0007_schema_per_org
Revises: 0006_organizations
Create Date: 2026-08-26
"""

from __future__ import annotations

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0007_schema_per_org"
down_revision: Union[str, None] = "0006_organizations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower())
    slug = slug.strip("-")[:64]
    return slug or "org"


def upgrade() -> None:
    op.add_column("organization", sa.Column("slug", sa.String(length=64), nullable=True))
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, name, office_name FROM organization")).fetchall()
    used: set[str] = set()
    for row in rows:
        base = _slugify(row.name or row.office_name or "org")
        slug = base
        n = 2
        while slug in used:
            slug = f"{base[:60]}-{n}"
            n += 1
        used.add(slug)
        bind.execute(sa.text("UPDATE organization SET slug = :slug WHERE id = :id"), {"slug": slug, "id": row.id})
    op.alter_column("organization", "slug", existing_type=sa.String(length=64), nullable=False)
    op.create_index("ix_organization_slug", "organization", ["slug"], unique=True)

    op.create_table(
        "platform_user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="admin"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_platform_user_username", "platform_user", ["username"])

    bind.execute(
        sa.text(
            """
            INSERT INTO platform_user (username, hashed_password, is_admin, role, created_at)
            SELECT username, hashed_password, is_admin, COALESCE(role, 'admin'), created_at
            FROM "user"
            WHERE is_admin IS true AND org_id IS NULL AND person_id IS NULL
            """
        )
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM "user"
            WHERE is_admin IS true AND org_id IS NULL AND person_id IS NULL
            """
        )
    )

    insp = inspect(bind)
    for uq in insp.get_unique_constraints("user"):
        if list(uq.get("column_names") or []) == ["username"]:
            op.drop_constraint(uq["name"], "user", type_="unique")
    op.create_unique_constraint("uq_user_org_username", "user", ["org_id", "username"])

    if bind.dialect.name == "postgresql":
        from sqlmodel import Session

        from app.db.tenancy import copy_public_tenant_rows

        session = Session(bind=bind)
        org_ids = [int(r[0]) for r in bind.execute(sa.text("SELECT id FROM organization")).fetchall()]
        for oid in org_ids:
            copy_public_tenant_rows(session, oid)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        rows = bind.execute(sa.text("SELECT id FROM organization")).fetchall()
        for row in rows:
            bind.execute(sa.text(f'DROP SCHEMA IF EXISTS "org_{int(row[0])}" CASCADE'))
    op.drop_constraint("uq_user_org_username", "user", type_="unique")
    op.create_unique_constraint("user_username_key", "user", ["username"])
    op.drop_index("ix_platform_user_username", table_name="platform_user")
    op.drop_table("platform_user")
    op.drop_index("ix_organization_slug", table_name="organization")
    op.drop_column("organization", "slug")
