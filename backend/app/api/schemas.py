"""Pydantic request/response models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class LoginRequest(BaseModel):
    username: str
    password: str
    org: str | None = None


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(min_length=1, max_length=128)
    employee_id: str | None = None
    email: str | None = None
    org: str | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)


class SiteOut(BaseModel):
    id: int
    name: str
    lat: float | None = None
    lng: float | None = None
    radius_m: float | None = None
    is_default: bool = False


class AuthConfigOut(BaseModel):
    allow_public_register: bool
    require_liveness: bool
    tz: str
    office_name: str = "HQ"
    geofence: bool = False
    geo_radius_m: float | None = None
    allow_kiosk_pin: bool = False
    org_type: str = "workplace"
    kernel: str = "daily_inout"
    subject_label: str = "employee"
    subject_label_plural: str = "employees"
    staff_label: str = "HR"
    group_label: str = "department"
    id_label: str = "Employee ID"
    require_checkout: bool = False
    allow_checkout: bool = True
    track_late: bool = True
    track_early_leave: bool = True
    geofence_on_self_punch: bool = True
    auto_absent_at_close: bool = False
    allow_multiple_present_per_day: bool = False
    org_id: int | None = None
    org_name: str | None = None
    org_slug: str | None = None
    default_site: SiteOut | None = None


class LinkedPersonOut(BaseModel):
    id: int
    name: str
    employee_id: str | None
    n_embeddings: int = 0
    face_ready: bool = False
    is_active: bool = True


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    role: str = "employee"
    org_id: int | None = None
    org_name: str | None = None
    org_slug: str | None = None
    created_at: datetime
    person: LinkedPersonOut | None = None


class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    employee_id: str | None = None
    email: str | None = None
    notes: str | None = None
    department: str | None = None
    office: str | None = None
    shift_start: str | None = None
    shift_end: str | None = None


class PersonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    employee_id: str | None = None
    email: str | None = None
    notes: str | None = None
    department: str | None = None
    office: str | None = None
    shift_start: str | None = None
    shift_end: str | None = None


class PersonOut(BaseModel):
    id: int
    name: str
    employee_id: str | None
    email: str | None = None
    notes: str | None
    department: str | None = None
    office: str | None = None
    shift_start: str | None = None
    shift_end: str | None = None
    created_at: datetime
    n_embeddings: int = 0
    username: str | None = None
    is_active: bool = True
    status: str = "Active"


class PersonLoginIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=72)


class FaceInfo(BaseModel):
    bbox: list[float]
    score: float
    landmarks: list[list[float]]
    quality: dict = Field(default_factory=dict)


class VerifyResponse(BaseModel):
    match: bool
    similarity: float
    threshold: float
    far_target: float
    encoder: str
    face_a: FaceInfo
    face_b: FaceInfo


class VerifyPersonResponse(BaseModel):
    match: bool
    similarity: float
    threshold: float
    far_target: float
    encoder: str
    person: PersonOut
    face: FaceInfo


class MatchOut(BaseModel):
    person_id: int
    name: str
    similarity: float
    n_embeddings: int


class IdentifyResponse(BaseModel):
    identified: bool
    matches: list[MatchOut]
    threshold: float
    encoder: str
    gallery_size: int
    face: FaceInfo


class ChallengeOut(BaseModel):
    challenge_id: str
    instruction: str
    expires_in_s: int
    hold_ms: int = 1200
    hold_frames: int = 8
    blink_frames: int = 16
    interval_ms: int = 70


class LivenessResponse(BaseModel):
    live: bool
    blink: dict
    texture: dict
    instruction: str


class EventOut(BaseModel):
    id: int
    kind: str
    person_id: int | None
    person_name: str | None
    decision: str
    similarity: float | None
    encoder: str | None
    detail: str | None
    created_at: datetime


class HealthOut(BaseModel):
    status: str
    encoder: str
    gallery_size: int
    verify_threshold: float
    identify_threshold: float
    device: str


class ReadyOut(BaseModel):
    status: str
    database: str
    weights: str
    gallery: str
    encoder: str | None = None
    detail: str | None = None


class AttendanceOut(BaseModel):
    id: int
    person_id: int
    person_name: str
    user_id: int | None
    decision: str
    similarity: float | None
    encoder: str | None
    already_marked: bool = False
    created_at: datetime
    checked_out_at: datetime | None = None
    source: str = "web"
    late: bool = False
    early_leave: bool = False
    threshold: float | None = None
    face: FaceInfo | None = None
    occurrence_id: int | None = None
    occurrence_title: str | None = None
    site_id: int | None = None


class AttendanceUpdate(BaseModel):
    decision: str | None = None
    late: bool | None = None
    early_leave: bool | None = None
    checked_out: bool | None = None


class AttendanceManualIn(BaseModel):
    person_id: int
    decision: str = "present"
    late: bool = False
    early_leave: bool = False
    note: str | None = None
    occurrence_id: int | None = None


class AbsenceStreakOut(BaseModel):
    person_id: int
    person_name: str
    days: int


class BoardPersonOut(BaseModel):
    person_id: int
    person_name: str
    office: str | None = None
    checked_in_at: datetime | None = None
    late: bool = False
    source: str = "web"


class SessionTodayOut(BaseModel):
    id: int
    title: str
    kind: str
    start: str
    end: str
    overnight: bool = False
    room: str | None = None
    offering_id: int | None = None
    offering_name: str | None = None
    expected: int = 0
    present: int = 0
    open: bool = False


class OpsSummaryOut(BaseModel):
    pending_faces: int
    present_today: int
    late_today: int
    failed_today: int
    absent_today: int
    awaiting_login: int
    still_out: int = 0
    workday: bool = True
    tz: str
    work_start: str
    work_end: str
    office_name: str = "HQ"
    recent: list[AttendanceOut] = Field(default_factory=list)
    consecutive_absent: list[AbsenceStreakOut] = Field(default_factory=list)
    in_now: list[BoardPersonOut] = Field(default_factory=list)
    waiting: list[BoardPersonOut] = Field(default_factory=list)
    spoof_today: int = 0
    org_type: str = "workplace"
    kernel: str = "daily_inout"
    sessions_today: list[SessionTodayOut] = Field(default_factory=list)
    visits_today: int = 0


class OfficeSettingsOut(BaseModel):
    tz: str
    work_start: str
    work_end: str
    late_grace_minutes: int
    office_name: str = "HQ"
    geo_lat: float | None = None
    geo_lng: float | None = None
    geo_radius_m: float | None = None
    weekend: str = "6,7"
    notify_late: bool = False
    allow_kiosk_pin: bool = False
    org_type: str = "workplace"
    kernel: str = "daily_inout"
    subject_label: str = "employee"
    subject_label_plural: str = "employees"
    staff_label: str = "HR"
    group_label: str = "department"
    id_label: str = "Employee ID"
    require_checkout: bool = False
    allow_checkout: bool = True
    track_late: bool = True
    track_early_leave: bool = True
    geofence_on_self_punch: bool = True
    auto_absent_at_close: bool = False
    allow_multiple_present_per_day: bool = False


class OfficeSettingsUpdate(BaseModel):
    tz: str | None = None
    work_start: str | None = None
    work_end: str | None = None
    late_grace_minutes: int | None = Field(default=None, ge=0, le=180)
    office_name: str | None = None
    geo_lat: float | None = None
    geo_lng: float | None = None
    geo_radius_m: float | None = Field(default=None, ge=0, le=50_000)
    weekend: str | None = None
    notify_late: bool | None = None
    allow_kiosk_pin: bool | None = None
    org_type: str | None = None
    kernel: str | None = None
    subject_label: str | None = None
    subject_label_plural: str | None = None
    staff_label: str | None = None
    group_label: str | None = None
    id_label: str | None = None
    require_checkout: bool | None = None
    allow_checkout: bool | None = None
    track_late: bool | None = None
    track_early_leave: bool | None = None
    geofence_on_self_punch: bool | None = None
    auto_absent_at_close: bool | None = None
    allow_multiple_present_per_day: bool | None = None


class ImportResult(BaseModel):
    created: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


class StaffCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=72)
    role: str = Field(default="hr")


class StaffUpdate(BaseModel):
    role: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)


class StaffOut(BaseModel):
    id: int
    username: str
    role: str
    is_admin: bool
    person_id: int | None = None
    created_at: datetime


class HolidayIn(BaseModel):
    day: str
    name: str = Field(min_length=1, max_length=128)


class HolidayOut(BaseModel):
    id: int
    day: str
    name: str


class PersonTimelineOut(BaseModel):
    person: PersonOut
    attendance: list[AttendanceOut] = Field(default_factory=list)
    events: list[EventOut] = Field(default_factory=list)


class SpoofAlertOut(BaseModel):
    id: int
    actor_username: str | None = None
    person_id: int | None = None
    person_name: str | None = None
    source: str
    reason: str | None = None
    similarity: float | None = None
    seen: bool = False
    created_at: datetime


class OrgPresetOut(BaseModel):
    org_type: str
    title: str
    blurb: str
    kernel: str
    subject_label: str | None = None
    subject_label_plural: str | None = None
    staff_label: str | None = None
    group_label: str | None = None
    id_label: str | None = None


class SiteIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    lat: float | None = None
    lng: float | None = None
    radius_m: float | None = Field(default=None, ge=0, le=50_000)
    is_default: bool = False


class OfferingIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    code: str | None = None
    kind: str = "course"
    default_start: str | None = None
    default_end: str | None = None
    room: str | None = None
    site_id: int | None = None
    min_percent: int = Field(default=75, ge=0, le=100)


class OfferingOut(BaseModel):
    id: int
    name: str
    code: str | None = None
    kind: str
    default_start: str | None = None
    default_end: str | None = None
    room: str | None = None
    site_id: int | None = None
    min_percent: int = 75
    is_active: bool = True
    enrolled: int = 0


class EnrollmentIn(BaseModel):
    person_id: int


class EnrollmentOut(BaseModel):
    id: int
    person_id: int
    person_name: str
    offering_id: int
    offering_name: str


class OccurrenceIn(BaseModel):
    offering_id: int | None = None
    kind: str | None = None
    title: str | None = None
    day: str
    start: str = "09:00"
    end: str = "10:00"
    overnight: bool = False
    room: str | None = None
    site_id: int | None = None


class OccurrenceOut(BaseModel):
    id: int
    offering_id: int | None = None
    offering_name: str | None = None
    kind: str
    title: str
    day: str
    start: str
    end: str
    overnight: bool = False
    room: str | None = None
    site_id: int | None = None
    open: bool = False
    expected: int = 0
    present: int = 0
    already_marked: bool = False


class OfferingStatsOut(BaseModel):
    offering: OfferingOut
    meetings: int
    present_marks: int
    expected_marks: int
    percent: float
    below_min: list[dict] = Field(default_factory=list)


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str | None = Field(default=None, min_length=1, max_length=64)
    org_type: str = "workplace"
    tz: str | None = None
    work_start: str | None = None
    work_end: str | None = None
    late_grace_minutes: int | None = Field(default=None, ge=0, le=180)
    office_name: str | None = None


class OrgUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    slug: str | None = Field(default=None, min_length=1, max_length=64)
    org_type: str | None = None
    tz: str | None = None
    work_start: str | None = None
    work_end: str | None = None
    late_grace_minutes: int | None = Field(default=None, ge=0, le=180)
    office_name: str | None = None
    geo_lat: float | None = None
    geo_lng: float | None = None
    geo_radius_m: float | None = Field(default=None, ge=0, le=50_000)
    weekend: str | None = None
    notify_late: bool | None = None
    allow_kiosk_pin: bool | None = None
    kernel: str | None = None
    subject_label: str | None = None
    subject_label_plural: str | None = None
    staff_label: str | None = None
    group_label: str | None = None
    id_label: str | None = None
    require_checkout: bool | None = None
    allow_checkout: bool | None = None
    track_late: bool | None = None
    track_early_leave: bool | None = None
    geofence_on_self_punch: bool | None = None
    auto_absent_at_close: bool | None = None
    allow_multiple_present_per_day: bool | None = None


class OrgOut(BaseModel):
    id: int
    name: str
    slug: str
    org_type: str
    kernel: str
    people_count: int = 0
    office_name: str = "HQ"
    tz: str = "Asia/Kolkata"
    work_start: str = "09:00"
    work_end: str = "18:00"
    subject_label: str = "employee"
    subject_label_plural: str = "employees"
    created_at: datetime


class AssistChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class AssistCitation(BaseModel):
    type: str
    id: int


class AssistChatOut(BaseModel):
    answer: str
    citations: list[AssistCitation] = []


class AssistMessageOut(BaseModel):
    id: int
    role: str
    content: str
    citations: list[AssistCitation] = []
    created_at: datetime
