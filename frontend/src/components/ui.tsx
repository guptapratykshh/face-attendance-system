import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { IconMoon, IconSun } from './icons'
import { useTheme } from '../hooks/useTheme'

export const inputClass =
  'w-full rounded-xl border border-line bg-panel px-3.5 py-2.5 text-sm text-ink shadow-sm placeholder:text-muted focus:border-ink focus:outline-none focus:ring-2 focus:ring-ink/15'

export const cardClass = 'rounded-2xl border border-line bg-panel shadow-[0_1px_2px_rgba(0,0,0,0.06)]'

export const listScrollClass = 'max-h-[min(22rem,calc(100dvh-16rem))] overflow-y-auto overscroll-contain'

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow?: string
  title: string
  subtitle?: string
  actions?: ReactNode
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow ? (
          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">{eyebrow}</div>
        ) : null}
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle ? <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  )
}

export function Button({
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' | 'ghost' }) {
  const styles = {
    primary: 'bg-accent text-accent-fg hover:opacity-90 shadow-sm',
    secondary: 'border border-line bg-panel text-ink hover:bg-soft',
    danger: 'border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 dark:border-rose-900 dark:bg-rose-950/50 dark:text-rose-300 dark:hover:bg-rose-950',
    ghost: 'text-muted hover:bg-soft hover:text-ink',
  }[variant]
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center rounded-xl px-4 py-2.5 text-sm font-semibold transition active:scale-[0.98] disabled:opacity-50 ${styles} ${className}`}
    />
  )
}

export function Alert({
  kind,
  children,
}: {
  kind: 'error' | 'ok' | 'wait' | 'info'
  children: ReactNode
}) {
  const styles = {
    error: 'border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300',
    ok: 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300',
    wait: 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300',
    info: 'border-line bg-soft text-ink',
  }[kind]
  const label = { error: 'Error', ok: 'Done', wait: 'Waiting', info: 'Note' }[kind]
  return (
    <div className={`rounded-2xl border px-4 py-3 text-sm leading-6 ${styles}`}>
      <span className="font-semibold">{label}. </span>
      {children}
    </div>
  )
}

const toneClass = {
  ok: 'bg-emerald-50 text-emerald-800 ring-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-300 dark:ring-emerald-800',
  bad: 'bg-rose-50 text-rose-800 ring-rose-200 dark:bg-rose-950/50 dark:text-rose-300 dark:ring-rose-800',
  warn: 'bg-amber-50 text-amber-900 ring-amber-200 dark:bg-amber-950/50 dark:text-amber-300 dark:ring-amber-800',
  info: 'bg-sky-50 text-sky-800 ring-sky-200 dark:bg-sky-950/50 dark:text-sky-300 dark:ring-sky-800',
  lab: 'bg-indigo-50 text-indigo-800 ring-indigo-200 dark:bg-indigo-950/50 dark:text-indigo-300 dark:ring-indigo-800',
  enroll: 'bg-violet-50 text-violet-800 ring-violet-200 dark:bg-violet-950/50 dark:text-violet-300 dark:ring-violet-800',
  muted: 'bg-soft text-muted ring-line',
}

const statusTone: Record<string, keyof typeof toneClass> = {
  Active: 'ok',
  present: 'ok',
  match: 'ok',
  live: 'ok',
  enrolled: 'ok',
  checked_out: 'ok',
  failed: 'bad',
  no_match: 'bad',
  spoof: 'bad',
  blocked: 'bad',
  deactivated: 'bad',
  Inactive: 'muted',
  'No face': 'warn',
  late: 'warn',
  excused: 'ok',
  absent: 'warn',
  hr: 'info',
  reactivated: 'ok',
  early_leave: 'warn',
  pin: 'info',
  'No login': 'info',
  login_set: 'info',
  updated: 'info',
  kiosk: 'info',
  web: 'muted',
  employee: 'info',
  attendance: 'info',
  enroll: 'enroll',
  identify: 'lab',
  verify: 'lab',
  liveness: 'warn',
  person: 'muted',
}

function prettyStatus(status: string) {
  const labels: Record<string, string> = {
    present: 'Present',
    failed: 'Failed',
    match: 'Match',
    no_match: 'No match',
    live: 'Live',
    spoof: 'Not live',
    blocked: 'Blocked',
    enrolled: 'Enrolled',
    checked_out: 'Checked out',
    deactivated: 'Deactivated',
    login_set: 'Login set',
    updated: 'Updated',
    late: 'Late',
    excused: 'Excused',
    absent: 'Absent',
    hr: 'HR edit',
    reactivated: 'Reactivated',
    early_leave: 'Left early',
    pin: 'PIN',
    attendance: 'Attendance',
    enroll: 'Enroll',
    identify: 'Identify',
    verify: 'Verify',
    liveness: 'Liveness',
    person: 'People',
    kiosk: 'Kiosk',
    web: 'Web',
    employee: 'App',
  }
  return labels[status] ?? status.replace(/_/g, ' ')
}

export function StatusBadge({ status }: { status: string }) {
  const tone = statusTone[status] ?? statusTone[status.toLowerCase()] ?? 'muted'
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ring-1 ring-inset ${toneClass[tone]}`}
    >
      {prettyStatus(status)}
    </span>
  )
}

