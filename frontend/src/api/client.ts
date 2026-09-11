import axios, { AxiosError } from 'axios'
import {
  ApiError,
  type AttendanceRecord,
  type AuthConfig,
  type Challenge,
  type EvalReport,
  type Health,
  type Holiday,
  type IdentifyResponse,
  type LivenessResponse,
  type AccessEvent,
  type AssistChatOut,
  type AssistMessage,
  type Enrollment,
  type Occurrence,
  type Offering,
  type OfferingStats,
  type OfficeSettings,
  type Organization,
  type OrgPreset,
  type Site,
  type OpsSummary,
  type Person,
  type PersonTimeline,
  type SpoofAlert,
  type StaffUser,
  type Token,
  type User,
  type VerifyPersonResponse,
  type VerifyResponse,
} from './types'

const client = axios.create({ baseURL: '/api/v1' })

client.interceptors.request.use((config) => {
  try {
    const token = globalThis.localStorage?.getItem('frs_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    const isPlatform = globalThis.localStorage?.getItem('frs_is_platform') === '1'
    const orgId = globalThis.localStorage?.getItem('frs_org_id')
    if (isPlatform && orgId) {
      config.headers['X-Org-Id'] = orgId
    }
  } catch {
    /* jsdom without a working localStorage */
  }
  return config
})

function toApiError(err: unknown): ApiError {
  const ax = err as AxiosError<{ detail?: string | { msg?: string }[]; code?: string }>
  const status = ax.response?.status ?? 0
  const data = ax.response?.data
  const raw = data?.detail
  const detail =
    (typeof raw === 'string' && raw) ||
    ax.message ||
    'request failed'
  const friendly =
    detail === 'Not Found'
      ? 'This API is out of date — restart the Sentinel backend.'
      : detail === 'face_not_recognized'
        ? 'We could not recognize that face.'
        : detail === 'location_required'
          ? 'Turn on location. You must be at the office to check in.'
          : detail === 'outside_geofence'
            ? 'You are not at the office. Go to the workplace, then check in.'
            : detail === 'kiosk_pin_disabled'
              ? 'ID check-in is off. Use the camera, or ask staff to turn ID fallback on.'
              : detail === 'checkout_disabled'
                ? 'Check-out is off for this organization.'
                : detail === 'occurrence_required'
                  ? 'Pick a class, shift, or session first.'
                  : detail === 'no_open_session'
                    ? 'No session is open right now.'
                  : detail === 'org_required'
                    ? 'Open an organization first.'
                    : detail === 'platform_admin_only'
                      ? 'Only the platform admin can manage organizations.'
            : detail
  return new ApiError(status, friendly, data?.code)
}

async function unwrap<T>(p: Promise<{ data: T }>): Promise<T> {
  try {
    return (await p).data
  } catch (err) {
    throw toApiError(err)
  }
}

export const api = {
  login: (username: string, password: string, org?: string) =>
    unwrap<Token>(client.post('/auth/login', { username, password, ...(org ? { org } : {}) })),
  register: (body: {
    username: string
    password: string
    name: string
    employee_id?: string
    email?: string
    org?: string
  }) => unwrap<User>(client.post('/auth/register', body)),
  me: () => unwrap<User>(client.get('/auth/me')),
  authConfig: () => unwrap<AuthConfig>(client.get('/auth/config')),
  changePassword: (current_password: string, new_password: string) =>
    unwrap<User>(client.post('/auth/password', { current_password, new_password })),
  health: () => unwrap<Health>(client.get('/health')),
  metrics: () => unwrap<EvalReport>(client.get('/metrics')),

  listPersons: (includeInactive = false) =>
    unwrap<Person[]>(client.get('/persons', { params: { include_inactive: includeInactive } })),
  getPerson: (id: number) => unwrap<Person>(client.get(`/persons/${id}`)),
  personTimeline: (id: number) => unwrap<PersonTimeline>(client.get(`/persons/${id}/timeline`)),
  createPerson: (body: {
    name: string
    employee_id?: string
    email?: string
    notes?: string
    department?: string
    office?: string
    shift_start?: string
    shift_end?: string
  }) => unwrap<Person>(client.post('/persons', body)),
  updatePerson: (
    id: number,
    body: {
      name?: string
      employee_id?: string | null
      email?: string | null
      notes?: string | null
      department?: string | null
      office?: string | null
      shift_start?: string | null
      shift_end?: string | null
    },
  ) => unwrap<Person>(client.patch(`/persons/${id}`, body)),
  deletePerson: (id: number) => unwrap<void>(client.delete(`/persons/${id}`)),
  reactivatePerson: (id: number) => unwrap<Person>(client.post(`/persons/${id}/reactivate`)),
  setPersonLogin: (id: number, body: { username: string; password: string }) =>
    unwrap<Person>(client.post(`/persons/${id}/login`, body)),
  enroll: (id: number, files: File[]) => {
    const fd = new FormData()
    files.forEach((f) => fd.append('images', f))
    return unwrap<Person>(client.post(`/persons/${id}/enroll`, fd))
  },
  importPersons: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return unwrap<{ created: number; skipped: number; errors: string[] }>(client.post('/persons/import', fd))
  },

  verify: (a: File, b: File) => {
    const fd = new FormData()
    fd.append('image_a', a)
    fd.append('image_b', b)
    return unwrap<VerifyResponse>(client.post('/verify', fd))
  },
  verifyPerson: (personId: number, image: File) => {
    const fd = new FormData()
    fd.append('image', image)
    return unwrap<VerifyPersonResponse>(client.post(`/verify/person/${personId}`, fd))
  },
  identify: (image: File, topK = 5) => {
    const fd = new FormData()
    fd.append('image', image)
    return unwrap<IdentifyResponse>(client.post(`/identify?top_k=${topK}`, fd))
  },

  issueChallenge: () => unwrap<Challenge>(client.post('/liveness/challenge')),
  checkLiveness: (challengeId: string, frames: Blob[], source = 'lab', probe?: unknown) => {
    const fd = new FormData()
    fd.append('challenge_id', challengeId)
    fd.append('source', source)
    if (probe) fd.append('capture_probe', JSON.stringify(probe))
    frames.forEach((b, i) => fd.append('frames', b, `frame-${i}.jpg`))
    return unwrap<LivenessResponse>(client.post('/liveness/check', fd))
  },

  events: (params?: { limit?: number; kind?: string; person_id?: number; from?: string; to?: string }) =>
    unwrap<AccessEvent[]>(client.get('/events', { params: { limit: 50, ...params } })),

  checkIn: (
    image: File,
    challengeId?: string,
    coords?: { lat: number; lng: number },
    extra?: { occurrenceId?: number; siteId?: number },
  ) => {
    const fd = new FormData()
    fd.append('image', image)
    if (challengeId) fd.append('challenge_id', challengeId)
    if (coords) {
      fd.append('latitude', String(coords.lat))
      fd.append('longitude', String(coords.lng))
    }
    if (extra?.occurrenceId != null) fd.append('occurrence_id', String(extra.occurrenceId))
    if (extra?.siteId != null) fd.append('site_id', String(extra.siteId))
    return unwrap<AttendanceRecord>(client.post('/attendance/check-in', fd))
  },
  checkOut: (image?: File, challengeId?: string) => {
    if (!image && !challengeId) return unwrap<AttendanceRecord>(client.post('/attendance/check-out'))
    const fd = new FormData()
    if (image) fd.append('image', image)
    if (challengeId) fd.append('challenge_id', challengeId)
    return unwrap<AttendanceRecord>(client.post('/attendance/check-out', fd))
  },
  todayAttendance: () => unwrap<AttendanceRecord | null>(client.get('/attendance/today')),
  myAttendance: () => unwrap<AttendanceRecord[]>(client.get('/attendance/me')),
  listAttendance: (params?: { from?: string; to?: string; person_id?: number; decision?: string }) =>
    unwrap<AttendanceRecord[]>(client.get('/attendance', { params })),
  updateAttendance: (
    id: number,
    body: { decision?: string; late?: boolean; early_leave?: boolean; checked_out?: boolean },
  ) => unwrap<AttendanceRecord>(client.patch(`/attendance/${id}`, body)),
  manualAttendance: (body: { person_id: number; decision?: string; late?: boolean; note?: string; occurrence_id?: number }) =>
    unwrap<AttendanceRecord>(client.post('/attendance/manual', body)),
  exportAttendanceUrl: (params?: { from?: string; to?: string; person_id?: number; decision?: string }) => {
    const search = new URLSearchParams()
    if (params?.from) search.set('from', params.from)
    if (params?.to) search.set('to', params.to)
    if (params?.person_id != null) search.set('person_id', String(params.person_id))
    if (params?.decision) search.set('decision', params.decision)
    const q = search.toString()
    return `/api/v1/attendance/export${q ? `?${q}` : ''}`
  },
  kioskPunch: (
    image: File,
    challengeId?: string,
    coords?: { lat: number; lng: number },
    extra?: { occurrenceId?: number; siteId?: number },
  ) => {
    const fd = new FormData()
    fd.append('image', image)
    if (challengeId) fd.append('challenge_id', challengeId)
    if (coords) {
      fd.append('latitude', String(coords.lat))
      fd.append('longitude', String(coords.lng))
    }
    if (extra?.occurrenceId != null) fd.append('occurrence_id', String(extra.occurrenceId))
    if (extra?.siteId != null) fd.append('site_id', String(extra.siteId))
    return unwrap<AttendanceRecord>(client.post('/attendance/kiosk', fd))
  },
  kioskPin: (pin: string, coords?: { lat: number; lng: number }, extra?: { occurrenceId?: number }) => {
    const fd = new FormData()
    fd.append('pin', pin)
    if (coords) {
      fd.append('latitude', String(coords.lat))
      fd.append('longitude', String(coords.lng))
    }
    if (extra?.occurrenceId != null) fd.append('occurrence_id', String(extra.occurrenceId))
    return unwrap<AttendanceRecord>(client.post('/attendance/kiosk', fd))
  },

  opsSummary: () => unwrap<OpsSummary>(client.get('/ops/summary')),
  officeSettings: () => unwrap<OfficeSettings>(client.get('/settings')),
  updateOfficeSettings: (body: Partial<OfficeSettings>) => unwrap<OfficeSettings>(client.patch('/settings', body)),
  orgPresets: () => unwrap<OrgPreset[]>(client.get('/settings/presets')),
  listOrgs: () => unwrap<Organization[]>(client.get('/orgs')),
  createOrg: (body: { name: string; org_type: string; tz?: string; work_start?: string; work_end?: string }) =>
    unwrap<Organization>(client.post('/orgs', body)),
  getOrg: (id: number) => unwrap<Organization>(client.get(`/orgs/${id}`)),
  updateOrg: (id: number, body: Partial<Organization> & { org_type?: string }) =>
    unwrap<Organization>(client.patch(`/orgs/${id}`, body)),

  listSites: () => unwrap<Site[]>(client.get('/schedule/sites')),
  createSite: (body: { name: string; lat?: number | null; lng?: number | null; radius_m?: number | null; is_default?: boolean }) =>
    unwrap<Site>(client.post('/schedule/sites', body)),
  deleteSite: (id: number) => unwrap<void>(client.delete(`/schedule/sites/${id}`)),
  listOfferings: () => unwrap<Offering[]>(client.get('/schedule/offerings')),
  createOffering: (body: {
    name: string
    code?: string
    kind?: string
    default_start?: string
    default_end?: string
    room?: string
    min_percent?: number
  }) => unwrap<Offering>(client.post('/schedule/offerings', body)),
  deleteOffering: (id: number) => unwrap<void>(client.delete(`/schedule/offerings/${id}`)),
  offeringEnrollments: (id: number) => unwrap<Enrollment[]>(client.get(`/schedule/offerings/${id}/enrollments`)),
  enrollInOffering: (offeringId: number, personId: number) =>
    unwrap<Enrollment>(client.post(`/schedule/offerings/${offeringId}/enrollments`, { person_id: personId })),
  dropEnrollment: (id: number) => unwrap<void>(client.delete(`/schedule/enrollments/${id}`)),
  offeringStats: (id: number) => unwrap<OfferingStats>(client.get(`/schedule/offerings/${id}/stats`)),
  listOccurrences: (params?: { day?: string; offering_id?: number; open_now?: boolean }) =>
    unwrap<Occurrence[]>(client.get('/schedule/occurrences', { params })),
  mySchedule: () => unwrap<Occurrence[]>(client.get('/schedule/mine')),
  createOccurrence: (body: {
    offering_id?: number
    kind?: string
    title?: string
    day: string
    start?: string
    end?: string
    overnight?: boolean
    room?: string
    site_id?: number
  }) => unwrap<Occurrence>(client.post('/schedule/occurrences', body)),
  deleteOccurrence: (id: number) => unwrap<void>(client.delete(`/schedule/occurrences/${id}`)),

  listUsers: () => unwrap<StaffUser[]>(client.get('/users')),
  createUser: (body: { username: string; password: string; role: string }) =>
    unwrap<StaffUser>(client.post('/users', body)),
  updateUser: (id: number, body: { role?: string; password?: string }) =>
    unwrap<StaffUser>(client.patch(`/users/${id}`, body)),

  listHolidays: () => unwrap<Holiday[]>(client.get('/holidays')),
  createHoliday: (body: { day: string; name: string }) => unwrap<Holiday>(client.post('/holidays', body)),
  deleteHoliday: (id: number) => unwrap<void>(client.delete(`/holidays/${id}`)),

  spoofAlerts: () => unwrap<SpoofAlert[]>(client.get('/ops/spoof-alerts', { params: { limit: 40 } })),
  spoofAlertImageUrl: (id: number) => `/api/v1/ops/spoof-alerts/${id}/image`,
  spoofAlertImage: async (id: number) => {
    const token = globalThis.localStorage?.getItem('frs_token')
    const orgId = globalThis.localStorage?.getItem('frs_org_id')
    const headers: Record<string, string> = {}
    if (token) headers.Authorization = `Bearer ${token}`
    if (orgId) headers['X-Org-Id'] = orgId
    const res = await fetch(`/api/v1/ops/spoof-alerts/${id}/image`, { headers })
    if (!res.ok) throw new Error('Could not load the blocked photo')
    return res.blob()
  },
  markSpoofSeen: (id: number) => unwrap<SpoofAlert>(client.post(`/ops/spoof-alerts/${id}/seen`)),

  assistChat: (message: string) =>
    unwrap<AssistChatOut>(client.post('/assist/chat', { message })),
  assistHistory: () => unwrap<AssistMessage[]>(client.get('/assist/history', { params: { limit: 40 } })),

  exportEventsUrl: (params?: { kind?: string; from?: string; to?: string }) => {
    const search = new URLSearchParams()
    if (params?.kind) search.set('kind', params.kind)
    if (params?.from) search.set('from', params.from)
    if (params?.to) search.set('to', params.to)
    const q = search.toString()
    return `/api/v1/events/export${q ? `?${q}` : ''}`
  },
}

export { client }
