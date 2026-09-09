"""Person shifts, holidays, geofence, and early leave.

Revision ID: 0002_ops
Revises: 0001_initial
Create Date: 2026-08-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_ops"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("person", sa.Column("department", sa.String(length=64), nullable=True))
    op.add_column("person", sa.Column("office", sa.String(length=64), nullable=True))
    op.add_column("person", sa.Column("shift_start", sa.String(length=8), nullable=True))
    op.add_column("person", sa.Column("shift_end", sa.String(length=8), nullable=True))

    op.add_column("attendance", sa.Column("early_leave", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("attendance", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("attendance", sa.Column("longitude", sa.Float(), nullable=True))

    op.add_column("appsetting", sa.Column("office_name", sa.String(length=64), nullable=False, server_default="HQ"))
    op.add_column("appsetting", sa.Column("geo_lat", sa.Float(), nullable=True))
    op.add_column("appsetting", sa.Column("geo_lng", sa.Float(), nullable=True))
    op.add_column("appsetting", sa.Column("geo_radius_m", sa.Float(), nullable=True))
    op.add_column("appsetting", sa.Column("weekend", sa.String(length=16), nullable=False, server_default="6,7"))
    op.add_column("appsetting", sa.Column("notify_late", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        "holiday",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_holiday_day", "holiday", ["day"])


def downgrade() -> None:
    op.drop_index("ix_holiday_day", table_name="holiday")
    op.drop_table("holiday")
    op.drop_column("appsetting", "notify_late")
    op.drop_column("appsetting", "weekend")
    op.drop_column("appsetting", "geo_radius_m")
    op.drop_column("appsetting", "geo_lng")
    op.drop_column("appsetting", "geo_lat")
    op.drop_column("appsetting", "office_name")
    op.drop_column("attendance", "longitude")
    op.drop_column("attendance", "latitude")
    op.drop_column("attendance", "early_leave")
    op.drop_column("person", "shift_end")
    op.drop_column("person", "shift_start")
    op.drop_column("person", "office")
    op.drop_column("person", "department")
