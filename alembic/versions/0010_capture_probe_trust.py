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


def _fk(target: str, schema: str | None) -> list[sa.ForeignKey]:
    """Foreign keys only in public.

    Org schemas are cloned with CREATE TABLE (LIKE ...), which does not carry constraints across,
    and their `user` table is a per-tenant copy rather than the public one.
    """
    return [] if schema else [sa.ForeignKey(target, ondelete="SET NULL")]


def _create_captureprobe(schema: str | None) -> None:
    op.create_table(
        "captureprobe",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), *_fk("organization.id", schema), nullable=True),
        sa.Column("user_id", sa.Integer(), *_fk("user.id", schema), nullable=True),
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
        schema=schema,
    )
    prefix = f"{schema}_" if schema else ""
    for col in ("org_id", "user_id", "challenge_id", "source", "label", "created_at"):
        op.create_index(f"ix_{prefix}captureprobe_{col}", "captureprobe", [col], schema=schema)


def _add_trust_columns(schema: str | None) -> None:
    op.add_column("attendance", sa.Column("trust_score", sa.Float(), nullable=True), schema=schema)
    op.add_column("attendance", sa.Column("trust_breakdown_json", sa.Text(), nullable=True), schema=schema)


def upgrade() -> None:
    bind = op.get_bind()
    _create_captureprobe(None)
    _add_trust_columns(None)
    for schema in _org_schemas(bind):
        _create_captureprobe(schema)
        _add_trust_columns(schema)


def downgrade() -> None:
    bind = op.get_bind()
    for schema in _org_schemas(bind):
        op.drop_column("attendance", "trust_breakdown_json", schema=schema)
        op.drop_column("attendance", "trust_score", schema=schema)
        op.drop_table("captureprobe", schema=schema)
    op.drop_column("attendance", "trust_breakdown_json")
    op.drop_column("attendance", "trust_score")
    op.drop_table("captureprobe")
