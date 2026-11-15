import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { ClassroomScan, Occurrence } from '../api/types'
import { ImageDropzone } from '../components/ImageDropzone'
import { WebcamCapture } from '../components/WebcamCapture'
import { Alert, Button, PageHeader, cardClass, inputClass } from '../components/ui'
import { datePreset, downloadAuthCsv } from '../lib/helpers'

export function ClassroomPage() {
  const [sessions, setSessions] = useState<Occurrence[]>([])
  const [occurrenceId, setOccurrenceId] = useState<number | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<ClassroomScan | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const preview = useMemo(() => file ? URL.createObjectURL(file) : null, [file])

  useEffect(() => {
    return () => { if (preview) URL.revokeObjectURL(preview) }
  }, [preview])

  useEffect(() => {
    api.listOccurrences({ day: datePreset('today').to })
      .then((rows) => setSessions(rows.filter((s) => s.kind === 'session' && s.offering_id != null)))
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load lectures'))
      .finally(() => setLoading(false))
  }, [])

  const selected = sessions.find((s) => s.id === occurrenceId)

  async function scan() {
    if (!file || !occurrenceId) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      setResult(await api.scanClassroom(occurrenceId, file))
      const rows = await api.listOccurrences({ day: datePreset('today').to })
      setSessions(rows.filter((s) => s.kind === 'session' && s.offering_id != null))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not scan classroom')
    } finally {
      setBusy(false)
    }
  }

  function changeFile(next: File | null) {
    setFile(next)
    setResult(null)
    setError(null)
  }

  return (
    <div>
      <PageHeader
        eyebrow="Lecture attendance"
        title="Classroom scan"
        subtitle="Select an open lecture, capture the class, and review detected faces and attendance afterward."
      />
      <div className={`${cardClass} mt-5 p-5`}>
        <label className="block text-sm font-medium text-ink" htmlFor="lecture-select">Today's lecture</label>
        <select id="lecture-select" className={`mt-2 w-full max-w-xl ${inputClass}`} value={occurrenceId ?? ''} onChange={(e) => { setOccurrenceId(e.target.value ? Number(e.target.value) : null); setResult(null) }}>
          <option value="">Select a lecture</option>
          {sessions.map((s) => <option key={s.id} value={s.id}>{s.title} · {s.start}–{s.end} · {s.expected} enrolled {s.open ? '· open' : '· closed'}</option>)}
        </select>
        {loading ? <p className="mt-3 text-sm text-muted">Loading lectures…</p> : null}
        {!loading && sessions.length === 0 ? <p className="mt-3 text-sm text-muted">No course lectures today. <Link className="text-accent underline" to="/schedule">Create a course and lecture</Link>, then enroll students.</p> : null}
        {selected ? <p className="mt-2 text-sm text-muted">{selected.expected} students on this roster · {selected.present} already present</p> : null}
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <ImageDropzone label="Classroom photo" file={file} onFile={changeFile} />
        <WebcamCapture onCapture={(captured) => changeFile(captured)} />
      </div>
      <p className="mt-3 text-sm text-muted">Use a clear, well-lit photo with visible faces. One photo can miss students who are turned away or too far from the camera.</p>
      <Button className="mt-4" disabled={!file || !selected?.open || busy} onClick={() => void scan()}>{busy ? 'Scanning…' : 'Scan and mark attendance'}</Button>
      {selected && !selected.open ? <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">This lecture is closed. Scanning is available from 15 minutes before it starts until it ends.</p> : null}
      {error ? <div className="mt-4"><Alert kind="error">{error}</Alert></div> : null}

      {result ? (
        <section className="mt-6" aria-label="Scan results">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-xl font-semibold text-ink">{result.title} · scan results</h2>
            <Button variant="secondary" onClick={() => void downloadAuthCsv(api.classroomCsvUrl(result.occurrence_id), `lecture-${result.occurrence_id}-attendance.csv`).catch((e) => setError(String(e)))}>Download lecture CSV</Button>
          </div>
          <p className="mt-2 text-sm text-muted">{result.detected} faces found · {result.marked} marked present · {result.already_marked} already marked · {result.face_ready} of {result.roster_size} enrolled students have face profiles</p>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {preview ? <img src={preview} alt="Scanned classroom" className="w-full rounded-2xl border border-line object-contain" /> : null}
            <div className={`${cardClass} p-4`}>
              <h3 className="font-semibold text-ink">Detected faces</h3>
              <ul className="mt-3 space-y-2">
                {result.faces.map((face, i) => (
                  <li key={i} className="flex items-center justify-between gap-3 rounded-xl border border-line p-3 text-sm">
                    <span className="font-medium text-ink">Face {i + 1}: {face.name || 'Unidentified'}</span>
                    <span className={face.status === 'marked' || face.status === 'already_marked' ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300'}>{face.status.replace('_', ' ')}{face.similarity == null ? '' : ` · ${face.similarity.toFixed(3)}`}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-4 text-sm text-muted">Unknown, low-quality, and unseen students need a manual check in <Link className="text-accent underline" to="/reports">Reports</Link>. A missing face is recorded as “not seen”, not automatically absent.</p>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  )
}
