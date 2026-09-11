"""SQLModel tables for operators, enrolled identities, embeddings, and access events."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import Column, ForeignKey, Index, Integer, LargeBinary, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def _org_id_column(*, nullable: bool = True):
    return Column(
        Integer,
        ForeignKey("organization.id", ondelete="SET NULL"),
        nullable=nullable,
        index=True,
    )


class Organization(SQLModel, table=True):
    """One workplace, school, college, or other attendance workspace."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, min_length=1, max_length=128)
    slug: str = Field(index=True, unique=True, min_length=1, max_length=64)
    tz: str = Field(default="Asia/Kolkata", max_length=64)
    work_start: str = Field(default="09:00", max_length=8)
    work_end: str = Field(default="18:00", max_length=8)
    late_grace_minutes: int = 15
    office_name: str = Field(default="HQ", max_length=64)
    geo_lat: float | None = None
    geo_lng: float | None = None
    geo_radius_m: float | None = None
    weekend: str = Field(default="6,7", max_length=16)
    notify_late: bool = False
    allow_kiosk_pin: bool = False
    org_type: str = Field(default="workplace", max_length=32)
    kernel: str = Field(default="daily_inout", max_length=32)
    subject_label: str = Field(default="employee", max_length=32)
    subject_label_plural: str = Field(default="employees", max_length=32)
    staff_label: str = Field(default="HR", max_length=32)
    group_label: str = Field(default="department", max_length=32)
    id_label: str = Field(default="Employee ID", max_length=64)
    require_checkout: bool = False
    allow_checkout: bool = True
    track_late: bool = True
    track_early_leave: bool = True
    geofence_on_self_punch: bool = True
    auto_absent_at_close: bool = False
    allow_multiple_present_per_day: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PlatformUser(SQLModel, table=True):
    """Platform admin only. Lives in public; not tied to an organization."""

    __tablename__ = "platform_user"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, min_length=3, max_length=64)
    hashed_password: str
    is_admin: bool = True
    role: str = Field(default="admin", max_length=32)
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def org_id(self) -> int | None:
        return None

    @property
    def person_id(self) -> int | None:
        return None

    def __repr__(self) -> str:  # pragma: no cover
        return f"PlatformUser({self.username!r})"


class User(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("org_id", "username", name="uq_user_org_username"),)

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, min_length=3, max_length=64)
    hashed_password: str
    is_admin: bool = False
    role: str = Field(default="employee", max_length=32, index=True)
    org_id: int | None = Field(default=None, sa_column=_org_id_column())
    person_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("person.id", ondelete="SET NULL"),
            nullable=True,
            unique=True,
            index=True,
        ),
    )
    created_at: datetime = Field(default_factory=utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"User({self.username!r}, role={self.role!r})"


class Person(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("org_id", "employee_id", name="uq_person_org_employee_id"),)

    id: int | None = Field(default=None, primary_key=True)
    org_id: int | None = Field(default=None, sa_column=_org_id_column())
    name: str = Field(index=True, min_length=1, max_length=128)
    employee_id: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=256)
    notes: str | None = None
    department: str | None = Field(default=None, max_length=64)
    office: str | None = Field(default=None, max_length=64)
    shift_start: str | None = Field(default=None, max_length=8)
    shift_end: str | None = Field(default=None, max_length=8)
    is_active: bool = Field(default=True, index=True)
    deactivated_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class FaceEmbedding(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    person_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("person.id", ondelete="RESTRICT"), nullable=False, index=True
        )
    )
    encoder: str = Field(index=True, max_length=64)
    dim: int
    vector: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    quality_json: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class AccessEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    org_id: int | None = Field(default=None, sa_column=_org_id_column())
    kind: str = Field(index=True, max_length=32)
    person_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("person.id", ondelete="SET NULL"), nullable=True, index=True
        ),
    )
    person_name: str | None = None
    decision: str = Field(max_length=32)
    similarity: float | None = None
    encoder: str | None = None
    detail: str | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)


