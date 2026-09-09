"""Spoof-alert evidence table.

Revision ID: 0004_spoof_alerts
Revises: 0003_kiosk_pin
Create Date: 2026-08-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_spoof_alerts"
down_revision: Union[str, None] = "0003_kiosk_pin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "spoofalert",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True, index=True),
        sa.Column("actor_username", sa.String(length=64), nullable=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id", ondelete="SET NULL"), nullable=True),
        sa.Column("person_name", sa.String(length=128), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="attendance"),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("similarity", sa.Float(), nullable=True),
        sa.Column("image", sa.LargeBinary(), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_spoofalert_person_id", "spoofalert", ["person_id"])
    op.create_index("ix_spoofalert_source", "spoofalert", ["source"])
    op.create_index("ix_spoofalert_created_at", "spoofalert", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_spoofalert_created_at", table_name="spoofalert")
    op.drop_index("ix_spoofalert_source", table_name="spoofalert")
    op.drop_index("ix_spoofalert_person_id", table_name="spoofalert")
    op.drop_table("spoofalert")
