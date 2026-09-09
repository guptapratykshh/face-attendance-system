import { useState } from 'react'
import { api } from '../api/client'
import type { AttendanceRecord } from '../api/types'
import { useAuth } from '../hooks/useAuth'
import { orgFrom } from '../lib/org'
import { inputClass } from './ui'

const DECISIONS = [
  { value: 'present', label: 'Present' },
  { value: 'absent', label: 'Absent' },
  { value: 'excused', label: 'Excused / leave' },
  { value: 'failed', label: 'Failed match' },
]

export function AttendanceEdit({
  row,
  onSaved,
  onError,
}: {
  row: AttendanceRecord
  onSaved: (next: AttendanceRecord) => void
  onError?: (message: string) => void
}) {
  const { config } = useAuth()
  const org = orgFrom(config)
  const [decision, setDecision] = useState(row.decision)
  const [late, setLate] = useState(row.late)
  const [early, setEarly] = useState(Boolean(row.early_leave))
  const [out, setOut] = useState(Boolean(row.checked_out_at))
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true)
    try {
      const next = await api.updateAttendance(row.id, {
        decision,
        late: decision === 'present' ? late : false,
        early_leave: decision === 'present' ? early : false,
        checked_out: decision === 'present' ? out : false,
      })
      onSaved(next)
    } catch (e) {
      onError?.(e instanceof Error ? e.message : 'Could not save attendance')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <select
        className={`${inputClass} py-1 text-xs`}
        value={decision}
        disabled={busy}
        onChange={(e) => setDecision(e.target.value)}
        aria-label="Attendance result"
      >
        {DECISIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {decision === 'present' ? (
        <>
          {org.trackLate ? (
            <label className="flex items-center gap-1 text-muted">
              <input type="checkbox" checked={late} disabled={busy} onChange={(e) => setLate(e.target.checked)} />
              Late
            </label>
          ) : null}
          {org.trackEarlyLeave ? (
            <label className="flex items-center gap-1 text-muted">
              <input type="checkbox" checked={early} disabled={busy} onChange={(e) => setEarly(e.target.checked)} />
              Left early
            </label>
          ) : null}
          {org.allowCheckout ? (
            <label className="flex items-center gap-1 text-muted">
              <input type="checkbox" checked={out} disabled={busy} onChange={(e) => setOut(e.target.checked)} />
              Checked out
            </label>
          ) : null}
        </>
      ) : null}
      <button
        type="button"
        disabled={busy}
        className="rounded-lg border border-line px-2 py-1 font-medium text-ink hover:bg-soft disabled:opacity-50"
        onClick={() => void save()}
      >
        {busy ? 'Saving…' : 'Save'}
      </button>
    </div>
  )
}
