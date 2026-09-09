import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { BoardPerson, OpsSummary } from '../api/types'
import { BrandMark } from '../components/Logo'
import { Initials, StatusBadge } from '../components/ui'

function useClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(id)
  }, [])
  return now
}

function timeOf(iso: string | null | undefined) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function PersonTile({ person, inNow }: { person: BoardPerson; inNow: boolean }) {
  return (
    <div
      className={`flex min-h-[8.5rem] flex-col justify-between rounded-3xl border p-5 ${
        inNow ? 'border-emerald-500/40 bg-panel shadow-[0_0_0_1px_rgba(16,185,129,0.12)]' : 'border-line bg-panel/70'
      }`}
    >
      <div className="flex items-start gap-4">
        <Initials name={person.person_name} className="h-14 w-14 text-lg" />
        <div className="min-w-0">
          <div className="truncate text-xl font-semibold tracking-tight">{person.person_name}</div>
          <div className="mt-1 text-sm text-muted">{person.office || 'Office'}</div>
        </div>
      </div>
      <div className="mt-4 flex items-center justify-between gap-2">
        {inNow ? (
          <>
            <div className="text-sm text-muted">In since {timeOf(person.checked_in_at)}</div>
            <div className="flex gap-1">
              <StatusBadge status="present" />
              {person.late ? <StatusBadge status="late" /> : null}
            </div>
          </>
        ) : (
          <>
            <div className="text-sm text-muted">Has not checked in</div>
            <span className="inline-flex rounded-full bg-soft px-2.5 py-0.5 text-xs font-medium text-muted ring-1 ring-inset ring-line">
              Waiting
            </span>
          </>
        )}
      </div>
    </div>
  )
}

export function BoardPage() {
  const now = useClock()
  const [summary, setSummary] = useState<OpsSummary | null>(null)

  useEffect(() => {
    const load = () => {
      api.opsSummary().then(setSummary).catch(() => undefined)
    }
    load()
    const id = window.setInterval(load, 8000)
    return () => window.clearInterval(id)
  }, [])

  const inNow = summary?.in_now ?? []
  const waiting = summary?.waiting ?? []
  const expected = (summary?.present_today ?? 0) + (summary?.absent_today ?? 0)
  const pct = expected ? Math.round(((summary?.present_today ?? 0) / expected) * 100) : 0
  const office = summary?.office_name || 'Office'
  const weekday = now.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })

  return (
    <div className="flex h-dvh flex-col bg-bg px-6 py-5 md:px-10 md:py-7">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <BrandMark className="mt-1 h-12 w-12 text-ink" />
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">Entrance screen</div>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight md:text-4xl">Who is in the office</h1>
            <p className="mt-2 max-w-xl text-sm leading-6 text-muted">
              Put this on a TV at the door. It refreshes by itself when someone checks in at the kiosk or on their phone.
            </p>
            <p className="mt-1 text-sm text-muted">
              {office} · {summary?.tz ?? '—'} · hours {summary?.work_start ?? '—'}–{summary?.work_end ?? '—'}
            </p>
          </div>
        </div>
        <div className="flex items-end gap-6">
          <div className="text-right">
            <div className="font-semibold tabular-nums text-4xl md:text-5xl">
              {now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
            <div className="mt-1 text-sm text-muted">{weekday}</div>
          </div>
          <Link to="/" className="rounded-xl border border-line px-3 py-2 text-sm text-ink hover:bg-soft">
            Exit
          </Link>
        </div>
      </header>

      <div className="mt-6 grid grid-cols-3 gap-3">
        <div className="rounded-2xl border border-emerald-500/30 bg-panel px-4 py-3">
          <div className="text-xs font-medium uppercase tracking-wide text-muted">In now</div>
          <div className="mt-1 text-3xl font-semibold tabular-nums">{inNow.length}</div>
        </div>
        <div className="rounded-2xl border border-line bg-panel px-4 py-3">
          <div className="text-xs font-medium uppercase tracking-wide text-muted">Not in yet</div>
          <div className="mt-1 text-3xl font-semibold tabular-nums">{waiting.length}</div>
        </div>
        <div className="rounded-2xl border border-line bg-panel px-4 py-3">
          <div className="text-xs font-medium uppercase tracking-wide text-muted">Of expected</div>
          <div className="mt-1 text-3xl font-semibold tabular-nums">{pct}%</div>
        </div>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-soft">
        <div className="h-full bg-emerald-500 transition-[width] duration-500" style={{ width: `${pct}%` }} />
      </div>

      <div className="mt-6 min-h-0 flex-1 overflow-y-auto">
        {summary?.workday === false ? (
          <div className="grid h-full place-items-center rounded-3xl border border-line bg-panel text-center">
            <div>
              <div className="text-2xl font-semibold">Office is closed today</div>
              <p className="mt-2 text-sm text-muted">Weekend or holiday — expected attendance is off.</p>
            </div>
          </div>
        ) : (
          <div className="grid gap-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(16rem,0.8fr)]">
            <section>
              <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-muted">In the building</h2>
              <div className="mt-3 grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(16rem,1fr))]">
                {inNow.map((p) => (
                  <PersonTile key={p.person_id} person={p} inNow />
                ))}
              </div>
              {inNow.length === 0 ? (
                <div className="mt-3 rounded-3xl border border-dashed border-line px-6 py-16 text-center">
                  <div className="text-lg font-medium">Nobody has checked in yet</div>
                  <p className="mt-2 text-sm text-muted">When a face matches at the kiosk, their name appears here.</p>
                </div>
              ) : null}
            </section>
            <section>
              <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-muted">Still expected</h2>
              <div className="mt-3 grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(14rem,1fr))]">
                {waiting.map((p) => (
                  <PersonTile key={p.person_id} person={p} inNow={false} />
                ))}
              </div>
              {waiting.length === 0 && inNow.length > 0 ? (
                <p className="mt-4 text-sm text-muted">Everyone expected is in.</p>
              ) : null}
            </section>
          </div>
        )}
      </div>
    </div>
  )
}