class Site(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    org_id: int | None = Field(default=None, sa_column=_org_id_column())
    name: str = Field(max_length=128)
    lat: float | None = None
    lng: float | None = None
    radius_m: float | None = None
    is_default: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Offering(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    org_id: int | None = Field(default=None, sa_column=_org_id_column())
    name: str = Field(index=True, min_length=1, max_length=128)
    code: str | None = Field(default=None, max_length=32, index=True)
    kind: str = Field(default="course", max_length=32)
    default_start: str | None = Field(default=None, max_length=8)
    default_end: str | None = Field(default=None, max_length=8)
    room: str | None = Field(default=None, max_length=64)
    site_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("site.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    min_percent: int = 75
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Enrollment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("person_id", "offering_id", name="uq_enrollment_person_offering"),)

    id: int | None = Field(default=None, primary_key=True)
    org_id: int | None = Field(default=None, sa_column=_org_id_column())
    person_id: int = Field(
        sa_column=Column(Integer, ForeignKey("person.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    offering_id: int = Field(
        sa_column=Column(Integer, ForeignKey("offering.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    created_at: datetime = Field(default_factory=utcnow)


class Occurrence(SQLModel, table=True):
    __table_args__ = (Index("ix_occurrence_day_kind", "day", "kind"),)

    id: int | None = Field(default=None, primary_key=True)
    org_id: int | None = Field(default=None, sa_column=_org_id_column())
    offering_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("offering.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    kind: str = Field(default="session", max_length=32, index=True)
    title: str = Field(max_length=128)
    day: date = Field(index=True)
    start: str = Field(default="09:00", max_length=8)
    end: str = Field(default="10:00", max_length=8)
    overnight: bool = False
    room: str | None = Field(default=None, max_length=64)
    site_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("site.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    created_at: datetime = Field(default_factory=utcnow)


class Attendance(SQLModel, table=True):
    __table_args__ = (
        Index("ix_attendance_person_created", "person_id", "created_at"),
        Index("ix_attendance_occurrence", "occurrence_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    org_id: int | None = Field(default=None, sa_column=_org_id_column())
    person_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("person.id", ondelete="RESTRICT"), nullable=False, index=True
        )
    )
    user_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
        ),
    )
    occurrence_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("occurrence.id", ondelete="SET NULL"), nullable=True, index=True
        ),
    )
    site_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("site.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    decision: str = Field(max_length=32)
    similarity: float | None = None
    encoder: str | None = None
    source: str = Field(default="web", max_length=32)
    late: bool = False
    early_leave: bool = False
    latitude: float | None = None
    longitude: float | None = None
    # Fused presence-trust probability and the per-signal contributions behind it.
    trust_score: float | None = None
    trust_breakdown_json: str | None = None
    checked_out_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)


class AppSetting(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tz: str = Field(default="Asia/Kolkata", max_length=64)
    work_start: str = Field(default="09:00", max_length=8)
    work_end: str = Field(default="18:00", max_length=8)
    late_grace_minutes: int = 15
    office_name: str = Field(default="HQ", max_length=64)
    geo_lat: float | None = None
    geo_lng: float | None = None
    geo_radius_m: float | None = None
    weekend: str = Field(default="6,7", max_length=16)
    notify_late: bool = False
    allow_kiosk_pin: bool = False
    org_type: str = Field(default="workplace", max_length=32)
    kernel: str = Field(default="daily_inout", max_length=32)
    subject_label: str = Field(default="employee", max_length=32)
    subject_label_plural: str = Field(default="employees", max_length=32)
    staff_label: str = Field(default="HR", max_length=32)
    group_label: str = Field(default="department", max_length=32)
    id_label: str = Field(default="Employee ID", max_length=64)
    require_checkout: bool = False
    allow_checkout: bool = True
    track_late: bool = True
    track_early_leave: bool = True
    geofence_on_self_punch: bool = True
    auto_absent_at_close: bool = False
    allow_multiple_present_per_day: bool = False
    updated_at: datetime = Field(default_factory=utcnow)


class Holiday(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    org_id: int | None = Field(default=None, sa_column=_org_id_column())
    day: date = Field(index=True)
    name: str = Field(max_length=128)
    created_at: datetime = Field(default_factory=utcnow)


class SpoofAlert(SQLModel, table=True):
    """A blocked photo/video check-in, with the captured frame for HR and admin."""

    id: int | None = Field(default=None, primary_key=True)
    org_id: int | None = Field(default=None, sa_column=_org_id_column())
    actor_user_id: int | None = Field(default=None, index=True)
    actor_username: str | None = Field(default=None, max_length=64)
    person_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("person.id", ondelete="SET NULL"), nullable=True, index=True
        ),
    )
    person_name: str | None = Field(default=None, max_length=128)
    source: str = Field(default="attendance", max_length=32, index=True)
    reason: str | None = None
    similarity: float | None = None
    image: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    seen_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)


class CaptureProbe(SQLModel, table=True):
    """One browser constraint-probe session, kept as the training set for virtual-camera detection.

    Stored whether or not the punch succeeded: bonafide sessions are the negative class, and a
    session that failed for an unrelated reason is still valid capture-path evidence.
    """

    id: int | None = Field(default=None, primary_key=True)
    org_id: int | None = Field(default=None, sa_column=_org_id_column())
    user_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
        ),
    )
    challenge_id: str | None = Field(default=None, max_length=64, index=True)
    source: str = Field(default="attendance", max_length=32, index=True)
    score: float | None = None
    live: bool | None = None
    scored_by: str | None = Field(default=None, max_length=16)
    reason: str | None = None
    features_json: str | None = None
    report_json: str | None = None
    # Set by scripts/collect_capture_sessions.py: bonafide | virtual_static | virtual_replay |
    # virtual_faceswap. Null for production traffic, which is unlabelled.
    label: str | None = Field(default=None, max_length=32, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class AssistChunk(SQLModel, table=True):
    """Retrieved RAG text chunk for the language / LLM assist modality."""

    id: int | None = Field(default=None, primary_key=True)
    org_id: int | None = Field(default=None, sa_column=_org_id_column())
    source_type: str = Field(max_length=32, index=True)  # attendance | person | faq
    source_id: int | None = Field(default=None, index=True)
    text: str
    embedding_json: str | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)


class AssistMessage(SQLModel, table=True):
    """Chat history for Assist (does not mutate attendance)."""

    id: int | None = Field(default=None, primary_key=True)
    org_id: int | None = Field(default=None, sa_column=_org_id_column())
    user_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
        ),
    )
    role: str = Field(max_length=16)  # user | assistant
    content: str
    citations_json: str | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)
