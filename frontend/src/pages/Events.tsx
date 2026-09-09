import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { AccessEvent } from '../api/types'
import { Alert, Button, EmptyState, KindBadge, PageHeader, StatusBadge, TableSkeleton, inputClass, scoreClass } from '../components/ui'
import { downloadAuthCsv } from '../lib/helpers'

export function EventsPage() {
  const [events, setEvents] = useState<AccessEvent[]>([])
  const [error, setError] = useState<string | null>(null)
  const [kind, setKind] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [loading, setLoading] = useState(true)

  async function refresh() {
    setEvents(
      await api.events({
        limit: 200,
        kind: kind || undefined,
        from: from || undefined,
        to: to || undefined,
      }),
    )
  }

  useEffect(() => {
    refresh()
      .catch((e) => setError(e.detail ?? String(e)))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <PageHeader
        eyebrow="Audit log"
        title="Activity"
        subtitle="Check-ins, face enrollments, and other system events."
      />
      {error ? <div className="mb-4"><Alert kind="error">{error}</Alert></div> : null}
      <div className="flex flex-wrap gap-3 items-end">
        <label className="text-xs font-medium text-muted">
          Type
          <select className={`mt-1 block ${inputClass}`} value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">All</option>
            <option value="attendance">Attendance</option>
            <option value="enroll">Enroll</option>
            <option value="identify">Identify</option>
            <option value="verify">Verify</option>
            <option value="liveness">Liveness</option>
            <option value="spoof">Photo / video cheat</option>
            <option value="person">People</option>
          </select>
        </label>
        <label className="text-xs font-medium text-muted">
          From
          <input type="date" className={`mt-1 block ${inputClass}`} value={from} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label className="text-xs font-medium text-muted">
          To
          <input type="date" className={`mt-1 block ${inputClass}`} value={to} onChange={(e) => setTo(e.target.value)} />
        </label>
        <Button onClick={() => void refresh().catch((e) => setError(e.detail ?? String(e)))}>Filter</Button>
        <Button
          variant="secondary"
          onClick={() =>
            void downloadAuthCsv(
              api.exportEventsUrl({ kind: kind || undefined, from: from || undefined, to: to || undefined }),
              'events.csv',
            )
          }
        >
          Download CSV
        </Button>
      </div>
      {loading ? (
        <div className="mt-5"><TableSkeleton /></div>
      ) : (
        <div className="mt-5 table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Type</th>
                <th>Result</th>
                <th>Person</th>
                <th>Score</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => {
                const pass = ['present', 'match', 'live', 'enrolled', 'checked_out'].includes(e.decision)
                const fail = ['failed', 'no_match', 'spoof', 'deactivated', 'blocked'].includes(e.decision)
                return (
                <tr key={e.id}>
                  <td className="mono text-muted">{new Date(e.created_at).toLocaleString()}</td>
                  <td><KindBadge kind={e.kind} /></td>
                  <td><StatusBadge status={e.decision} /></td>
                  <td>{e.person_name ?? '—'}</td>
                  <td className={`mono ${scoreClass(e.similarity, pass ? true : fail ? false : undefined)}`}>
                    {e.similarity != null ? e.similarity.toFixed(4) : '—'}
                  </td>
                  <td className="text-muted">{e.detail}</td>
                </tr>
                )
              })}
            </tbody>
          </table>
          {events.length === 0 ? <EmptyState title="No activity yet" body="Check-ins and enrollments will appear here." /> : null}
        </div>
      )}
    </div>
  )
}
