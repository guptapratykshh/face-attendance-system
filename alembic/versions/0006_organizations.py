"""Multi-organization tables and org_id on existing rows.

Revision ID: 0006_organizations
Revises: 0005_attendance_modes
Create Date: 2026-08-26
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_organizations"
down_revision: Union[str, None] = "0005_attendance_modes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_TABLES = (
    "person",
    "user",
    "attendance",
    "accessevent",
    "site",
    "offering",
    "enrollment",
    "occurrence",
    "holiday",
    "spoofalert",
)


def upgrade() -> None:
    op.create_table(
        "organization",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False, index=True),
        sa.Column("tz", sa.String(length=64), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("work_start", sa.String(length=8), nullable=False, server_default="09:00"),
        sa.Column("work_end", sa.String(length=8), nullable=False, server_default="18:00"),
        sa.Column("late_grace_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("office_name", sa.String(length=64), nullable=False, server_default="HQ"),
        sa.Column("geo_lat", sa.Float(), nullable=True),
        sa.Column("geo_lng", sa.Float(), nullable=True),
        sa.Column("geo_radius_m", sa.Float(), nullable=True),
        sa.Column("weekend", sa.String(length=16), nullable=False, server_default="6,7"),
        sa.Column("notify_late", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_kiosk_pin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("org_type", sa.String(length=32), nullable=False, server_default="workplace"),
        sa.Column("kernel", sa.String(length=32), nullable=False, server_default="daily_inout"),
        sa.Column("subject_label", sa.String(length=32), nullable=False, server_default="employee"),
        sa.Column("subject_label_plural", sa.String(length=32), nullable=False, server_default="employees"),
        sa.Column("staff_label", sa.String(length=32), nullable=False, server_default="HR"),
        sa.Column("group_label", sa.String(length=32), nullable=False, server_default="department"),
        sa.Column("id_label", sa.String(length=64), nullable=False, server_default="Employee ID"),
        sa.Column("require_checkout", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_checkout", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("track_late", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("track_early_leave", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("geofence_on_self_punch", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("auto_absent_at_close", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_multiple_present_per_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    bind = op.get_bind()
    office = bind.execute(sa.text("SELECT * FROM appsetting WHERE id = 1")).mappings().first()
    now = datetime.now(timezone.utc)
    if office:
        bind.execute(
            sa.text(
                """
                INSERT INTO organization (
                    name, tz, work_start, work_end, late_grace_minutes, office_name,
                    geo_lat, geo_lng, geo_radius_m, weekend, notify_late, allow_kiosk_pin,
                    org_type, kernel, subject_label, subject_label_plural, staff_label,
                    group_label, id_label, require_checkout, allow_checkout, track_late,
                    track_early_leave, geofence_on_self_punch, auto_absent_at_close,
                    allow_multiple_present_per_day, created_at, updated_at
                ) VALUES (
                    :name, :tz, :work_start, :work_end, :late_grace_minutes, :office_name,
                    :geo_lat, :geo_lng, :geo_radius_m, :weekend, :notify_late, :allow_kiosk_pin,
                    :org_type, :kernel, :subject_label, :subject_label_plural, :staff_label,
                    :group_label, :id_label, :require_checkout, :allow_checkout, :track_late,
                    :track_early_leave, :geofence_on_self_punch, :auto_absent_at_close,
                    :allow_multiple_present_per_day, :created_at, :updated_at
                )
                """
            ),
            {
                "name": office.get("office_name") or "HQ",
                "tz": office.get("tz") or "Asia/Kolkata",
                "work_start": office.get("work_start") or "09:00",
                "work_end": office.get("work_end") or "18:00",
                "late_grace_minutes": office.get("late_grace_minutes") or 15,
                "office_name": office.get("office_name") or "HQ",
                "geo_lat": office.get("geo_lat"),
                "geo_lng": office.get("geo_lng"),
                "geo_radius_m": office.get("geo_radius_m"),
                "weekend": office.get("weekend") or "6,7",
                "notify_late": bool(office.get("notify_late")),
                "allow_kiosk_pin": bool(office.get("allow_kiosk_pin")),
                "org_type": office.get("org_type") or "workplace",
                "kernel": office.get("kernel") or "daily_inout",
                "subject_label": office.get("subject_label") or "employee",
                "subject_label_plural": office.get("subject_label_plural") or "employees",
                "staff_label": office.get("staff_label") or "HR",
                "group_label": office.get("group_label") or "department",
                "id_label": office.get("id_label") or "Employee ID",
                "require_checkout": bool(office.get("require_checkout")),
                "allow_checkout": office.get("allow_checkout") if office.get("allow_checkout") is not None else True,
                "track_late": office.get("track_late") if office.get("track_late") is not None else True,
                "track_early_leave": office.get("track_early_leave") if office.get("track_early_leave") is not None else True,
                "geofence_on_self_punch": office.get("geofence_on_self_punch")
                if office.get("geofence_on_self_punch") is not None
                else True,
                "auto_absent_at_close": bool(office.get("auto_absent_at_close")),
                "allow_multiple_present_per_day": bool(office.get("allow_multiple_present_per_day")),
                "created_at": now,
                "updated_at": now,
            },
        )
    else:
        bind.execute(
            sa.text(
                """
                INSERT INTO organization (name, created_at, updated_at)
                VALUES ('HQ', :created_at, :updated_at)
                """
            ),
            {"created_at": now, "updated_at": now},
        )
    org_id = bind.execute(sa.text("SELECT id FROM organization ORDER BY id LIMIT 1")).scalar_one()

    for table in _ORG_TABLES:
        op.add_column(table, sa.Column("org_id", sa.Integer(), nullable=True))
        op.create_foreign_key(f"fk_{table}_org_id", table, "organization", ["org_id"], ["id"], ondelete="SET NULL")
        op.create_index(f"ix_{table}_org_id", table, ["org_id"])
        bind.execute(sa.text(f"UPDATE {table} SET org_id = :org_id WHERE org_id IS NULL"), {"org_id": org_id})

    bind.execute(
        sa.text("UPDATE \"user\" SET org_id = NULL WHERE is_admin = true AND person_id IS NULL"),
    )

    try:
        op.drop_constraint("person_employee_id_key", "person", type_="unique")
    except Exception:
        pass
    op.create_unique_constraint("uq_person_org_employee_id", "person", ["org_id", "employee_id"])


def downgrade() -> None:
    op.drop_constraint("uq_person_org_employee_id", "person", type_="unique")
    for table in reversed(_ORG_TABLES):
        op.drop_index(f"ix_{table}_org_id", table_name=table)
        op.drop_constraint(f"fk_{table}_org_id", table, type_="foreignkey")
        op.drop_column(table, "org_id")
    op.drop_table("organization")
