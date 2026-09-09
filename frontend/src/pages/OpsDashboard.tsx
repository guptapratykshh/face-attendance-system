import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Holiday, OfficeSettings, OpsSummary, OrgPreset, SpoofAlert } from '../api/types'
import { AttendanceEdit } from '../components/AttendanceEdit'
import { MetricCard } from '../components/MetricCard'
import { Alert, Button, EmptyState, Initials, MetricSkeleton, PageHeader, StatusBadge, cardClass, inputClass } from '../components/ui'
import { useAuth } from '../hooks/useAuth'
import { useToast } from '../hooks/useToast'
import { roleOf } from '../api/types'
import { fenceOn, readCoords } from '../lib/helpers'
import { orgFrom, titleCase } from '../lib/org'

function CountUp({ value }: { value: number }) {
  const [shown, setShown] = useState(0)
  const prev = useRef(0)
  useEffect(() => {
    const from = prev.current
    prev.current = value
    const start = performance.now()
    let frame = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / 400)
      setShown(Math.round(from + (value - from) * t))
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [value])
  return <>{shown}</>
}

function SpoofPhoto({ id, name }: { id: number; name: string }) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    let url: string | null = null
    let cancelled = false
    void api
      .spoofAlertImage(id)
      .then((blob) => {
        if (cancelled) return
        url = URL.createObjectURL(blob)
        setSrc(url)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [id])
  if (!src) {
    return <div className="aspect-[4/3] w-full animate-pulse rounded-xl bg-soft" />
  }
  return <img src={src} alt={`Blocked check-in for ${name}`} className="aspect-[4/3] w-full rounded-xl object-cover" />
}

