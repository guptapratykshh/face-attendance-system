"""Capture-path probe sessions and the fused presence-trust score on attendance.

Revision ID: 0010_capture_probe_trust
Revises: 0009_assist_tables
Create Date: 2026-09-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_capture_probe_trust"
down_revision: Union[str, None] = "0009_assist_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _org_schemas(bind) -> list[str]:
    """Schema-per-org deployments mirror tenant tables into org_* schemas."""
    if bind.dialect.name != "postgresql":
        return []
    rows = bind.execute(
        sa.text("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'org\\_%' ESCAPE '\\'")
    ).scalars()
    return [str(r) for r in rows]


def _create_captureprobe() -> None:
    """Public only, matching 0009.

    Org schemas pick the table up from provision_org_schema(), which clones tenant tables from
    public with CREATE TABLE (LIKE ...) on the next boot.
    """
    op.create_table(
        "captureprobe",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organization.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("challenge_id", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="attendance"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("live", sa.Boolean(), nullable=True),
        sa.Column("scored_by", sa.String(length=16), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("features_json", sa.Text(), nullable=True),
        sa.Column("report_json", sa.Text(), nullable=True),
        sa.Column("label", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for col in ("org_id", "user_id", "challenge_id", "source", "label", "created_at"):
        op.create_index(f"ix_captureprobe_{col}", "captureprobe", [col])


def _add_trust_columns(schema: str | None) -> None:
    """Every schema needs these.

    Unlike a missing table, provision_org_schema() will not add a missing *column* to an
    attendance table an org schema already has, so existing tenants must be altered here.
    """
    op.add_column("attendance", sa.Column("trust_score", sa.Float(), nullable=True), schema=schema)
    op.add_column("attendance", sa.Column("trust_breakdown_json", sa.Text(), nullable=True), schema=schema)


def upgrade() -> None:
    _create_captureprobe()
    _add_trust_columns(None)
    for schema in _org_schemas(op.get_bind()):
        _add_trust_columns(schema)


def downgrade() -> None:
    for schema in _org_schemas(op.get_bind()):
        op.drop_column("attendance", "trust_breakdown_json", schema=schema)
        op.drop_column("attendance", "trust_score", schema=schema)
    op.drop_column("attendance", "trust_breakdown_json")
    op.drop_column("attendance", "trust_score")
    op.drop_table("captureprobe")
