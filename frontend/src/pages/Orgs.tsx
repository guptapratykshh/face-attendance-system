import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { Organization, OrgPreset } from '../api/types'
import { Alert, Button, EmptyState, PageHeader, cardClass, inputClass } from '../components/ui'
import { useAuth } from '../hooks/useAuth'
import { useToast } from '../hooks/useToast'
import { titleCase } from '../lib/org'

export function OrgsPage() {
  const { enterOrg } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [orgs, setOrgs] = useState<Organization[]>([])
  const [presets, setPresets] = useState<OrgPreset[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ name: '', org_type: 'workplace' })

  async function refresh() {
    setLoading(true)
    try {
      const [rows, catalog] = await Promise.all([api.listOrgs(), api.orgPresets().catch(() => [] as OrgPreset[])])
      setOrgs(rows)
      setPresets(catalog)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load organizations')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function openOrg(org: Organization) {
    await enterOrg(org.id)
    toast.push('ok', `Opened ${org.name}`)
    navigate('/')
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    if (!form.name.trim()) return
    setCreating(true)
    try {
      const created = await api.createOrg({ name: form.name.trim(), org_type: form.org_type })
      setForm({ name: '', org_type: 'workplace' })
      await refresh()
      await openOrg(created)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create organization')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Organizations"
        subtitle="Create a workplace, school, or other site, then enroll people inside it."
      />
      {error ? <Alert kind="error">{error}</Alert> : null}

      <section className={`mt-6 ${cardClass} p-5`}>
        <h2 className="text-sm font-semibold text-ink">Create organization</h2>
        <p className="mt-1 text-sm text-muted">Type sets labels and how attendance works for that org only.</p>
        <form onSubmit={(e) => void onCreate(e)} className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="text-xs font-medium text-muted" htmlFor="org-name">
            Name
            <input
              id="org-name"
              className={`mt-1 ${inputClass}`}
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="North Campus"
              required
            />
          </label>
          <label className="text-xs font-medium text-muted" htmlFor="org-type">
            Type
            <select
              id="org-type"
              className={`mt-1 ${inputClass}`}
              value={form.org_type}
              onChange={(e) => setForm((f) => ({ ...f, org_type: e.target.value }))}
            >
              {(presets.length ? presets : [{ org_type: 'workplace', title: 'Workplace / office' }]).map((p) => (
                <option key={p.org_type} value={p.org_type}>
                  {p.title}
                </option>
              ))}
            </select>
          </label>
          {presets.find((p) => p.org_type === form.org_type)?.blurb ? (
            <p className="sm:col-span-2 text-sm text-muted">{presets.find((p) => p.org_type === form.org_type)?.blurb}</p>
          ) : null}
          <div>
            <Button type="submit" disabled={creating}>
              {creating ? 'Creating…' : 'Create and open'}
            </Button>
          </div>
        </form>
      </section>

      <h2 className="mt-10 text-lg font-semibold text-ink">All organizations</h2>
      {loading ? <p className="mt-3 text-sm text-muted">Loading…</p> : null}
      {!loading && orgs.length === 0 ? (
        <div className={`mt-3 ${cardClass}`}>
          <EmptyState title="None yet" body="Create the first organization to enroll people and run attendance." />
        </div>
      ) : (
        <ul className="mt-3 grid gap-3 sm:grid-cols-2">
          {orgs.map((org) => (
            <li key={org.id} className={`${cardClass} p-4`}>
              <div className="text-sm font-semibold text-ink">{org.name}</div>
              <p className="mt-1 text-xs text-muted">
                {titleCase(org.org_type.replace('_', ' '))} · {titleCase(org.subject_label_plural)} · {org.people_count}{' '}
                enrolled
              </p>
              <p className="mt-1 font-mono text-xs text-muted">Login code: {org.slug}</p>
              <Button className="mt-4" variant="secondary" onClick={() => void openOrg(org)}>
                Open
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
