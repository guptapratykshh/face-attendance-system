"""Organization attendance profile, sessions, shifts, and sites.

Revision ID: 0005_attendance_modes
Revises: 0004_spoof_alerts
Create Date: 2026-08-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_attendance_modes"
down_revision: Union[str, None] = "0004_spoof_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "site",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("radius_m", sa.Float(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "offering",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False, index=True),
        sa.Column("code", sa.String(length=32), nullable=True, index=True),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="course"),
        sa.Column("default_start", sa.String(length=8), nullable=True),
        sa.Column("default_end", sa.String(length=8), nullable=True),
        sa.Column("room", sa.String(length=64), nullable=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("site.id", ondelete="SET NULL"), nullable=True),
        sa.Column("min_percent", sa.Integer(), nullable=False, server_default="75"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "enrollment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id", ondelete="CASCADE"), nullable=False),
        sa.Column("offering_id", sa.Integer(), sa.ForeignKey("offering.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("person_id", "offering_id", name="uq_enrollment_person_offering"),
    )
    op.create_index("ix_enrollment_person_id", "enrollment", ["person_id"])
    op.create_index("ix_enrollment_offering_id", "enrollment", ["offering_id"])
    op.create_table(
        "occurrence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("offering_id", sa.Integer(), sa.ForeignKey("offering.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="session"),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("start", sa.String(length=8), nullable=False, server_default="09:00"),
        sa.Column("end", sa.String(length=8), nullable=False, server_default="10:00"),
        sa.Column("overnight", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("room", sa.String(length=64), nullable=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("site.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_occurrence_day", "occurrence", ["day"])
    op.create_index("ix_occurrence_kind", "occurrence", ["kind"])
    op.create_index("ix_occurrence_day_kind", "occurrence", ["day", "kind"])

    op.add_column("attendance", sa.Column("occurrence_id", sa.Integer(), nullable=True))
    op.add_column("attendance", sa.Column("site_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_attendance_occurrence", "attendance", "occurrence", ["occurrence_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_attendance_site", "attendance", "site", ["site_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_attendance_occurrence", "attendance", ["occurrence_id"])

    for name, col in [
        ("org_type", sa.Column("org_type", sa.String(length=32), nullable=False, server_default="workplace")),
        ("kernel", sa.Column("kernel", sa.String(length=32), nullable=False, server_default="daily_inout")),
        ("subject_label", sa.Column("subject_label", sa.String(length=32), nullable=False, server_default="employee")),
        ("subject_label_plural", sa.Column("subject_label_plural", sa.String(length=32), nullable=False, server_default="employees")),
        ("staff_label", sa.Column("staff_label", sa.String(length=32), nullable=False, server_default="HR")),
        ("group_label", sa.Column("group_label", sa.String(length=32), nullable=False, server_default="department")),
        ("id_label", sa.Column("id_label", sa.String(length=64), nullable=False, server_default="Employee ID")),
        ("require_checkout", sa.Column("require_checkout", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("allow_checkout", sa.Column("allow_checkout", sa.Boolean(), nullable=False, server_default=sa.true())),
        ("track_late", sa.Column("track_late", sa.Boolean(), nullable=False, server_default=sa.true())),
        ("track_early_leave", sa.Column("track_early_leave", sa.Boolean(), nullable=False, server_default=sa.true())),
        ("geofence_on_self_punch", sa.Column("geofence_on_self_punch", sa.Boolean(), nullable=False, server_default=sa.true())),
        ("auto_absent_at_close", sa.Column("auto_absent_at_close", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("allow_multiple_present_per_day", sa.Column("allow_multiple_present_per_day", sa.Boolean(), nullable=False, server_default=sa.false())),
    ]:
        op.add_column("appsetting", col)


def downgrade() -> None:
    for name in [
        "allow_multiple_present_per_day",
        "auto_absent_at_close",
        "geofence_on_self_punch",
        "track_early_leave",
        "track_late",
        "allow_checkout",
        "require_checkout",
        "id_label",
        "group_label",
        "staff_label",
        "subject_label_plural",
        "subject_label",
        "kernel",
        "org_type",
    ]:
        op.drop_column("appsetting", name)
    op.drop_index("ix_attendance_occurrence", table_name="attendance")
    op.drop_constraint("fk_attendance_site", "attendance", type_="foreignkey")
    op.drop_constraint("fk_attendance_occurrence", "attendance", type_="foreignkey")
    op.drop_column("attendance", "site_id")
    op.drop_column("attendance", "occurrence_id")
    op.drop_index("ix_occurrence_day_kind", table_name="occurrence")
    op.drop_index("ix_occurrence_kind", table_name="occurrence")
    op.drop_index("ix_occurrence_day", table_name="occurrence")
    op.drop_table("occurrence")
    op.drop_index("ix_enrollment_offering_id", table_name="enrollment")
    op.drop_index("ix_enrollment_person_id", table_name="enrollment")
    op.drop_table("enrollment")
    op.drop_table("offering")
    op.drop_table("site")