export function OpsDashboardPage() {
  const { user, refreshConfig, config } = useAuth()
  const toast = useToast()
  const [summary, setSummary] = useState<OpsSummary | null>(null)
  const [office, setOffice] = useState<OfficeSettings | null>(null)
  const [presets, setPresets] = useState<OrgPreset[]>([])
  const org = orgFrom(office ?? undefined)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [holidays, setHolidays] = useState<Holiday[]>([])
  const [holidayForm, setHolidayForm] = useState({ day: '', name: '' })
  const [alerts, setAlerts] = useState<SpoofAlert[]>([])
  const admin = roleOf(user) === 'admin'
  const canEditOffice = admin || roleOf(user) === 'hr'

  async function refresh() {
    const [s, o] = await Promise.all([api.opsSummary(), api.officeSettings()])
    setSummary(s)
    setOffice(o)
    try {
      setPresets(await api.orgPresets())
    } catch {
      setPresets([])
    }
    try {
      setAlerts(await api.spoofAlerts())
    } catch {
      setAlerts([])
    }
    try {
      setHolidays(await api.listHolidays())
    } catch {
      setHolidays([])
    }
  }

  useEffect(() => {
    refresh()
      .catch((e) => setError(e.detail ?? String(e)))
      .finally(() => setLoading(false))
    const id = window.setInterval(() => {
      refresh().catch(() => undefined)
    }, 12000)
    return () => window.clearInterval(id)
  }, [])

  async function saveHours() {
    if (!office) return
    setSaving(true)
    try {
      setOffice(await api.updateOfficeSettings(office))
      await refreshConfig()
      await refresh()
      toast.push('ok', 'Office settings saved')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save office hours')
    } finally {
      setSaving(false)
    }
  }

  async function pinHere() {
    if (!office) return
    try {
      const here = await readCoords(true)
      if (!here) return
      const next = {
        ...office,
        geo_lat: Number(here.lat.toFixed(6)),
        geo_lng: Number(here.lng.toFixed(6)),
        geo_radius_m: office.geo_radius_m && office.geo_radius_m > 0 ? office.geo_radius_m : 150,
      }
      setOffice(next)
      setOffice(await api.updateOfficeSettings(next))
      toast.push('ok', 'Office location saved. Check-in now requires this area.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not read this device location')
    }
  }

  async function clearFence() {
    if (!office) return
    const next = { ...office, geo_lat: null, geo_lng: null, geo_radius_m: null }
    setOffice(await api.updateOfficeSettings(next))
    toast.push('ok', 'Location lock turned off')
  }

  async function override(personId: number, decision: string, note?: string) {
    try {
      await api.manualAttendance({ person_id: personId, decision, note })
      toast.push('ok', decision === 'present' ? 'Marked present' : `Set to ${decision}`)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update attendance')
    }
  }

  async function punish(personId: number, name: string) {
    if (!window.confirm(`Deactivate ${name}? They will not be able to check in.`)) return
    try {
      await api.deletePerson(personId)
      toast.push('ok', `${name} deactivated`)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not deactivate')
    }
  }

  async function addHoliday(e: FormEvent) {
    e.preventDefault()
    try {
      await api.createHoliday(holidayForm)
      setHolidayForm({ day: '', name: '' })
      toast.push('ok', 'Holiday added')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add holiday')
    }
  }

  const weekday = new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })
  const expected = (summary?.present_today ?? 0) + (summary?.absent_today ?? 0)
  const pct = expected ? Math.round(((summary?.present_today ?? 0) / expected) * 100) : 0

  return (
    <div>
      <PageHeader
        eyebrow="Overview"
        title={org.kernel === 'session' ? 'Today’s sessions' : org.kernel === 'visit' ? 'Visits today' : 'Who is in today'}
        subtitle={`${config?.org_name ? `${config.org_name} · ` : ''}${config?.org_slug ? `${config.org_slug} · ` : ''}${weekday}${summary ? ` · ${summary.tz}` : ''}. ${titleCase(org.subjectPlural)} · ${org.orgType.replace('_', ' ')}.`}
        actions={
          <>
            <Link to="/board" className="inline-flex items-center rounded-xl border border-line bg-panel px-4 py-2.5 text-sm font-semibold text-ink">
              TV entrance screen
            </Link>
            <Link to="/people" className="inline-flex items-center rounded-xl bg-accent text-accent-fg px-4 py-2.5 text-sm font-semibold">
              {titleCase(org.subjectPlural)}
            </Link>
            <Link
              to="/enroll"
              className="inline-flex items-center rounded-xl border border-line bg-panel px-4 py-2.5 text-sm font-semibold text-ink"
            >
              Add faces{summary?.pending_faces ? ` (${summary.pending_faces})` : ''}
            </Link>
          </>
        }
      />
      {error ? <Alert kind="error">{error}</Alert> : null}

      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <MetricSkeleton key={i} />
          ))}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <MetricCard label="Present" value={summary ? <CountUp value={summary.present_today} /> : '—'} hint={org.kernel === 'visit' ? 'visits' : 'checked in'} tone="ok" />
            {org.trackLate ? (
              <MetricCard label="Late" value={String(summary?.late_today ?? '—')} hint="after start + grace" tone="warn" />
            ) : null}
            {org.usesRoster ? (
              <MetricCard label="Not in yet" value={String(summary?.absent_today ?? '—')} hint="have a face on file" />
            ) : (
              <MetricCard label="Visits" value={String(summary?.visits_today ?? '—')} hint="check-ins today" />
            )}
            <MetricCard label="Failed checks" value={String(summary?.failed_today ?? '—')} hint="face did not match" tone="bad" />
          </div>
          <div className="mt-3 grid grid-cols-2 lg:grid-cols-4 gap-3">
            <MetricCard
              label="Photo / video blocked"
              value={String(summary?.spoof_today ?? alerts.length)}
              hint={`sent to ${org.staff} and admin`}
              tone="bad"
            />
            <MetricCard label="Waiting for a photo" value={String(summary?.pending_faces ?? '—')} hint="cannot check in yet" tone="warn" />
            {org.allowCheckout ? (
              <MetricCard label="Still out" value={String(summary?.still_out ?? '—')} hint="checked in, not out" />
            ) : null}
            <MetricCard label="No login yet" value={String(summary?.awaiting_login ?? '—')} hint="need a username" />
            <MetricCard label="Workday" value={summary?.workday === false ? 'Off' : 'Yes'} hint="weekends and holidays skip absent" />
          </div>
          <div className={`mt-3 ${cardClass} p-5`}>
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">In vs expected</span>
              <span className="mono text-muted">{pct}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-soft">
              <div className="h-full bg-emerald-500" style={{ width: `${pct}%` }} />
            </div>
          </div>
        </>
      )}

      {alerts.length > 0 ? (
        <section className={`mt-8 ${cardClass} p-5 ring-1 ring-rose-200 dark:ring-rose-900`}>
          <h2 className="text-sm font-semibold text-ink">Photo or video check-in blocked</h2>
          <p className="mt-1 text-sm text-muted">
            Someone tried to mark attendance with a still photo or a screen. They were not marked present. Review the
            captured frame and follow up with the person.
          </p>
          <ul className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {alerts.map((alert) => (
              <li key={alert.id} className="rounded-2xl border border-line bg-soft/40 p-3">
                <SpoofPhoto id={alert.id} name={alert.person_name || alert.actor_username || 'Unknown'} />
                <div className="mt-3 flex items-start justify-between gap-2">
                  <div>
                    <div className="font-semibold text-ink">{alert.person_name || 'Unknown face'}</div>
                    <div className="text-xs text-muted">
                      {alert.actor_username ? `Account ${alert.actor_username}` : 'Kiosk'} ·{' '}
                      {alert.source === 'kiosk' ? 'Entrance kiosk' : 'Phone check-in'}
                    </div>
                    <div className="mt-1 text-xs text-muted">{new Date(alert.created_at).toLocaleString()}</div>
                    {alert.reason ? <p className="mt-2 text-xs text-muted">{alert.reason}</p> : null}
                  </div>
                  <StatusBadge status="blocked" />
                </div>
                {alert.person_id ? (
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <Link to={`/people/${alert.person_id}`} className="font-medium text-ink underline">
                      Open person
                    </Link>
                    <button
                      type="button"
                      className="font-medium text-emerald-700 hover:underline dark:text-emerald-400"
                      onClick={() => void override(alert.person_id!, 'present', 'HR override after blocked photo/video')}
                    >
                      Mark present
                    </button>
                    <button
                      type="button"
                      className="font-medium text-ink hover:underline"
                      onClick={() => void override(alert.person_id!, 'excused', 'HR excused after blocked photo/video')}
                    >
                      Mark excused
                    </button>
                    <button
                      type="button"
                      className="font-medium text-rose-600 hover:underline dark:text-rose-400"
                      onClick={() => void punish(alert.person_id!, alert.person_name || 'this person')}
                    >
                      Deactivate
                    </button>
                  </div>
                ) : null}
                {!alert.seen ? (
                  <button
                    type="button"
                    className="mt-2 block text-xs text-muted hover:text-ink"
                    onClick={() =>
                      void api.markSpoofSeen(alert.id).then((next) => {
                        setAlerts((rows) => rows.map((row) => (row.id === next.id ? next : row)))
                        toast.push('ok', 'Marked as reviewed')
                      })
                    }
                  >
                    Mark reviewed
                  </button>
                ) : (
                  <p className="mt-2 text-xs text-muted">Reviewed</p>
                )}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {summary?.sessions_today && summary.sessions_today.length > 0 ? (
        <section className={`mt-8 ${cardClass} p-5`}>
          <h2 className="text-sm font-semibold text-ink">
            {org.kernel === 'shift' ? 'Shifts today' : org.kernel === 'visit' ? 'Events today' : 'Sessions today'}
          </h2>
          <ul className="mt-3 divide-y divide-line">
            {summary.sessions_today.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                <div>
                  <div className="font-medium text-ink">{s.title}</div>
                  <div className="text-xs text-muted">
                    {s.start}–{s.end}
                    {s.room ? ` · ${s.room}` : ''}
                    {s.open ? ' · open now' : ''}
                  </div>
                </div>
                <div className="text-sm text-ink">
                  {s.present}/{s.expected || '—'} present
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {canEditOffice && office ? (
        <section className={`mt-8 ${cardClass} p-5`}>
          <h2 className="text-sm font-semibold text-ink">{org.allowCheckout ? 'Hours' : 'Day start'}</h2>
          <p className="mt-1 text-sm text-muted">
            {org.trackLate ? 'Used to mark late arrivals' : 'Used for the local calendar day'}
            {org.trackEarlyLeave ? ' and early leave.' : '.'}
          </p>
          <div className="mt-4 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <label className="text-xs font-medium text-muted" htmlFor="office-tz">
              Timezone
              <input id="office-tz" className={`mt-1 ${inputClass}`} value={office.tz} onChange={(e) => setOffice({ ...office, tz: e.target.value })} />
            </label>
            <label className="text-xs font-medium text-muted" htmlFor="office-name">
              Office name
              <input id="office-name" className={`mt-1 ${inputClass}`} value={office.office_name ?? ''} onChange={(e) => setOffice({ ...office, office_name: e.target.value })} />
            </label>
            <label className="text-xs font-medium text-muted" htmlFor="office-grace">
              Grace (minutes)
              <input
                id="office-grace"
                type="number"
                className={`mt-1 ${inputClass}`}
                value={office.late_grace_minutes}
                onChange={(e) => setOffice({ ...office, late_grace_minutes: Number(e.target.value) })}
              />
            </label>
            <label className="text-xs font-medium text-muted" htmlFor="office-weekend">
              Weekend (ISO days)
              <input id="office-weekend" className={`mt-1 ${inputClass}`} value={office.weekend ?? '6,7'} onChange={(e) => setOffice({ ...office, weekend: e.target.value })} />
            </label>
            <label className="text-xs font-medium text-muted" htmlFor="office-start">
              Start
              <input id="office-start" className={`mt-1 ${inputClass}`} value={office.work_start} onChange={(e) => setOffice({ ...office, work_start: e.target.value })} />
            </label>
            <label className="text-xs font-medium text-muted" htmlFor="office-end">
              End
              <input id="office-end" className={`mt-1 ${inputClass}`} value={office.work_end} onChange={(e) => setOffice({ ...office, work_end: e.target.value })} />
            </label>
            <label className="flex items-center gap-2 text-sm text-ink sm:col-span-2">
              <input
                type="checkbox"
                checked={Boolean(office.notify_late)}
                onChange={(e) => setOffice({ ...office, notify_late: e.target.checked })}
              />
              Email when late, absent after grace, or 3 failed checks
            </label>
            <label className="text-xs font-medium text-muted sm:col-span-2" htmlFor="office-type">
              Organization type
              <select
                id="office-type"
                className={`mt-1 ${inputClass}`}
                value={office.org_type || 'workplace'}
                onChange={(e) => setOffice({ ...office, org_type: e.target.value })}
              >
                {(presets.length ? presets : [{ org_type: office.org_type || 'workplace', title: office.org_type || 'workplace' }]).map(
                  (p) => (
                    <option key={p.org_type} value={p.org_type}>
                      {p.title}
                    </option>
                  ),
                )}
              </select>
              <span className="mt-1 block font-normal text-amber-800 dark:text-amber-300">
                Changing type reapplies attendance rules for this organization only.
              </span>
            </label>
            <label className="flex items-center gap-2 text-sm text-ink sm:col-span-2">
              <input
                type="checkbox"
                checked={Boolean(office.allow_kiosk_pin)}
                onChange={(e) => setOffice({ ...office, allow_kiosk_pin: e.target.checked })}
              />
              Allow kiosk check-in with {org.id} (skips the face — keep off unless the camera is down)
            </label>
          </div>
          <Button disabled={saving} className="mt-4" onClick={() => void saveHours()}>
            Save hours
          </Button>
        </section>
      ) : null}

      {canEditOffice && office ? (
        <section className={`mt-6 ${cardClass} p-5`}>
          <h2 className="text-sm font-semibold text-ink">Office location lock</h2>
          <p className="mt-1 text-sm text-muted">
            Stand at the workplace, save this spot, and pick a radius. Employees can mark attendance only inside that
            circle. The entrance kiosk still works without GPS.
          </p>
          {fenceOn(office) ? (
            <p className="mt-3 text-sm text-emerald-700 dark:text-emerald-400">
              Locked to {office.office_name || 'the office'} · {office.geo_lat?.toFixed(5)}, {office.geo_lng?.toFixed(5)} ·{' '}
              {Math.round(office.geo_radius_m ?? 0)} m
            </p>
          ) : (
            <p className="mt-3 text-sm text-amber-800 dark:text-amber-300">Not set — people can check in from anywhere.</p>
          )}
          <div className="mt-4 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <label className="text-xs font-medium text-muted" htmlFor="office-lat">
              Latitude
              <input id="office-lat" className={`mt-1 ${inputClass}`} value={office.geo_lat ?? ''} onChange={(e) => setOffice({ ...office, geo_lat: e.target.value === '' ? null : Number(e.target.value) })} />
            </label>
            <label className="text-xs font-medium text-muted" htmlFor="office-lng">
              Longitude
              <input id="office-lng" className={`mt-1 ${inputClass}`} value={office.geo_lng ?? ''} onChange={(e) => setOffice({ ...office, geo_lng: e.target.value === '' ? null : Number(e.target.value) })} />
            </label>
            <label className="text-xs font-medium text-muted" htmlFor="office-radius">
              Radius (metres)
              <input id="office-radius" type="number" min={20} max={5000} className={`mt-1 ${inputClass}`} value={office.geo_radius_m ?? ''} onChange={(e) => setOffice({ ...office, geo_radius_m: e.target.value === '' ? null : Number(e.target.value) })} />
            </label>
            <div className="flex flex-wrap items-end gap-2">
              {[['50 m', 50], ['150 m', 150], ['300 m', 300], ['500 m', 500]].map(([label, metres]) => (
                <button
                  key={String(metres)}
                  type="button"
                  className="rounded-xl border border-line px-3 py-2 text-xs font-medium hover:bg-soft"
                  onClick={() => setOffice({ ...office, geo_radius_m: Number(metres) })}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button onClick={() => void pinHere()}>Use this device as the office</Button>
            <Button variant="secondary" disabled={saving} onClick={() => void saveHours()}>
              Save location
            </Button>
            {fenceOn(office) ? (
              <Button variant="ghost" onClick={() => void clearFence()}>
                Turn off lock
              </Button>
            ) : null}
          </div>
        </section>
      ) : null}

      {admin ? (
        <section className={`mt-6 ${cardClass} p-5`}>
          <h2 className="text-sm font-semibold text-ink">Holidays</h2>
          <p className="mt-1 text-sm text-muted">Expected attendance skips these days.</p>
          <form onSubmit={(e) => void addHoliday(e)} className="mt-4 grid gap-3 sm:grid-cols-3">
            <input type="date" className={inputClass} value={holidayForm.day} onChange={(e) => setHolidayForm((f) => ({ ...f, day: e.target.value }))} required />
            <input className={inputClass} placeholder="Name" value={holidayForm.name} onChange={(e) => setHolidayForm((f) => ({ ...f, name: e.target.value }))} required />
            <Button type="submit">Add holiday</Button>
          </form>
          <ul className="mt-4 space-y-2">
            {holidays.map((h) => (
              <li key={h.id} className="flex items-center justify-between text-sm">
                <span>{h.day} · {h.name}</span>
                <button
                  type="button"
                  className="text-rose-600 dark:text-rose-400"
                  onClick={() =>
                    void api.deleteHoliday(h.id).then(() => {
                      toast.push('ok', 'Holiday removed')
                      return refresh()
                    })
                  }
                >
                  Remove
                </button>
              </li>
            ))}
            {holidays.length === 0 ? <li className="text-sm text-muted">None yet.</li> : null}
          </ul>
        </section>
      ) : null}

      {(summary?.consecutive_absent?.length ?? 0) > 0 && org.usesRoster ? (
        <section className="mt-8">
          <h2 className="text-lg font-semibold text-ink">Consecutive absences</h2>
          <div className="mt-3 space-y-2">
            {(summary?.consecutive_absent ?? []).map((s) => (
              <div key={s.person_id} className={`${cardClass} flex flex-wrap items-center justify-between gap-3 p-3`}>
                <Link to={`/people/${s.person_id}`} className="hover:underline">
                  <span className="font-medium">{s.person_name}</span>
                  <span className="ml-2 text-sm text-muted">{s.days} days</span>
                </Link>
                <div className="flex flex-wrap gap-2 text-xs">
                  <button type="button" className="rounded-lg border border-line px-2 py-1 font-medium hover:bg-soft" onClick={() => void override(s.person_id, 'present')}>
                    Mark present
                  </button>
                  <button type="button" className="rounded-lg border border-line px-2 py-1 font-medium hover:bg-soft" onClick={() => void override(s.person_id, 'excused')}>
                    Excused
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {(summary?.waiting?.length ?? 0) > 0 && org.usesRoster ? (
        <section className="mt-8">
          <h2 className="text-lg font-semibold text-ink">Not in yet</h2>
          <p className="mt-1 text-sm text-muted">{org.staff} and admin can mark present, absent, or excused without a face check.</p>
          <div className="mt-3 space-y-2">
            {(summary?.waiting ?? []).map((p) => (
              <div key={p.person_id} className={`${cardClass} flex flex-wrap items-center justify-between gap-3 p-3`}>
                <Link to={`/people/${p.person_id}`} className="font-medium hover:underline">
                  {p.person_name}
                </Link>
                <div className="flex flex-wrap gap-2 text-xs">
                  <button type="button" className="rounded-lg border border-line px-2 py-1 font-medium hover:bg-soft" onClick={() => void override(p.person_id, 'present')}>
                    Mark present
                  </button>
                  <button type="button" className="rounded-lg border border-line px-2 py-1 font-medium hover:bg-soft" onClick={() => void override(p.person_id, 'absent')}>
                    Absent
                  </button>
                  <button type="button" className="rounded-lg border border-line px-2 py-1 font-medium hover:bg-soft" onClick={() => void override(p.person_id, 'excused')}>
                    Excused
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <h2 className="mt-10 text-lg font-semibold text-ink">Latest check-ins</h2>
      <div className="mt-3 space-y-2">
        {(summary?.recent ?? []).map((r) => (
          <div key={r.id} className={`${cardClass} flex flex-wrap items-center gap-3 p-3`}>
            <Link to={`/people/${r.person_id}`} className="flex min-w-0 flex-1 items-center gap-3 hover:underline">
              <Initials name={r.person_name} />
              <div className="min-w-0">
                <div className="truncate font-medium">{r.person_name}</div>
                <div className="text-xs text-muted mono">
                  {new Date(r.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            </Link>
            <AttendanceEdit row={r} onSaved={() => void refresh()} onError={setError} />
          </div>
        ))}
        {summary && summary.recent.length === 0 ? (
          <div className={cardClass}>
            <EmptyState title="No check-ins yet" body="When people mark present, they show up here." />
          </div>
        ) : null}
      </div>
    </div>
  )
}
