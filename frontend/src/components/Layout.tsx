import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useEffect, useState, type ComponentType, type SVGProps } from 'react'
import { api } from '../api/client'
import { canManagePeople, canUseLab, isPlatformAdmin, isStaff, roleOf } from '../api/types'
import { useAuth } from '../hooks/useAuth'
import { orgFrom, roleCaption, titleCase } from '../lib/org'
import {
  IconAccount,
  IconActivity,
  IconCheckIn,
  IconDays,
  IconFace,
  IconKiosk,
  IconLab,
  IconOrgs,
  IconPeople,
  IconReports,
  IconSignOut,
  IconStaff,
  IconToday,
  IconAssist,
} from './icons'
import { Initials, ThemeToggle } from './ui'
import { Logo } from './Logo'

type NavIcon = ComponentType<SVGProps<SVGSVGElement>>
type Link = { to: string; label: string; badge?: number; end?: boolean; icon: NavIcon }

function readCollapsed() {
  try {
    return globalThis.localStorage?.getItem('frs_sidebar') === 'collapsed'
  } catch {
    return false
  }
}

export function Layout() {
  const { user, logout, config, currentOrgId } = useAuth()
  const org = orgFrom(config)
  const location = useLocation()
  const [pending, setPending] = useState(0)
  const [spoofs, setSpoofs] = useState(0)
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const people = canManagePeople(user)
  const lab = canUseLab(user)
  const staff = isStaff(user)
  const role = roleOf(user)
  const admin = role === 'admin'
  const platform = isPlatformAdmin(user)
  const orgOpen = !platform || Boolean(currentOrgId)
  const labSection = ['/lab', '/verify', '/identify', '/liveness'].some((p) =>
    p === '/lab' ? location.pathname === '/lab' : location.pathname.startsWith(p),
  )

  useEffect(() => {
    if (!people || !orgOpen) return
    api
      .opsSummary()
      .then((s) => {
        setPending(s.pending_faces)
        setSpoofs(s.spoof_today ?? 0)
      })
      .catch(() => undefined)
  }, [people, orgOpen])

  useEffect(() => {
    try {
      globalThis.localStorage?.setItem('frs_sidebar', collapsed ? 'collapsed' : 'open')
    } catch {
      /* ignore */
    }
  }, [collapsed])

  const links: Link[] = []
  if (platform) {
    links.push({ to: '/orgs', label: orgOpen ? 'Switch organization' : 'Organizations', icon: IconOrgs })
  }
  if (people && orgOpen) {
    links.push(
      { to: '/', label: 'Today', icon: IconToday, end: true, badge: spoofs || undefined },
      { to: '/people', label: titleCase(org.subjectPlural), icon: IconPeople },
      { to: '/enroll', label: 'Add faces', icon: IconFace, badge: pending },
      { to: '/reports', label: 'Reports', icon: IconReports },
      { to: '/assist', label: 'Assist', icon: IconAssist },
    )
    if (org.needsSchedule) {
      links.push({ to: '/schedule', label: org.kernel === 'shift' ? 'Shifts' : org.kernel === 'visit' ? 'Events' : 'Timetable', icon: IconDays })
    }
  }
  if (staff && orgOpen) {
    links.push(
      { to: '/kiosk', label: 'Entrance kiosk', icon: IconKiosk },
      { to: '/events', label: 'Activity', icon: IconActivity },
    )
  }
  if (admin && orgOpen) {
    links.push({ to: '/staff', label: 'Staff', icon: IconStaff })
  }
  if (lab && orgOpen) {
    links.push({ to: '/lab', label: 'Recognition lab', icon: IconLab })
  }
  if (!staff && orgOpen) {
    links.push(
      { to: '/attendance', label: 'Check in', icon: IconCheckIn },
      { to: '/my-attendance', label: 'My days', icon: IconDays },
      { to: '/profile', label: 'Account', icon: IconAccount },
    )
  }

  const displayName = user?.person?.name ?? user?.username ?? 'You'
  const roleLabel = roleCaption(role, org)
  const chromeLess = location.pathname === '/kiosk' || location.pathname === '/board'

  if (chromeLess) {
    return <Outlet />
  }

  return (
    <div className="h-dvh md:flex overflow-hidden">
      <aside
        className={`hidden md:flex shrink-0 h-full flex-col border-r border-line bg-panel/90 py-5 backdrop-blur transition-[width] duration-200 ${
          collapsed ? 'w-[4.75rem] px-2' : 'w-64 px-4'
        }`}
      >
        <div className={`mb-5 flex items-center ${collapsed ? 'flex-col gap-3' : 'gap-2 px-1'}`}>
          <Logo
            compact={collapsed}
            subtitle={staff ? `${titleCase(org.subject)} attendance` : 'Your attendance'}
            className={collapsed ? 'justify-center' : 'flex-1 min-w-0'}
          />
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-muted hover:bg-soft hover:text-ink"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8">
              {collapsed ? (
                <path d="M7 4l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
              ) : (
                <path d="M13 4l-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
              )}
            </svg>
          </button>
        </div>
        <nav className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto overscroll-contain pr-0.5">
          {links.map((l) => {
            const labLink = l.to === '/lab'
            const ItemIcon = l.icon
            return (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end ?? l.to === '/'}
                title={l.badge ? `${l.label} (${l.badge})` : l.label}
                className={({ isActive }) =>
                  `rounded-xl py-2.5 text-sm font-medium flex items-center ${
                    collapsed ? 'justify-center px-0' : 'gap-3 px-3'
                  } ${
                    isActive || (labLink && labSection)
                      ? 'bg-accent text-accent-fg'
                      : 'text-muted hover:bg-soft hover:text-ink'
                  }`
                }
              >
                <span className="relative shrink-0">
                  <ItemIcon className="h-5 w-5" />
                  {collapsed && l.badge ? (
                    <span className="absolute -right-1 -top-1 h-1.5 w-1.5 rounded-full bg-current" />
                  ) : null}
                </span>
                {collapsed ? (
                  <span className="sr-only">{l.label}</span>
                ) : (
                  <>
                    <span className="flex-1 truncate">{l.label}</span>
                    {l.badge ? (
                      <span className="rounded-full bg-soft px-2 text-xs font-semibold text-ink">
                        {l.badge}
                      </span>
                    ) : null}
                  </>
                )}
              </NavLink>
            )
          })}
        </nav>
        <div className="mt-3 shrink-0 space-y-3">
          <ThemeToggle className={`w-full ${collapsed ? 'px-2 py-2.5' : ''}`} compact={collapsed} />
          <div className={`rounded-2xl bg-soft ${collapsed ? 'p-2' : 'p-3'}`}>
            {orgOpen && (config?.org_name || user?.org_name) && !collapsed ? (
              <div className="mb-3 min-w-0">
                <div className="truncate text-sm font-medium text-ink">{config?.org_name || user?.org_name}</div>
                {(config?.org_slug || user?.org_slug) ? (
                  <div className="truncate font-mono text-[11px] text-muted">
                    {config?.org_slug || user?.org_slug}
                  </div>
                ) : null}
              </div>
            ) : null}
            <div className={`flex items-center ${collapsed ? 'justify-center' : 'gap-3'}`}>
              <Initials name={displayName} />
              {collapsed ? null : (
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-ink">{displayName}</div>
                  <div className="text-xs text-muted">{roleLabel}</div>
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={logout}
              title="Sign out"
              className={`mt-3 w-full rounded-xl py-2 text-sm text-muted hover:bg-panel hover:text-ink ${
                collapsed ? 'grid place-items-center px-0' : 'flex items-center gap-2 px-3 text-left'
              }`}
            >
              <IconSignOut className="h-5 w-5" />
              {collapsed ? <span className="sr-only">Sign out</span> : 'Sign out'}
            </button>
          </div>
        </div>
      </aside>
      <main className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-5 md:px-10 md:py-8 pb-28 md:pb-10">
        <div className="mx-auto max-w-6xl">
          <div className="mb-5 flex items-center justify-between md:hidden">
            <div className="flex items-center gap-2">
              <Logo compact wordmark={false} />
              <div className="font-semibold text-ink">Sentinel</div>
            </div>
            <div className="flex items-center gap-3">
              <ThemeToggle />
              <button type="button" onClick={logout} className="text-sm font-medium text-ink">
                Sign out
              </button>
            </div>
          </div>
          <Outlet />
        </div>
      </main>
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-20 border-t border-line bg-panel/95 backdrop-blur">
        <div className="flex overflow-x-auto overscroll-contain">
          {links.map((l) => {
            const ItemIcon = l.icon
            return (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end ?? l.to === '/'}
                className={({ isActive }) =>
                  `flex-1 min-w-[4.5rem] px-2 py-2.5 text-center text-[11px] font-medium ${
                    isActive || (l.to === '/lab' && labSection) ? 'text-ink' : 'text-muted'
                  }`
                }
              >
                <ItemIcon className="mx-auto mb-1 h-5 w-5" />
                {l.label}
                {l.badge ? ` · ${l.badge}` : ''}
              </NavLink>
            )
          })}
        </div>
      </nav>
    </div>
  )
}
