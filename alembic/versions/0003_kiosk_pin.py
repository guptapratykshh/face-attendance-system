"""Kiosk PIN fallback flag.

Revision ID: 0003_kiosk_pin
Revises: 0002_ops
Create Date: 2026-08-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_kiosk_pin"
down_revision: Union[str, None] = "0002_ops"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "appsetting",
        sa.Column("allow_kiosk_pin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("appsetting", "allow_kiosk_pin")
