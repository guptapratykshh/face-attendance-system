import { type FormEvent, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Person } from '../api/types'
import { Alert, Button, EmptyState, PageHeader, StatusBadge, TableSkeleton, cardClass, inputClass } from '../components/ui'
import { useAuth } from '../hooks/useAuth'
import { useToast } from '../hooks/useToast'
import { orgFrom, titleCase } from '../lib/org'

export function PeoplePage() {
  const toast = useToast()
  const { config } = useAuth()
  const org = orgFrom(config)
  const [people, setPeople] = useState<Person[]>([])
  const [query, setQuery] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [editing, setEditing] = useState<Person | null>(null)
  const [form, setForm] = useState({
    name: '',
    employee_id: '',
    email: '',
    notes: '',
    department: '',
    office: '',
    shift_start: '',
    shift_end: '',
  })
  const [loginFor, setLoginFor] = useState<Person | null>(null)
  const [loginForm, setLoginForm] = useState({ username: '', password: '' })
  const [create, setCreate] = useState({ name: '', employee_id: '', email: '', department: '', office: '' })

  async function refresh() {
    setPeople(await api.listPersons(true))
  }

  useEffect(() => {
    refresh()
      .catch((e) => setError(e.detail ?? String(e)))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return people
    return people.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.username ?? '').toLowerCase().includes(q) ||
        (p.employee_id ?? '').toLowerCase().includes(q) ||
        (p.department ?? '').toLowerCase().includes(q) ||
        (p.office ?? '').toLowerCase().includes(q),
    )
  }, [people, query])

  async function addPerson(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await api.createPerson({
        name: create.name.trim(),
        employee_id: create.employee_id.trim() || undefined,
        email: create.email.trim() || undefined,
        department: create.department.trim() || undefined,
        office: create.office.trim() || undefined,
      })
      setCreate({ name: '', employee_id: '', email: '', department: '', office: '' })
      toast.push('ok', 'Person added')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add this person')
    }
  }

  async function onImport(file: File | null) {
    if (!file) return
    setError(null)
    try {
      const result = await api.importPersons(file)
      toast.push('ok', `Imported ${result.created}, skipped ${result.skipped}`)
      if (result.errors.length) setError(result.errors.join('; '))
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
    }
  }

  async function saveEdit(e: FormEvent) {
    e.preventDefault()
    if (!editing) return
    setBusyId(editing.id)
    try {
      await api.updatePerson(editing.id, {
        name: form.name.trim(),
        employee_id: form.employee_id.trim() || null,
        email: form.email.trim() || null,
        notes: form.notes.trim() || null,
        department: form.department.trim() || null,
        office: form.office.trim() || null,
        shift_start: form.shift_start.trim() || null,
        shift_end: form.shift_end.trim() || null,
      })
      setEditing(null)
      toast.push('ok', 'Saved')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed')
    } finally {
      setBusyId(null)
    }
  }

  async function saveLogin(e: FormEvent) {
    e.preventDefault()
    if (!loginFor) return
    setBusyId(loginFor.id)
    try {
      await api.setPersonLogin(loginFor.id, {
        username: loginForm.username.trim(),
        password: loginForm.password,
      })
      toast.push('ok', `Username ${loginForm.username.trim()} is ready`)
      setLoginFor(null)
      setLoginForm({ username: '', password: '' })
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not set login')
    } finally {
      setBusyId(null)
    }
  }

  async function deactivate(p: Person) {
    if (!window.confirm(`Deactivate ${p.name}? Their history stays, but they cannot check in.`)) return
    setBusyId(p.id)
    try {
      await api.deletePerson(p.id)
      toast.push('ok', `${p.name} deactivated`)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not deactivate')
    } finally {
      setBusyId(null)
    }
  }

  async function reactivate(p: Person) {
    setBusyId(p.id)
    try {
      await api.reactivatePerson(p.id)
      toast.push('ok', `${p.name} can check in again`)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not reactivate')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Directory"
        title={titleCase(org.subjectPlural)}
        subtitle={`Add a ${org.subject}, give them a login, then save a face photo. They cannot check in until the photo is there.`}
      />
      {error ? <div className="mb-4"><Alert kind="error">{error}</Alert></div> : null}

      <form onSubmit={(e) => void addPerson(e)} className={`${cardClass} p-5 grid gap-3 md:grid-cols-5`}>
        <input className={inputClass} placeholder="Full name" value={create.name} onChange={(e) => setCreate((c) => ({ ...c, name: e.target.value }))} required />
        <input className={inputClass} placeholder={org.id} value={create.employee_id} onChange={(e) => setCreate((c) => ({ ...c, employee_id: e.target.value }))} />
        <input className={inputClass} placeholder="Email" value={create.email} onChange={(e) => setCreate((c) => ({ ...c, email: e.target.value }))} />
        <input className={inputClass} placeholder="Office" value={create.office} onChange={(e) => setCreate((c) => ({ ...c, office: e.target.value }))} />
        <Button type="submit">Add {org.subject}</Button>
        <label className="md:col-span-5 text-xs text-muted">
          Or import a CSV with columns name, employee_id, email
          <input type="file" accept=".csv,text/csv" className="mt-1 block text-sm" onChange={(e) => void onImport(e.target.files?.[0] ?? null)} />
        </label>
      </form>

      <input
        className={`${inputClass} mt-4 max-w-md`}
        placeholder="Search by name, username, office, or ID"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      {loginFor ? (
        <form onSubmit={(e) => void saveLogin(e)} className={`mt-4 ${cardClass} p-5 grid gap-3 md:grid-cols-2 ring-1 ring-line`}>
          <div className="md:col-span-2 text-sm font-medium text-ink">Login for {loginFor.name}</div>
          <input className={inputClass} placeholder="Username" value={loginForm.username} onChange={(e) => setLoginForm((f) => ({ ...f, username: e.target.value }))} required minLength={3} />
          <input type="password" className={inputClass} placeholder="Password (min 8 characters)" value={loginForm.password} onChange={(e) => setLoginForm((f) => ({ ...f, password: e.target.value }))} required minLength={8} />
          <div className="md:col-span-2 flex gap-2">
            <Button type="submit">Save login</Button>
            <Button type="button" variant="ghost" onClick={() => setLoginFor(null)}>Cancel</Button>
          </div>
        </form>
      ) : null}

      {editing ? (
        <form onSubmit={(e) => void saveEdit(e)} className={`mt-4 ${cardClass} p-5 grid gap-3 md:grid-cols-2 ring-1 ring-line`}>
          <input className={inputClass} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
          <input className={inputClass} placeholder={org.id} value={form.employee_id} onChange={(e) => setForm((f) => ({ ...f, employee_id: e.target.value }))} />
          <input className={inputClass} placeholder="Email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
          <input className={inputClass} placeholder={titleCase(org.group)} value={form.department} onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))} />
          <input className={inputClass} placeholder="Office" value={form.office} onChange={(e) => setForm((f) => ({ ...f, office: e.target.value }))} />
          <input className={inputClass} placeholder="Notes" value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} />
          <input className={inputClass} placeholder="Shift start HH:MM" value={form.shift_start} onChange={(e) => setForm((f) => ({ ...f, shift_start: e.target.value }))} />
          <input className={inputClass} placeholder="Shift end HH:MM" value={form.shift_end} onChange={(e) => setForm((f) => ({ ...f, shift_end: e.target.value }))} />
          <div className="md:col-span-2 flex gap-2">
            <Button type="submit">Save</Button>
            <Button type="button" variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
          </div>
        </form>
      ) : null}

      {loading ? (
        <div className="mt-5"><TableSkeleton rows={6} /></div>
      ) : (
        <div className="mt-5 table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Login</th>
                <th>Office</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <tr key={p.id} className={!p.is_active ? 'opacity-60' : ''}>
                  <td className="font-medium text-ink">
                    <Link to={`/people/${p.id}`} className="hover:underline">{p.name}</Link>
                  </td>
                  <td><StatusBadge status={p.status} /></td>
                  <td className="mono text-muted">{p.username ?? '—'}</td>
                  <td className="text-muted">{p.office || p.department || '—'}</td>
                  <td>
                    <div className="flex flex-wrap gap-3 text-sm">
                      <Link to={`/people/${p.id}`} className="font-medium text-ink hover:underline">Timeline</Link>
                      <Link to={`/enroll?person=${p.id}`} className="font-medium text-ink hover:underline">
                        {p.n_embeddings === 0 ? 'Add photo' : 'Add another photo'}
                      </Link>
                      <button type="button" className="font-medium text-ink hover:underline" onClick={() => { setLoginFor(p); setLoginForm({ username: p.username ?? '', password: '' }) }}>
                        {p.username ? 'Reset login' : 'Give login'}
                      </button>
                      <button type="button" className="font-medium text-ink hover:underline" onClick={() => { setEditing(p); setForm({ name: p.name, employee_id: p.employee_id ?? '', email: p.email ?? '', notes: p.notes ?? '', department: p.department ?? '', office: p.office ?? '', shift_start: p.shift_start ?? '', shift_end: p.shift_end ?? '' }) }}>
                        Edit
                      </button>
                      {p.is_active ? (
                        <button type="button" className="font-medium text-rose-600 dark:text-rose-400 hover:underline" disabled={busyId === p.id} onClick={() => void deactivate(p)}>
                          Deactivate
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="font-medium text-emerald-700 hover:underline dark:text-emerald-400"
                          disabled={busyId === p.id}
                          onClick={() => void reactivate(p)}
                        >
                          Reactivate
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 ? (
            <EmptyState
              title={people.length === 0 ? 'No people yet' : 'No matches'}
              body={people.length === 0 ? 'Add someone above, then enroll a photo so they can check in.' : 'Try a different search.'}
            />
          ) : null}
        </div>
      )}
    </div>
  )
}
