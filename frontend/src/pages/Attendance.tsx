import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { AttendanceRecord, AuthConfig, Occurrence, OfficeSettings } from '../api/types'
import { ScanFrame } from '../components/ScanFrame'
import { Alert, Button, StatusBadge, cardClass, inputClass } from '../components/ui'
import { useAuth } from '../hooks/useAuth'
import { useWebcam } from '../hooks/useWebcam'
import { fenceOn, readCoords, runBlinkChallenge } from '../lib/helpers'
import { orgFrom, titleCase } from '../lib/org'

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

export function AttendancePage() {
  const { user, refresh, config } = useAuth()
  const org = orgFrom(config)
  const cam = useWebcam()
  const [today, setToday] = useState<AttendanceRecord | null>(null)
  const [sessions, setSessions] = useState<Occurrence[]>([])
  const [occurrenceId, setOccurrenceId] = useState<number | undefined>(undefined)
  const [result, setResult] = useState<AttendanceRecord | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [hint, setHint] = useState('Look at the camera, then check in.')
  const [showDetails, setShowDetails] = useState(false)
  const [cfg, setCfg] = useState<AuthConfig | null>(null)
  const [office, setOffice] = useState<OfficeSettings | null>(null)
  const faceReady = Boolean(user?.person?.face_ready)
  const active = user?.person?.is_active !== false
  const firstName = (user?.person?.name ?? user?.username ?? 'there').split(' ')[0]
  const tone = result?.decision === 'present' ? 'ok' : error ? 'bad' : 'idle'
  const mustBeOnSite = fenceOn(office) || Boolean(cfg?.geofence)

  useEffect(() => {
    const id = window.setInterval(() => {
      void refresh().catch(() => undefined)
    }, 4000)
    void refresh().catch(() => undefined)
    void api.authConfig().then(setCfg).catch(() => undefined)
    void api.officeSettings().then(setOffice).catch(() => undefined)
    void api.todayAttendance().then(setToday).catch(() => undefined)
    if (org.needsSchedule) {
      void api
        .mySchedule()
        .then((rows) => {
          setSessions(rows)
          const open = rows.find((r) => r.open && !r.already_marked) ?? rows.find((r) => r.open) ?? rows[0]
          if (open) setOccurrenceId(open.id)
        })
        .catch(() => undefined)
    }
    return () => window.clearInterval(id)
  }, [refresh, org.needsSchedule])

  async function liveIfNeeded() {
    if (cfg?.require_liveness === false) return undefined
    return runBlinkChallenge(cam, setHint)
  }

  async function coordsIfNeeded() {
    if (!fenceOn(office) && !cfg?.geofence) return undefined
    setHint('Checking that you are at the office…')
    return readCoords(true)
  }

  async function punch() {
    setBusy(true)
    setError(null)
    try {
      if (!cam.ready) await cam.start()
      const challengeId = await liveIfNeeded()
      setHint('Matching your face…')
      const shot = await cam.capture()
      const file = new File([shot], 'selfie.jpg', { type: 'image/jpeg' })
      const rec = await api.checkIn(file, challengeId, await coordsIfNeeded(), {
        occurrenceId,
      })
      setResult(rec)
      setToday(rec.decision === 'present' ? rec : today)
      setHint(rec.decision === 'present' ? 'You are marked present.' : 'That photo did not match. Try better light.')
      if (org.needsSchedule) {
        const rows = await api.mySchedule()
        setSessions(rows)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Check-in failed. Try again.')
    } finally {
      setBusy(false)
    }
  }

  async function doCheckOut(withFace: boolean) {
    setBusy(true)
    setError(null)
    try {
      if (!withFace) {
        const rec = await api.checkOut()
        setToday(rec)
        setResult(rec)
        return
      }
      if (!cam.ready) await cam.start()
      const challengeId = await liveIfNeeded()
      const shot = await cam.capture()
      const rec = await api.checkOut(new File([shot], 'out.jpg', { type: 'image/jpeg' }), challengeId)
      setToday(rec)
      setResult(rec)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Check-out failed')
    } finally {
      setBusy(false)
    }
  }

  const present = today?.decision === 'present'
  const sessionMarked = sessions.find((s) => s.id === occurrenceId)?.already_marked
  const shownPresent = org.needsSchedule ? Boolean(sessionMarked || (present && today?.occurrence_id === occurrenceId)) : present

  return (
    <div className="max-w-xl">
      <p className="text-sm font-medium text-ink">
        {greeting()}, {firstName}
      </p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-ink">
        {org.kernel === 'session' ? 'Mark this session' : org.kernel === 'visit' ? 'Check in for this visit' : 'Check in for today'}
      </h1>
      <p className="mt-2 text-sm leading-6 text-muted">
        {org.allowCheckout
          ? 'One face check marks you present. You can check out with a second look when you leave.'
          : org.kernel === 'session'
            ? 'Pick the class that is open, then mark yourself present with a face check.'
            : 'One face check marks you present for the day.'}
      </p>
      {config?.org_name || user?.org_name ? (
        <p className="mt-2 text-sm text-ink">
          {config?.default_site?.name || config?.org_name || user?.org_name}
          {config?.org_slug || user?.org_slug ? (
            <span className="ml-2 font-mono text-xs text-muted">{config?.org_slug || user?.org_slug}</span>
          ) : null}
        </p>
      ) : null}
      {mustBeOnSite ? (
        <div className="mt-4">
          <Alert kind="info">
            Attendance only counts at{' '}
            {cfg?.default_site?.name || office?.office_name || cfg?.office_name || cfg?.org_name || 'the office'}
            {cfg?.default_site?.radius_m
              ? ` (within ${Math.round(cfg.default_site.radius_m)} m)`
              : office?.geo_radius_m
                ? ` (within ${Math.round(office.geo_radius_m)} m)`
                : ''}
            . Allow location when asked.
          </Alert>
        </div>
      ) : null}

      <ol className="mt-6 grid grid-cols-3 gap-2 text-center text-xs font-medium">
        {[
          { ok: true, label: 'Signed in' },
          { ok: faceReady, label: 'Photo ready' },
          { ok: shownPresent, label: 'Present' },
        ].map((s) => (
          <li
            key={s.label}
            className={`rounded-2xl px-2 py-3 ${s.ok ? 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300' : 'bg-panel text-muted ring-1 ring-line'}`}
          >
            {s.label}
          </li>
        ))}
      </ol>

      <div className="mt-6 space-y-4">
        {!active ? (
          <Alert kind="error">This account is deactivated. Please talk to {org.staff}.</Alert>
        ) : !faceReady ? (
          <Alert kind="wait">
            {org.staff} still needs to add your photo. Leave this page open — it updates by itself when you are ready to check
            in.
          </Alert>
        ) : shownPresent && today && !org.needsSchedule ? (
          <div className={`${cardClass} p-6`}>
            <div className="flex flex-wrap items-center gap-2 text-lg font-semibold text-emerald-700 dark:text-emerald-400">
              You are in · {formatTime(today.created_at)}
              <StatusBadge status="present" />
              {today.late && org.trackLate ? <StatusBadge status="late" /> : null}
              {today.checked_out_at ? <StatusBadge status="checked_out" /> : null}
              {today.early_leave && org.trackEarlyLeave ? <StatusBadge status="early_leave" /> : null}
            </div>
            {today.checked_out_at ? (
              <p className="mt-2 text-sm text-muted">Checked out at {formatTime(today.checked_out_at)}. See you tomorrow.</p>
            ) : org.allowCheckout ? (
              <>
                <p className="mt-2 text-sm text-muted">Have a good day. Confirm with a face check when you leave, or skip if the camera is down.</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button disabled={busy} onClick={() => void doCheckOut(true)}>
                    Check out with face
                  </Button>
                  <Button variant="secondary" disabled={busy} onClick={() => void doCheckOut(false)}>
                    Check out without camera
                  </Button>
                </div>
              </>
            ) : (
              <p className="mt-2 text-sm text-muted">You are marked present for today.</p>
            )}
          </div>
        ) : (
          <div className={`${cardClass} overflow-hidden`}>
            <div className="relative">
              <video
                ref={cam.videoRef}
                className="w-full aspect-[4/3] bg-black object-cover"
                playsInline
                muted
              />
              {cam.ready ? <ScanFrame active={busy} tone={tone} /> : null}
            </div>
            <div className="p-5">
              {org.needsSchedule && sessions.length > 0 ? (
                <label className="mb-3 block text-sm font-medium text-ink">
                  {titleCase(org.group)}
                  <select
                    className={`mt-1 ${inputClass}`}
                    value={occurrenceId ?? ''}
                    onChange={(e) => setOccurrenceId(e.target.value ? Number(e.target.value) : undefined)}
                  >
                    {sessions.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.title} · {s.start}–{s.end}
                        {s.already_marked ? ' (marked)' : s.open ? ' (open)' : ''}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              <p className="text-sm text-muted">{hint}</p>
              {cam.error ? (
                <div className="mt-3 rounded-2xl border border-line bg-soft p-4 text-sm">
                  <div className="font-medium">Camera is blocked</div>
                  <p className="mt-1 text-muted">Allow the camera in the browser, or ask staff to check you in at the kiosk with your {org.id.toLowerCase()}.</p>
                </div>
              ) : null}
              <div className="mt-4">
                {!cam.ready ? (
                  <Button className="w-full py-3.5 text-base" onClick={() => void cam.start()}>
                    Allow camera
                  </Button>
                ) : (
                  <Button disabled={busy} className="w-full py-3.5 text-base" onClick={() => void punch()}>
                    {busy
                      ? 'Checking…'
                      : cfg?.require_liveness === false
                        ? 'Mark me present'
                        : 'Wait, blink, then mark present'}
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}

        {error ? <Alert kind="error">{error}</Alert> : null}
        {result && result.decision !== 'present' && result.decision !== 'checked_out' ? (
          <div className={`${cardClass} p-5 ring-1 ring-rose-300 dark:ring-rose-800`}>
            <div className="font-medium text-rose-700 dark:text-rose-400">We could not match that photo.</div>
            <p className="mt-1 text-sm text-muted">Face the oval, use even light, and try once more.</p>
            <button type="button" className="mt-3 text-xs text-muted" onClick={() => setShowDetails((v) => !v)}>
              {showDetails ? 'Hide technical details' : 'Show technical details'}
            </button>
            {showDetails ? (
              <p className="mt-2 text-xs text-muted mono">
                score {result.similarity ?? '—'} · need {result.threshold ?? '—'}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}
