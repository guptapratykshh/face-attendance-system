export type Token = {
  access_token: string
  token_type: string
  username: string
}

export type Role = 'admin' | 'hr' | 'operator' | 'employee'

export type User = {
  id: number
  username: string
  is_admin: boolean
  role: Role
  org_id?: number | null
  org_name?: string | null
  org_slug?: string | null
  created_at: string
  person: LinkedPerson | null
}

export type LinkedPerson = {
  id: number
  name: string
  employee_id: string | null
  n_embeddings: number
  face_ready: boolean
  is_active: boolean
}

export type FaceInfo = {
  bbox: number[]
  score: number
  landmarks: number[][]
  quality: Record<string, number>
}

export type Person = {
  id: number
  name: string
  employee_id: string | null
  email: string | null
  notes: string | null
  department: string | null
  office: string | null
  shift_start: string | null
  shift_end: string | null
  created_at: string
  n_embeddings: number
  username: string | null
  is_active: boolean
  status: string
}

export type PersonTimeline = {
  person: Person
  attendance: AttendanceRecord[]
  events: AccessEvent[]
}

export type StaffUser = {
  id: number
  username: string
  role: Role
  is_admin: boolean
  person_id: number | null
  created_at: string
}

export type Holiday = {
  id: number
  day: string
  name: string
}

export type SpoofAlert = {
  id: number
  actor_username: string | null
  person_id: number | null
  person_name: string | null
  source: string
  reason: string | null
  similarity: number | null
  seen: boolean
  created_at: string
}

export type VerifyResponse = {
  match: boolean
  similarity: number
  threshold: number
  far_target: number
  encoder: string
  face_a: FaceInfo
  face_b: FaceInfo
}

export type VerifyPersonResponse = {
  match: boolean
  similarity: number
  threshold: number
  far_target: number
  encoder: string
  person: Person
  face: FaceInfo
}

export type MatchOut = {
  person_id: number
  name: string
  similarity: number
  n_embeddings: number
}

export type IdentifyResponse = {
  identified: boolean
  matches: MatchOut[]
  threshold: number
  encoder: string
  gallery_size: number
  face: FaceInfo
}

export type Challenge = {
  challenge_id: string
  instruction: string
  expires_in_s: number
  hold_ms?: number
  hold_frames?: number
  blink_frames?: number
  interval_ms?: number
}

export type CapturePathResult = {
  live: boolean
  score: number
  reason: string
  features: Record<string, number | null>
}

export type LivenessResponse = {
  live: boolean
  blink: Record<string, unknown>
  texture: Record<string, unknown>
  capture_path?: CapturePathResult | null
  instruction: string
}

export type AccessEvent = {
  id: number
  kind: string
  person_id: number | null
  person_name: string | null
  decision: string
  similarity: number | null
  encoder: string | null
  detail: string | null
  created_at: string
}

export type Health = {
  status: string
  encoder: string
  gallery_size: number
  verify_threshold: number
  identify_threshold: number
  device: string
}

export type TarPoint = { tar: number; threshold: number; far_target: number }

export type EncoderResult = {
  encoder: string
  eer: number
  accuracy?: { mean: number; std: number; per_fold: number[] }
  tar_at_far: Record<string, TarPoint>
  genuine: { mean: number; std: number; min: number; max: number }
  impostor: { mean: number; std: number; min: number; max: number }
  roc: { far: number[]; tar: number[] }
  score_histogram?: { bin_centers: number[]; genuine: number[]; impostor: number[] }
}

export type EvalReport = {
  generated_at: string
  protocol: Record<string, unknown>
  results: Record<string, EncoderResult>
  served_encoder: string
}

export type AttendanceRecord = {
  id: number
  person_id: number
  person_name: string
  user_id: number | null
  decision: string
  similarity: number | null
  encoder: string | null
  already_marked: boolean
  created_at: string
  checked_out_at: string | null
  source: string
  late: boolean
  early_leave?: boolean
  threshold: number | null
  occurrence_id?: number | null
  occurrence_title?: string | null
  site_id?: number | null
}

export type SessionToday = {
  id: number
  title: string
  kind: string
  start: string
  end: string
  overnight?: boolean
  room?: string | null
  offering_id?: number | null
  offering_name?: string | null
  expected: number
  present: number
  open: boolean
}

export type OpsSummary = {
  pending_faces: number
  present_today: number
  late_today: number
  failed_today: number
  absent_today: number
  awaiting_login: number
  still_out?: number
  workday?: boolean
  tz: string
  work_start: string
  work_end: string
  recent: AttendanceRecord[]
  consecutive_absent?: AbsenceStreak[]
  office_name?: string
  in_now?: BoardPerson[]
  waiting?: BoardPerson[]
  spoof_today?: number
  org_type?: string
  kernel?: string
  sessions_today?: SessionToday[]
  visits_today?: number
}

