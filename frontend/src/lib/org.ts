import type { AuthConfig, OfficeSettings } from '../api/types'

export type OrgProfile = {
  orgType: string
  kernel: string
  subject: string
  subjectPlural: string
  staff: string
  group: string
  id: string
  allowCheckout: boolean
  requireCheckout: boolean
  trackLate: boolean
  trackEarlyLeave: boolean
  geofenceOnSelfPunch: boolean
  needsSchedule: boolean
  usesRoster: boolean
}

const DEFAULTS: OrgProfile = {
  orgType: 'workplace',
  kernel: 'daily_inout',
  subject: 'employee',
  subjectPlural: 'employees',
  staff: 'HR',
  group: 'department',
  id: 'Employee ID',
  allowCheckout: true,
  requireCheckout: false,
  trackLate: true,
  trackEarlyLeave: true,
  geofenceOnSelfPunch: true,
  needsSchedule: false,
  usesRoster: true,
}

export function titleCase(value: string) {
  if (!value) return value
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export function orgFrom(cfg: AuthConfig | OfficeSettings | null | undefined): OrgProfile {
  if (!cfg) return DEFAULTS
  const kernel = cfg.kernel || 'daily_inout'
  return {
    orgType: cfg.org_type || 'workplace',
    kernel,
    subject: cfg.subject_label || 'employee',
    subjectPlural: cfg.subject_label_plural || 'employees',
    staff: cfg.staff_label || 'HR',
    group: cfg.group_label || 'department',
    id: cfg.id_label || 'Employee ID',
    allowCheckout: cfg.allow_checkout !== false,
    requireCheckout: Boolean(cfg.require_checkout),
    trackLate: cfg.track_late !== false,
    trackEarlyLeave: Boolean(cfg.track_early_leave),
    geofenceOnSelfPunch: cfg.geofence_on_self_punch !== false,
    needsSchedule: kernel === 'session' || kernel === 'shift' || kernel === 'visit',
    usesRoster: kernel !== 'visit',
  }
}

export function roleCaption(role: string, org: OrgProfile) {
  if (role === 'admin') return 'Admin'
  if (role === 'hr') return org.staff
  if (role === 'operator') return 'Operator'
  return titleCase(org.subject)
}