export function KindBadge({ kind }: { kind: string }) {
  return <StatusBadge status={kind} />
}

export function scoreClass(similarity: number | null | undefined, ok?: boolean) {
  if (similarity == null) return 'text-muted'
  if (ok === true) return 'text-emerald-600 dark:text-emerald-400'
  if (ok === false) return 'text-rose-600 dark:text-rose-400'
  return 'text-ink'
}

export { EmptyState, MetricSkeleton, Skeleton, TableSkeleton } from './feedback'

export function LabTabs() {
  const items = [
    { to: '/lab', label: 'Accuracy' },
    { to: '/verify', label: 'Verify' },
    { to: '/identify', label: 'Identify' },
    { to: '/liveness', label: 'Liveness' },
  ]
  return (
    <div className="mb-6 flex flex-wrap gap-1 rounded-2xl bg-soft p-1">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/lab'}
          className={({ isActive }) =>
            `rounded-xl px-3 py-2 text-sm font-medium ${isActive ? 'bg-panel text-ink shadow-sm' : 'text-muted hover:text-ink'}`
          }
        >
          {item.label}
        </NavLink>
      ))}
    </div>
  )
}

export function Initials({ name, className = '' }: { name: string; className?: string }) {
  const parts = name.trim().split(/\s+/).slice(0, 2)
  const letters = parts.map((p) => p[0]?.toUpperCase() ?? '').join('') || '?'
  return (
    <div className={`grid h-9 w-9 shrink-0 place-items-center rounded-full bg-accent text-xs font-semibold text-accent-fg ${className}`}>
      {letters}
    </div>
  )
}

export function ThemeToggle({
  className = '',
  inverted = false,
  compact = false,
}: {
  className?: string
  inverted?: boolean
  compact?: boolean
}) {
  const { theme, toggle } = useTheme()
  const colors = inverted
    ? 'border-accent-fg/20 text-accent-fg hover:bg-white/10 dark:hover:bg-black/10'
    : 'border-line text-ink hover:bg-soft'
  return (
    <button
      type="button"
      onClick={toggle}
      className={`rounded-xl border px-3 py-2 text-sm font-medium ${colors} ${className}`}
      aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
    >
      {compact ? (
        theme === 'dark' ? (
          <IconSun className="mx-auto h-5 w-5" />
        ) : (
          <IconMoon className="mx-auto h-5 w-5" />
        )
      ) : theme === 'dark' ? (
        'Light'
      ) : (
        'Dark'
      )}
    </button>
  )
}
