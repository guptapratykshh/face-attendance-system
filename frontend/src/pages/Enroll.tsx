import { type FormEvent, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { Person } from '../api/types'
import { ImageDropzone } from '../components/ImageDropzone'
import { WebcamCapture } from '../components/WebcamCapture'
import { Alert, Button, PageHeader, StatusBadge, cardClass, inputClass, listScrollClass } from '../components/ui'
import { useToast } from '../hooks/useToast'
import { useAuth } from '../hooks/useAuth'
import { orgFrom } from '../lib/org'

export function EnrollPage() {
  const [params, setParams] = useSearchParams()
  const [people, setPeople] = useState<Person[]>([])
  const [name, setName] = useState('')
  const [employeeId, setEmployeeId] = useState('')
  const [selected, setSelected] = useState<number | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [extras, setExtras] = useState<File[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const { config } = useAuth()
  const org = orgFrom(config)

  async function refresh() {
    setPeople(await api.listPersons())
  }

  useEffect(() => {
    refresh().catch((e) => setError(e.detail ?? String(e)))
  }, [])

  useEffect(() => {
    const raw = params.get('person')
    if (!raw) return
    const id = Number(raw)
    if (Number.isFinite(id)) setSelected(id)
  }, [params])

  const chosen = people.find((p) => p.id === selected) ?? null
  const awaiting = useMemo(() => people.filter((p) => p.n_embeddings === 0), [people])
  const enrolled = useMemo(() => people.filter((p) => p.n_embeddings > 0), [people])

  function pick(id: number) {
    setSelected(id)
    setError(null)
    setParams({ person: String(id) }, { replace: true })
  }

  async function create(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const p = await api.createPerson({ name, employee_id: employeeId || undefined })
      pick(p.id)
      setName('')
      setEmployeeId('')
      toast.push('ok', `${p.name} added`)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create person')
    } finally {
      setBusy(false)
    }
  }

  async function enroll() {
    if (selected == null) return
    const files = [file, ...extras].filter((f): f is File => Boolean(f))
    if (!files.length) return
    if (files.length > 5) {
      setError('Upload at most 5 photos per enrollment.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const updated = await api.enroll(selected, files)
      setFile(null)
      setExtras([])
      toast.push('ok', `${updated.name} can check in now.`)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the photo')
    } finally {
      setBusy(false)
    }
  }

  async function remove(id: number) {
    const target = people.find((p) => p.id === id)
    if (!window.confirm(`Deactivate ${target?.name ?? 'this person'}? Attendance history is kept.`)) return
    await api.deletePerson(id)
    if (selected === id) {
      setSelected(null)
      setParams({}, { replace: true })
    }
    await refresh()
  }

  function PersonRow({ p }: { p: Person }) {
    return (
      <li className={`flex items-center justify-between px-4 py-3 ${selected === p.id ? 'bg-soft' : ''}`}>
        <button type="button" className="text-left" onClick={() => pick(p.id)}>
          <div className="flex items-center gap-2">
            <span className="font-medium text-ink">{p.name}</span>
            <StatusBadge status={p.status} />
          </div>
          <div className="text-xs text-muted">
            {p.username ? `login ${p.username}` : 'no login'} · {p.employee_id ?? 'no ID'}
            {p.n_embeddings === 0 ? ' · waiting for photo' : ` · ${p.n_embeddings} photo(s)`}
          </div>
        </button>
        <button type="button" className="text-xs font-medium text-rose-600 dark:text-rose-400" onClick={() => void remove(p.id)}>
          Deactivate
        </button>
      </li>
    )
  }

  return (
    <div>
      <PageHeader
        title="Add face photos"
        subtitle="Use 1–5 front-facing photos, even light, one face filling the frame. Glasses are fine; sunglasses are not."
      />
      {error ? <div className="mb-4"><Alert kind="error">{error}</Alert></div> : null}

      {awaiting.length > 0 ? (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-ink">Waiting for a photo ({awaiting.length})</h2>
          <ul className={`mt-2 divide-y divide-line ${cardClass} ring-1 ring-line ${listScrollClass}`}>
            {awaiting.map((p) => (
              <PersonRow key={p.id} p={p} />
            ))}
          </ul>
        </div>
      ) : (
        <p className="mb-6 text-sm text-muted">Nobody is waiting for a photo right now.</p>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        <div className={`space-y-3 ${cardClass} p-5`}>
          <h2 className="text-sm font-semibold text-ink">Capture or upload</h2>
          {chosen ? (
            <p className="text-sm text-ink">
              Selected: {chosen.name}
              {chosen.n_embeddings === 0 ? ' — no photo yet' : ` — ${chosen.n_embeddings} photo(s) already`}
            </p>
          ) : (
            <p className="text-sm text-muted">Pick someone from the lists, then take or upload a photo.</p>
          )}
          <ImageDropzone label="Enrollment photo" file={file} onFile={setFile} />
          <WebcamCapture
            overlay
            onCapture={(f) => {
              if (!file) setFile(f)
              else setExtras((xs) => [...xs, f])
            }}
          />
          <Button disabled={selected == null || (!file && extras.length === 0) || busy} onClick={() => void enroll()}>
            {busy ? 'Saving…' : chosen ? `Save photo for ${chosen.name}` : 'Save photo'}
          </Button>
        </div>

        <form onSubmit={(e) => void create(e)} className={`${cardClass} h-fit space-y-3 p-5`}>
          <h2 className="text-sm font-semibold text-ink">Add someone without a login</h2>
          <p className="text-xs text-muted">Most people should register themselves. Use this only for gallery-only identities.</p>
          <input className={inputClass} placeholder="Full name" value={name} onChange={(e) => setName(e.target.value)} required />
          <input className={inputClass} placeholder={`${org.id} (optional)`} value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} />
          <Button type="submit" disabled={busy}>Create</Button>
        </form>
      </div>

      <h2 className="mt-10 text-sm font-semibold text-ink">Already have a photo</h2>
      <ul className={`mt-2 divide-y divide-line ${cardClass} ${listScrollClass}`}>
        {enrolled.map((p) => (
          <PersonRow key={p.id} p={p} />
        ))}
        {enrolled.length === 0 ? <li className="px-4 py-6 text-sm text-muted">None yet.</li> : null}
      </ul>
    </div>
  )
}
