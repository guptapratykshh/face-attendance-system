"""Initial attendance-platform schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-25
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "person",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("employee_id", sa.String(length=64), nullable=True),
        sa.Column("email", sa.String(length=256), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_person_name", "person", ["name"])
    op.create_index("ix_person_is_active", "person", ["is_active"])
    op.create_unique_constraint("uq_person_employee_id", "person", ["employee_id"])

    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="employee"),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("person_id"),
    )
    op.create_index("ix_user_username", "user", ["username"])
    op.create_index("ix_user_role", "user", ["role"])
    op.create_index("ix_user_person_id", "user", ["person_id"])

    op.create_table(
        "faceembedding",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("encoder", sa.String(length=64), nullable=False),
        sa.Column("dim", sa.Integer(), nullable=False),
        sa.Column("vector", sa.LargeBinary(), nullable=False),
        sa.Column("quality_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_faceembedding_person_id", "faceembedding", ["person_id"])
    op.create_index("ix_faceembedding_encoder", "faceembedding", ["encoder"])

    op.create_table(
        "accessevent",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.Column("person_name", sa.String(), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("similarity", sa.Float(), nullable=True),
        sa.Column("encoder", sa.String(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_accessevent_kind", "accessevent", ["kind"])
    op.create_index("ix_accessevent_person_id", "accessevent", ["person_id"])
    op.create_index("ix_accessevent_created_at", "accessevent", ["created_at"])

    op.create_table(
        "attendance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("similarity", sa.Float(), nullable=True),
        sa.Column("encoder", sa.String(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="web"),
        sa.Column("late", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("checked_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_attendance_person_id", "attendance", ["person_id"])
    op.create_index("ix_attendance_user_id", "attendance", ["user_id"])
    op.create_index("ix_attendance_created_at", "attendance", ["created_at"])
    op.create_index("ix_attendance_person_created", "attendance", ["person_id", "created_at"])

    op.create_table(
        "appsetting",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tz", sa.String(length=64), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("work_start", sa.String(length=8), nullable=False, server_default="09:00"),
        sa.Column("work_end", sa.String(length=8), nullable=False, server_default="18:00"),
        sa.Column("late_grace_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("appsetting")
    op.drop_table("attendance")
    op.drop_table("accessevent")
    op.drop_table("faceembedding")
    op.drop_table("user")
    op.drop_table("person")
