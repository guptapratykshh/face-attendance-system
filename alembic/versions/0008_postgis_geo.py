"""PostGIS geography columns for sites and attendance punches.

Revision ID: 0008_postgis_geo
Revises: 0007_schema_per_org
Create Date: 2026-09-03
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_postgis_geo"
down_revision: Union[str, None] = "0007_schema_per_org"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
    op.execute(sa.text("ALTER TABLE site ADD COLUMN IF NOT EXISTS geom geography(Point, 4326)"))
    op.execute(
        sa.text(
            """
            UPDATE site
            SET geom = ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography
            WHERE lat IS NOT NULL AND lng IS NOT NULL AND geom IS NULL
            """
        )
    )
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_site_geom ON site USING GIST (geom)"))
    op.execute(
        sa.text("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS punch_geom geography(Point, 4326)")
    )
    op.execute(
        sa.text(
            """
            UPDATE attendance
            SET punch_geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND punch_geom IS NULL
            """
        )
    )
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_attendance_punch_geom ON attendance USING GIST (punch_geom)"))

    # Mirror columns into existing org_* schemas
    schemas = bind.execute(
        sa.text(
            """
            SELECT nspname FROM pg_namespace
            WHERE nspname LIKE 'org_%' AND nspname ~ '^org_[0-9]+$'
            """
        )
    ).fetchall()
    for (schema,) in schemas:
        op.execute(
            sa.text(
                f'ALTER TABLE "{schema}".site ADD COLUMN IF NOT EXISTS geom geography(Point, 4326)'
            )
        )
        op.execute(
            sa.text(
                f"""
                UPDATE "{schema}".site
                SET geom = ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography
                WHERE lat IS NOT NULL AND lng IS NOT NULL AND geom IS NULL
                """
            )
        )
        op.execute(sa.text(f'CREATE INDEX IF NOT EXISTS ix_site_geom ON "{schema}".site USING GIST (geom)'))
        op.execute(
            sa.text(
                f'ALTER TABLE "{schema}".attendance ADD COLUMN IF NOT EXISTS punch_geom geography(Point, 4326)'
            )
        )
        op.execute(
            sa.text(
                f"""
                UPDATE "{schema}".attendance
                SET punch_geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND punch_geom IS NULL
                """
            )
        )
        op.execute(
            sa.text(
                f'CREATE INDEX IF NOT EXISTS ix_attendance_punch_geom ON "{schema}".attendance USING GIST (punch_geom)'
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    schemas = ["public"] + [
        row[0]
        for row in bind.execute(
            sa.text(
                """
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'org_%' AND nspname ~ '^org_[0-9]+$'
                """
            )
        ).fetchall()
    ]
    for schema in schemas:
        op.execute(sa.text(f'DROP INDEX IF EXISTS "{schema}".ix_attendance_punch_geom'))
        op.execute(sa.text(f'DROP INDEX IF EXISTS "{schema}".ix_site_geom'))
        op.execute(sa.text(f'ALTER TABLE "{schema}".attendance DROP COLUMN IF EXISTS punch_geom'))
        op.execute(sa.text(f'ALTER TABLE "{schema}".site DROP COLUMN IF EXISTS geom'))
