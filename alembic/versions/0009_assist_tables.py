"""Assist RAG chunk and chat message tables.

Revision ID: 0009_assist_tables
Revises: 0008_postgis_geo
Create Date: 2026-09-03
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_assist_tables"
down_revision: Union[str, None] = "0008_postgis_geo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistchunk",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organization.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_assistchunk_org_id", "assistchunk", ["org_id"])
    op.create_index("ix_assistchunk_source_type", "assistchunk", ["source_type"])
    op.create_index("ix_assistchunk_source_id", "assistchunk", ["source_id"])
    op.create_index("ix_assistchunk_created_at", "assistchunk", ["created_at"])

    op.create_table(
        "assistmessage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organization.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_assistmessage_org_id", "assistmessage", ["org_id"])
    op.create_index("ix_assistmessage_user_id", "assistmessage", ["user_id"])
    op.create_index("ix_assistmessage_created_at", "assistmessage", ["created_at"])


def downgrade() -> None:
    op.drop_table("assistmessage")
    op.drop_table("assistchunk")
