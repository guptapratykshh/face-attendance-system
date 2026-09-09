import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { PersonTimeline } from '../api/types'
import { AttendanceEdit } from '../components/AttendanceEdit'
import { Alert, Button, EmptyState, KindBadge, PageHeader, StatusBadge, TableSkeleton, cardClass } from '../components/ui'
import { useToast } from '../hooks/useToast'

export function PersonPage() {
  const { id } = useParams()
  const toast = useToast()
  const personId = Number(id)
  const [data, setData] = useState<PersonTimeline | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  async function refresh() {
    setData(await api.personTimeline(personId))
  }

  useEffect(() => {
    if (!Number.isFinite(personId)) return
    refresh()
      .catch((e) => setError(e.detail ?? String(e)))
      .finally(() => setLoading(false))
  }, [personId])

  async function deactivate() {
    if (!data) return
    if (!window.confirm(`Deactivate ${data.person.name}?`)) return
    setBusy(true)
    try {
      await api.deletePerson(data.person.id)
      toast.push('ok', `${data.person.name} is deactivated`)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not deactivate')
    } finally {
      setBusy(false)
    }
  }

  const person = data?.person

  return (
    <div>
      <PageHeader
        eyebrow="Person"
        title={person?.name ?? 'Person'}
        subtitle={person ? `${person.status}${person.office ? ` · ${person.office}` : ''}${person.department ? ` · ${person.department}` : ''}` : 'Attendance, photos, and events for one person.'}
        actions={
          person ? (
            <>
              <Link to={`/enroll?person=${person.id}`} className="inline-flex items-center rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-accent-fg">
                {person.n_embeddings ? 'Add another photo' : 'Add photo'}
              </Link>
              <Link to="/people" className="inline-flex items-center rounded-xl border border-line bg-panel px-4 py-2.5 text-sm font-semibold text-ink">
                Directory
              </Link>
            </>
          ) : null
        }
      />
      {error ? <Alert kind="error">{error}</Alert> : null}
      {loading ? <TableSkeleton /> : null}
      {person ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className={`${cardClass} p-4`}>
              <div className="text-xs text-muted">Status</div>
              <div className="mt-2"><StatusBadge status={person.status} /></div>
            </div>
            <div className={`${cardClass} p-4`}>
              <div className="text-xs text-muted">Login</div>
              <div className="mt-2 font-medium">{person.username ?? 'Not set'}</div>
            </div>
            <div className={`${cardClass} p-4`}>
              <div className="text-xs text-muted">Shift</div>
              <div className="mt-2 font-medium">
                {person.shift_start || person.shift_end ? `${person.shift_start ?? '—'} – ${person.shift_end ?? '—'}` : 'Office hours'}
              </div>
            </div>
            <div className={`${cardClass} p-4`}>
              <div className="text-xs text-muted">Photos</div>
              <div className="mt-2 font-medium">{person.n_embeddings}</div>
            </div>
          </div>

          <h2 className="mt-10 text-lg font-semibold">Attendance</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => {
                setBusy(true)
                void api
                  .manualAttendance({ person_id: person.id, decision: 'present' })
                  .then(async () => {
                    toast.push('ok', 'Marked present today')
                    await refresh()
                  })
                  .catch((e) => setError(e instanceof Error ? e.message : 'Could not mark present'))
                  .finally(() => setBusy(false))
              }}
            >
              Mark present today
            </Button>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => {
                setBusy(true)
                void api
                  .manualAttendance({ person_id: person.id, decision: 'absent' })
                  .then(async () => {
                    toast.push('ok', 'Marked absent today')
                    await refresh()
                  })
                  .catch((e) => setError(e instanceof Error ? e.message : 'Could not mark absent'))
                  .finally(() => setBusy(false))
              }}
            >
              Mark absent today
            </Button>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => {
                setBusy(true)
                void api
                  .manualAttendance({ person_id: person.id, decision: 'excused' })
                  .then(async () => {
                    toast.push('ok', 'Marked excused today')
                    await refresh()
                  })
                  .catch((e) => setError(e instanceof Error ? e.message : 'Could not mark excused'))
                  .finally(() => setBusy(false))
              }}
            >
              Mark excused today
            </Button>
          </div>
          <div className="mt-3 table-wrap">
            <table>
              <thead>
                <tr>
                  <th>In</th>
                  <th>Out</th>
                  <th>Result</th>
                  <th>Where</th>
                  <th>Edit</th>
                </tr>
              </thead>
              <tbody>
                {(data?.attendance ?? []).map((r) => (
                  <tr key={r.id}>
                    <td className="mono text-muted">{new Date(r.created_at).toLocaleString()}</td>
                    <td className="mono text-muted">{r.checked_out_at ? new Date(r.checked_out_at).toLocaleString() : '—'}</td>
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
                        onSaved={() => void refresh()}
                        onError={(message) => setError(message)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data && data.attendance.length === 0 ? (
              <EmptyState title="No punches yet" body="When they check in, the timeline fills in here." />
            ) : null}
          </div>

          <h2 className="mt-10 text-lg font-semibold">Events</h2>
          <div className="mt-3 table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Type</th>
                  <th>Result</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {(data?.events ?? []).map((e) => (
                  <tr key={e.id}>
                    <td className="mono text-muted">{new Date(e.created_at).toLocaleString()}</td>
                    <td><KindBadge kind={e.kind} /></td>
                    <td><StatusBadge status={e.decision} /></td>
                    <td className="text-muted">{e.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data && data.events.length === 0 ? (
              <EmptyState title="No events" body="Enrollments and check-ins will show up here." />
            ) : null}
          </div>

          {person.is_active ? (
            <Button variant="danger" disabled={busy} className="mt-8" onClick={() => void deactivate()}>
              Deactivate
            </Button>
          ) : (
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <p className="text-sm text-muted">This person is deactivated.</p>
              <Button
                disabled={busy}
                onClick={() => {
                  setBusy(true)
                  void api
                    .reactivatePerson(person.id)
                    .then(async () => {
                      toast.push('ok', `${person.name} can check in again`)
                      await refresh()
                    })
                    .catch((e) => setError(e instanceof Error ? e.message : 'Could not reactivate'))
                    .finally(() => setBusy(false))
                }}
              >
                Reactivate
              </Button>
            </div>
          )}
        </>
      ) : null}
    </div>
  )
}
