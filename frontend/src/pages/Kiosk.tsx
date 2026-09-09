import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { AttendanceRecord, AuthConfig, Occurrence } from '../api/types'
import { BrandMark } from '../components/Logo'
import { ScanFrame } from '../components/ScanFrame'
import { StatusBadge, inputClass } from '../components/ui'
import { useAuth } from '../hooks/useAuth'
import { useWebcam } from '../hooks/useWebcam'
import { readCoords, runBlinkChallenge } from '../lib/helpers'
import { orgFrom } from '../lib/org'

function firstName(value: string | null | undefined) {
  return (value ?? 'there').split(' ')[0]
}

export function KioskPage() {
  const { logout, config } = useAuth()
  const org = orgFrom(config)
  const cam = useWebcam()
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<AttendanceRecord | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fullscreen, setFullscreen] = useState(false)
  const [pinMode, setPinMode] = useState(false)
  const [pin, setPin] = useState('')
  const [cfg, setCfg] = useState<AuthConfig | null>(null)
  const [hint, setHint] = useState('Face the oval, even light, one person.')
  const [sessions, setSessions] = useState<Occurrence[]>([])
  const [occurrenceId, setOccurrenceId] = useState<number | undefined>(undefined)
  const pinAllowed = Boolean(cfg?.allow_kiosk_pin)
  const usingPin = pinAllowed && pinMode
  const needsOccurrence = org.kernel === 'session' || org.kernel === 'shift'

  useEffect(() => {
    void cam.start()
  }, [cam.start])

  useEffect(() => {
    void api.authConfig().then(setCfg).catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!needsOccurrence) return
    const day = new Date().toISOString().slice(0, 10)
    void api
      .listOccurrences({ day })
      .then((rows) => {
        setSessions(rows)
        const open = rows.find((r) => r.open) ?? rows[0]
        if (open) setOccurrenceId(open.id)
      })
      .catch(() => undefined)
  }, [needsOccurrence])

  useEffect(() => {
    if (!result && !error) return
    const id = window.setTimeout(() => {
      setResult(null)
      setError(null)
      setHint('Face the oval, even light, one person.')
    }, 5000)
    return () => window.clearTimeout(id)
  }, [result, error])

  async function punch() {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      if (!cam.ready) await cam.start()
      const coords = await readCoords()
      if (usingPin) {
        const rec = await api.kioskPin(pin.trim(), coords, { occurrenceId })
        setResult(rec)
        setPin('')
        return
      }
      let challengeId: string | undefined
      const liveCfg = cfg ?? (await api.authConfig())
      if (liveCfg.require_liveness) {
        challengeId = await runBlinkChallenge(cam, setHint, 'kiosk')
      }
      setHint('Matching your face…')
      const blob = await cam.capture()
      const rec = await api.kioskPunch(new File([blob], 'kiosk.jpg', { type: 'image/jpeg' }), challengeId, coords, {
        occurrenceId,
      })
      setResult(rec)
    } catch (e) {
      setResult(null)
      const message = e instanceof Error ? e.message : 'We could not recognize you'
      if (/interrupted by a new load request|AbortError/i.test(message)) {
        setError('Hold still and tap Check in again.')
      } else if (/face_not_recognized/i.test(message)) {
        setError('We could not recognize you')
      } else {
        setError(message)
      }
    } finally {
      setBusy(false)
    }
  }

  const ok = Boolean(result && (result.decision === 'present' || result.already_marked))
  const tone = ok ? 'ok' : error ? 'bad' : 'idle'

  return (
    <div className="relative h-dvh overflow-hidden bg-bg">
      <div className="absolute left-4 top-4 z-10 flex items-center gap-3">
        <BrandMark className="h-9 w-9 text-ink" />
        <div>
          <div className="text-sm font-semibold">Sentinel kiosk</div>
          <div className="text-xs text-muted">Stand still. Look at the camera.</div>
        </div>
      </div>
      <div className="absolute right-4 top-4 z-10 flex gap-2">
        <button
          type="button"
          className="rounded-xl border border-line px-3 py-2 text-sm text-ink hover:bg-soft"
          onClick={() => {
            if (!document.fullscreenElement) void document.documentElement.requestFullscreen?.()
            else void document.exitFullscreen?.()
            setFullscreen(Boolean(document.fullscreenElement) === false)
          }}
        >
          {fullscreen ? 'Exit full screen' : 'Full screen'}
        </button>
        <Link to="/" className="rounded-xl border border-line px-3 py-2 text-sm text-ink hover:bg-soft">
          Exit
        </Link>
        <button type="button" className="rounded-xl px-3 py-2 text-sm text-muted" onClick={logout}>
          Sign out
        </button>
      </div>

      <div className="mx-auto flex h-full max-w-3xl flex-col justify-center px-4">
        <div className="relative overflow-hidden rounded-3xl border border-line bg-black">
          <video ref={cam.videoRef} className="aspect-[4/3] w-full object-cover" playsInline muted />
          {cam.ready ? <ScanFrame active={busy || (!result && !error)} tone={tone} /> : null}
        </div>
        <p className="mt-4 text-center text-sm text-muted">
          {busy ? hint : cam.error ? cam.error : hint}
        </p>
        {needsOccurrence ? (
          <select
            className={`mx-auto mt-3 max-w-md ${inputClass}`}
            value={occurrenceId ?? ''}
            onChange={(e) => setOccurrenceId(e.target.value ? Number(e.target.value) : undefined)}
          >
            <option value="">Select {org.kernel === 'shift' ? 'shift' : 'class'}</option>
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title} · {s.start}–{s.end}
                {s.open ? ' · open' : ''}
              </option>
            ))}
          </select>
        ) : null}
        <button
          type="button"
          disabled={usingPin ? !pin.trim() || busy : !cam.ready || busy || (needsOccurrence && !occurrenceId)}
          className="mt-4 rounded-2xl bg-accent px-6 py-3.5 text-base font-semibold text-accent-fg disabled:opacity-50"
          onClick={() => void punch()}
        >
          {busy ? 'Checking…' : usingPin ? 'Check in with ID' : 'Check in'}
        </button>
        {pinAllowed ? (
          <button
            type="button"
            className="mt-3 text-sm text-muted"
            onClick={() => setPinMode((v) => !v)}
          >
            {usingPin ? 'Use the camera' : `Camera not working? Use ${org.id}`}
          </button>
        ) : null}
        {usingPin ? (
          <input
            className={`mx-auto mt-3 max-w-xs ${inputClass} text-center text-lg`}
            placeholder={org.id}
            value={pin}
            onChange={(e) => setPin(e.target.value)}
          />
        ) : null}

        {result || error ? (
          <div
            className={`mt-6 rounded-3xl border p-8 text-center ${
              ok ? 'border-emerald-400 bg-emerald-50 dark:bg-emerald-950/40' : 'border-rose-400 bg-rose-50 dark:bg-rose-950/40'
            }`}
          >
            <div className={`text-4xl font-semibold ${ok ? 'text-emerald-600 dark:text-emerald-300' : 'text-rose-600 dark:text-rose-300'}`}>
              {error
                ? 'Try once more'
                : result?.already_marked
                  ? `Already in, ${firstName(result.person_name)}`
                  : result?.decision === 'present'
                    ? `Welcome, ${firstName(result.person_name)}`
                    : 'We could not recognize you'}
            </div>
            {result ? (
              <div className="mt-4 flex justify-center gap-2">
                <StatusBadge status={ok ? 'present' : 'failed'} />
                {result.late ? <StatusBadge status="late" /> : null}
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted">{error || 'Face the camera and try again.'}</p>
            )}
          </div>
        ) : null}
      </div>
    </div>
  )
}