export type AbsenceStreak = {
  person_id: number
  person_name: string
  days: number
}

export type AssistCitation = {
  type: string
  id: number
}

export type AssistChatOut = {
  answer: string
  citations: AssistCitation[]
}

export type AssistMessage = {
  id: number
  role: string
  content: string
  citations: AssistCitation[]
  created_at: string
}

export type BoardPerson = {
  person_id: number
  person_name: string
  office?: string | null
  checked_in_at?: string | null
  late?: boolean
  source?: string
}

export type OfficeSettings = {
  tz: string
  work_start: string
  work_end: string
  late_grace_minutes: number
  office_name: string
  geo_lat: number | null
  geo_lng: number | null
  geo_radius_m: number | null
  weekend: string
  notify_late: boolean
  allow_kiosk_pin?: boolean
  org_type?: string
  kernel?: string
  subject_label?: string
  subject_label_plural?: string
  staff_label?: string
  group_label?: string
  id_label?: string
  require_checkout?: boolean
  allow_checkout?: boolean
  track_late?: boolean
  track_early_leave?: boolean
  geofence_on_self_punch?: boolean
  auto_absent_at_close?: boolean
  allow_multiple_present_per_day?: boolean
}

export type AuthConfig = {
  allow_public_register: boolean
  require_liveness: boolean
  tz: string
  office_name?: string
  geofence?: boolean
  geo_radius_m?: number | null
  allow_kiosk_pin?: boolean
  org_type?: string
  kernel?: string
  subject_label?: string
  subject_label_plural?: string
  staff_label?: string
  group_label?: string
  id_label?: string
  require_checkout?: boolean
  allow_checkout?: boolean
  track_late?: boolean
  track_early_leave?: boolean
  geofence_on_self_punch?: boolean
  auto_absent_at_close?: boolean
  allow_multiple_present_per_day?: boolean
  org_id?: number | null
  org_name?: string | null
  org_slug?: string | null
  default_site?: Site | null
}

export type OrgPreset = {
  org_type: string
  title: string
  blurb: string
  kernel: string
  subject_label?: string | null
  group_label?: string | null
  id_label?: string | null
}

export type Organization = {
  id: number
  name: string
  slug: string
  org_type: string
  kernel: string
  people_count: number
  office_name: string
  tz: string
  work_start: string
  work_end: string
  subject_label: string
  subject_label_plural: string
  created_at: string
}

export type Site = {
  id: number
  name: string
  lat: number | null
  lng: number | null
  radius_m: number | null
  is_default: boolean
}

export type Offering = {
  id: number
  name: string
  code: string | null
  kind: string
  default_start: string | null
  default_end: string | null
  room: string | null
  site_id: number | null
  min_percent: number
  is_active: boolean
  enrolled: number
}

export type Occurrence = {
  id: number
  offering_id: number | null
  offering_name: string | null
  kind: string
  title: string
  day: string
  start: string
  end: string
  overnight: boolean
  room: string | null
  site_id: number | null
  open: boolean
  expected: number
  present: number
  already_marked: boolean
}

export type Enrollment = {
  id: number
  person_id: number
  person_name: string
  offering_id: number
  offering_name: string
}

export type OfferingStats = {
  offering: Offering
  meetings: number
  present_marks: number
  expected_marks: number
  percent: number
  below_min: { person_id: number; person_name: string; percent: number; present: number; meetings: number }[]
}

export class ApiError extends Error {
  status: number
  code?: string
  detail: string

  constructor(status: number, detail: string, code?: string) {
    super(detail)
    this.status = status
    this.detail = detail
    this.code = code
  }
}

export function roleOf(user: User | null | undefined): Role {
  if (!user) return 'employee'
  if (user.is_admin) return 'admin'
  return user.role || 'employee'
}

export function canManagePeople(user: User | null | undefined) {
  const role = roleOf(user)
  return role === 'admin' || role === 'hr'
}

export function canUseLab(user: User | null | undefined) {
  const role = roleOf(user)
  return role === 'admin' || role === 'operator'
}

export function isStaff(user: User | null | undefined) {
  const role = roleOf(user)
  return role === 'admin' || role === 'hr' || role === 'operator'
}

export function isPlatformAdmin(user: User | null | undefined) {
  return Boolean(user?.is_admin && (user.org_id == null || user.org_id === undefined))
}

export function homePath(user: User | null | undefined) {
  if (!user) return '/login'
  if (isPlatformAdmin(user)) return '/orgs'
  if (canManagePeople(user)) return '/'
  if (canUseLab(user)) return '/lab'
  return '/attendance'
}
