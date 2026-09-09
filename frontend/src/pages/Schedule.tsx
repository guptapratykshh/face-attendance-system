import { type FormEvent, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Occurrence, Offering, Person, Site } from '../api/types'
import { Alert, Button, PageHeader, cardClass, inputClass } from '../components/ui'
import { useAuth } from '../hooks/useAuth'
import { useToast } from '../hooks/useToast'
import { orgFrom, titleCase } from '../lib/org'

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export function SchedulePage() {
  const { config } = useAuth()
  const org = orgFrom(config)
  const toast = useToast()
  const [offerings, setOfferings] = useState<Offering[]>([])
  const [occurrences, setOccurrences] = useState<Occurrence[]>([])
  const [sites, setSites] = useState<Site[]>([])
  const [people, setPeople] = useState<Person[]>([])
  const [error, setError] = useState<string | null>(null)
  const [offeringForm, setOfferingForm] = useState({ name: '', code: '', kind: org.kernel === 'shift' ? 'shift' : 'course', default_start: '09:00', default_end: '10:00' })
  const [occForm, setOccForm] = useState({ offering_id: '', title: '', day: todayIso(), start: '09:00', end: '10:00', overnight: false })
  const [siteForm, setSiteForm] = useState({ name: '', lat: '', lng: '', radius_m: '150' })
  const [enrollFor, setEnrollFor] = useState<number | null>(null)
  const [enrollPerson, setEnrollPerson] = useState('')

  async function refresh() {
    const [offs, occs, st, ps] = await Promise.all([
      api.listOfferings(),
      api.listOccurrences({ day: todayIso() }),
      api.listSites(),
      api.listPersons(),
    ])
    setOfferings(offs)
    setOccurrences(occs)
    setSites(st)
    setPeople(ps)
  }

  useEffect(() => {
    refresh().catch((e) => setError(e instanceof Error ? e.message : 'Could not load timetable'))
  }, [])

  async function addOffering(e: FormEvent) {
    e.preventDefault()
    await api.createOffering(offeringForm)
    setOfferingForm({ name: '', code: '', kind: offeringForm.kind, default_start: '09:00', default_end: '10:00' })
    toast.push('ok', `${titleCase(org.group)} added`)
    await refresh()
  }

  async function addOccurrence(e: FormEvent) {
    e.preventDefault()
    await api.createOccurrence({
      offering_id: occForm.offering_id ? Number(occForm.offering_id) : undefined,
      title: occForm.title || undefined,
      day: occForm.day,
      start: occForm.start,
      end: occForm.end,
      overnight: occForm.overnight,
      kind: org.kernel === 'shift' ? 'shift' : org.kernel === 'visit' ? 'event' : 'session',
    })
    setOccForm({ ...occForm, title: '' })
    toast.push('ok', 'Meeting added')
    await refresh()
  }

  async function addSite(e: FormEvent) {
    e.preventDefault()
    await api.createSite({
      name: siteForm.name,
      lat: siteForm.lat ? Number(siteForm.lat) : null,
      lng: siteForm.lng ? Number(siteForm.lng) : null,
      radius_m: siteForm.radius_m ? Number(siteForm.radius_m) : 150,
    })
    setSiteForm({ name: '', lat: '', lng: '', radius_m: '150' })
    toast.push('ok', 'Site added')
    await refresh()
  }

  return (
    <div>
      <PageHeader
        eyebrow="Schedule"
        title={org.kernel === 'shift' ? 'Shifts and sites' : org.kernel === 'visit' ? 'Events and sites' : 'Timetable'}
        subtitle={`Create ${org.group}s, enroll ${org.subjectPlural}, and open today’s meetings for the kiosk.`}
      />
      {error ? <div className="mb-4"><Alert kind="error">{error}</Alert></div> : null}

      <section className={`${cardClass} p-5`}>
        <h2 className="text-sm font-semibold text-ink">{titleCase(org.group)}s</h2>
        <form onSubmit={(e) => void addOffering(e)} className="mt-3 grid gap-3 md:grid-cols-5">
          <input className={inputClass} placeholder="Name" value={offeringForm.name} onChange={(e) => setOfferingForm((f) => ({ ...f, name: e.target.value }))} required />
          <input className={inputClass} placeholder="Code" value={offeringForm.code} onChange={(e) => setOfferingForm((f) => ({ ...f, code: e.target.value }))} />
          <input className={inputClass} placeholder="Start" value={offeringForm.default_start} onChange={(e) => setOfferingForm((f) => ({ ...f, default_start: e.target.value }))} />
          <input className={inputClass} placeholder="End" value={offeringForm.default_end} onChange={(e) => setOfferingForm((f) => ({ ...f, default_end: e.target.value }))} />
          <Button type="submit">Add</Button>
        </form>
        <ul className="mt-4 divide-y divide-line">
          {offerings.map((o) => (
            <li key={o.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
              <div>
                <span className="font-medium text-ink">{o.name}</span>
                {o.code ? <span className="text-muted"> · {o.code}</span> : null}
                <span className="text-muted"> · {o.enrolled} enrolled</span>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => setEnrollFor(o.id)}>
                  Enroll
                </Button>
                <Button
                  variant="ghost"
                  onClick={() =>
                    void api.deleteOffering(o.id).then(() => {
                      toast.push('ok', 'Archived')
                      return refresh()
                    })
                  }
                >
                  Archive
                </Button>
              </div>
            </li>
          ))}
        </ul>
        {enrollFor ? (
          <form
            className="mt-4 flex flex-wrap gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              void api.enrollInOffering(enrollFor, Number(enrollPerson)).then(() => {
                toast.push('ok', 'Enrolled')
                setEnrollPerson('')
                return refresh()
              })
            }}
          >
            <select className={inputClass} value={enrollPerson} onChange={(e) => setEnrollPerson(e.target.value)} required>
              <option value="">Select {org.subject}</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <Button type="submit">Add to class</Button>
            <Button type="button" variant="ghost" onClick={() => setEnrollFor(null)}>
              Done
            </Button>
          </form>
        ) : null}
      </section>

      <section className={`mt-6 ${cardClass} p-5`}>
        <h2 className="text-sm font-semibold text-ink">Today’s meetings</h2>
        <form onSubmit={(e) => void addOccurrence(e)} className="mt-3 grid gap-3 md:grid-cols-6">
          <select className={inputClass} value={occForm.offering_id} onChange={(e) => setOccForm((f) => ({ ...f, offering_id: e.target.value }))}>
            <option value="">No {org.group}</option>
            {offerings.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
          <input className={inputClass} placeholder="Title" value={occForm.title} onChange={(e) => setOccForm((f) => ({ ...f, title: e.target.value }))} />
          <input type="date" className={inputClass} value={occForm.day} onChange={(e) => setOccForm((f) => ({ ...f, day: e.target.value }))} required />
          <input className={inputClass} value={occForm.start} onChange={(e) => setOccForm((f) => ({ ...f, start: e.target.value }))} />
          <input className={inputClass} value={occForm.end} onChange={(e) => setOccForm((f) => ({ ...f, end: e.target.value }))} />
          <Button type="submit">Open meeting</Button>
          {org.kernel === 'shift' ? (
            <label className="flex items-center gap-2 text-sm text-ink md:col-span-6">
              <input type="checkbox" checked={occForm.overnight} onChange={(e) => setOccForm((f) => ({ ...f, overnight: e.target.checked }))} />
              Crosses midnight
            </label>
          ) : null}
        </form>
        <ul className="mt-4 divide-y divide-line">
          {occurrences.map((o) => (
            <li key={o.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
              <div>
                <span className="font-medium text-ink">{o.title}</span>
                <span className="text-muted">
                  {' '}
                  · {o.start}–{o.end} · {o.present}/{o.expected || 0}
                  {o.open ? ' · open' : ''}
                </span>
              </div>
              <Button variant="ghost" onClick={() => void api.deleteOccurrence(o.id).then(() => refresh())}>
                Remove
              </Button>
            </li>
          ))}
        </ul>
      </section>

      <section className={`mt-6 ${cardClass} p-5`}>
        <h2 className="text-sm font-semibold text-ink">Sites</h2>
        <p className="mt-1 text-sm text-muted">Field and shift check-ins can be locked to these geofences.</p>
        <form onSubmit={(e) => void addSite(e)} className="mt-3 grid gap-3 md:grid-cols-5">
          <input className={inputClass} placeholder="Name" value={siteForm.name} onChange={(e) => setSiteForm((f) => ({ ...f, name: e.target.value }))} required />
          <input className={inputClass} placeholder="Lat" value={siteForm.lat} onChange={(e) => setSiteForm((f) => ({ ...f, lat: e.target.value }))} />
          <input className={inputClass} placeholder="Lng" value={siteForm.lng} onChange={(e) => setSiteForm((f) => ({ ...f, lng: e.target.value }))} />
          <input className={inputClass} placeholder="Radius m" value={siteForm.radius_m} onChange={(e) => setSiteForm((f) => ({ ...f, radius_m: e.target.value }))} />
          <Button type="submit">Add site</Button>
        </form>
        <ul className="mt-4 divide-y divide-line text-sm">
          {sites.map((s) => (
            <li key={s.id} className="flex items-center justify-between py-2">
              <span>
                {s.name}
                {s.is_default ? ' · default workplace' : ''}
                {s.lat != null ? ` · ${s.lat}, ${s.lng} · ${s.radius_m} m` : ''}
              </span>
              <Button variant="ghost" onClick={() => void api.deleteSite(s.id).then(() => refresh())}>
                Remove
              </Button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
