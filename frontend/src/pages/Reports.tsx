import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { AttendanceRecord, Person } from '../api/types'
import { AttendanceEdit } from '../components/AttendanceEdit'
import { Alert, Button, EmptyState, PageHeader, StatusBadge, TableSkeleton, inputClass } from '../components/ui'
import { datePreset, downloadAuthCsv } from '../lib/helpers'

export function ReportsPage() {
  const [rows, setRows] = useState<AttendanceRecord[]>([])
  const [people, setPeople] = useState<Person[]>([])
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [personId, setPersonId] = useState('')
  const [decision, setDecision] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  async function load() {
    const params = {
      from: from || undefined,
      to: to || undefined,
      person_id: personId ? Number(personId) : undefined,
      decision: decision || undefined,
    }
    setRows(await api.listAttendance(params))
  }

  useEffect(() => {
    Promise.all([api.listPersons(), api.listAttendance()])
      .then(([ps, att]) => {
        setPeople(ps)
        setRows(att)
      })
      .catch((e) => setError(e.detail ?? String(e)))
      .finally(() => setLoading(false))
  }, [])

  function applyPreset(kind: 'today' | 'week' | 'month') {
    const p = datePreset(kind)
    setFrom(p.from)
    setTo(p.to)
  }

  const exportHref = api.exportAttendanceUrl({
    from: from || undefined,
    to: to || undefined,
    person_id: personId ? Number(personId) : undefined,
    decision: decision || undefined,
  })

  const present = rows.filter((r) => r.decision === 'present').length
  const late = rows.filter((r) => r.late).length
  const rate = rows.length ? Math.round((present / rows.length) * 100) : 0

  return (
    <div>
      <PageHeader
        eyebrow="Payroll & audit"
        title="Attendance report"
        subtitle="Filter by date or person, then download a spreadsheet for payroll."
      />
      {error ? <div className="mb-4"><Alert kind="error">{error}</Alert></div> : null}
      <div className="mb-3 flex flex-wrap gap-2">
        <Button variant="secondary" onClick={() => applyPreset('today')}>Today</Button>
        <Button variant="secondary" onClick={() => applyPreset('week')}>This week</Button>
        <Button variant="secondary" onClick={() => applyPreset('month')}>This month</Button>
      </div>
      <div className="flex flex-wrap gap-3 items-end">
        <label className="text-xs font-medium text-muted">
          From
          <input type="date" className={`mt-1 block ${inputClass}`} value={from} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label className="text-xs font-medium text-muted">
          To
          <input type="date" className={`mt-1 block ${inputClass}`} value={to} onChange={(e) => setTo(e.target.value)} />
        </label>
        <label className="text-xs font-medium text-muted">
          Person
          <select className={`mt-1 block min-w-40 ${inputClass}`} value={personId} onChange={(e) => setPersonId(e.target.value)}>
            <option value="">Everyone</option>
            {people.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </label>
        <label className="text-xs font-medium text-muted">
          Result
          <select className={`mt-1 block ${inputClass}`} value={decision} onChange={(e) => setDecision(e.target.value)}>
            <option value="">All</option>
            <option value="present">Present</option>
            <option value="absent">Absent</option>
            <option value="excused">Excused</option>
            <option value="failed">Did not match</option>
          </select>
        </label>
        <Button onClick={() => void load().catch((e) => setError(e.detail ?? String(e)))}>Apply</Button>
        <Button variant="secondary" onClick={() => void downloadAuthCsv(exportHref, 'attendance.csv')}>
          Download CSV
        </Button>
      </div>
      <p className="mt-4 text-sm text-muted">
        {rows.length} rows · {rate}% present · {late} late
      </p>
      {loading ? (
        <div className="mt-6"><TableSkeleton /></div>
      ) : (
        <div className="mt-6 table-wrap">
          <table>
            <thead>
              <tr>
                <th>In</th>
                <th>Out</th>
                <th>Person</th>
                <th>Session</th>
                <th>Result</th>
                <th>Where</th>
                <th>Edit</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="mono text-muted">{new Date(r.created_at).toLocaleString()}</td>
                  <td className="mono text-muted">{r.checked_out_at ? new Date(r.checked_out_at).toLocaleString() : '—'}</td>
                  <td className="font-medium text-ink">
                    <Link to={`/people/${r.person_id}`} className="hover:underline">{r.person_name}</Link>
                  </td>
                  <td className="text-muted">{r.occurrence_title || '—'}</td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      <StatusBadge status={r.decision} />
                      {r.late ? <StatusBadge status="late" /> : null}
                      {r.early_leave ? <StatusBadge status="early_leave" /> : null}
                    </div>
                  </td>
                  <td><StatusBadge status={r.source} /></td>
                  <td>
                    <AttendanceEdit
                      row={r}
                      onSaved={(next) => setRows((cur) => cur.map((row) => (row.id === next.id ? next : row)))}
                      onError={(message) => setError(message)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 ? <EmptyState title="Nothing in this date range" body="Try Today, This week, or clear the filters." /> : null}
        </div>
      )}
    </div>
  )
}
