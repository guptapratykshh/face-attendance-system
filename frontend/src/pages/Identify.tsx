import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { IdentifyResponse, Person } from '../api/types'
import { FaceBoxOverlay } from '../components/FaceBoxOverlay'
import { ImageDropzone } from '../components/ImageDropzone'
import { ScoreGauge } from '../components/ScoreGauge'
import { WebcamCapture } from '../components/WebcamCapture'
import { Button, LabTabs, PageHeader, StatusBadge, scoreClass } from '../components/ui'

export function IdentifyPage() {
  const [file, setFile] = useState<File | null>(null)
  const [people, setPeople] = useState<Person[]>([])
  const [result, setResult] = useState<IdentifyResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.listPersons().then(setPeople).catch(() => undefined)
  }, [])

  async function run() {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      setResult(await api.identify(file))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'identify failed')
    } finally {
      setBusy(false)
    }
  }

  const top = result?.matches[0]

  return (
    <div>
      <PageHeader title="Find who this is" subtitle={`Search ${people.length} enrolled people. This is a lab tool, not the employee check-in.`} />
      <LabTabs />
      <div className="mt-6 grid md:grid-cols-2 gap-4">
        <ImageDropzone label="Probe image" file={file} onFile={setFile} />
        <WebcamCapture onCapture={setFile} />
      </div>
      <Button disabled={!file || busy} className="mt-4" onClick={() => void run()}>
        {busy ? 'Searching…' : 'Identify'}
      </Button>
      {error ? <p className="mt-3 text-rose-600 dark:text-rose-400 text-sm">{error}</p> : null}
      {result && top ? (
        <div className="mt-6 grid md:grid-cols-2 gap-4">
          {file ? <FaceBoxOverlay src={URL.createObjectURL(file)} face={result.face} /> : null}
          <div>
            <ScoreGauge similarity={top.similarity} threshold={result.threshold} match={result.identified} />
            <ul className="mt-4 max-h-64 space-y-2 overflow-y-auto overscroll-contain pr-1">
              {result.matches.map((m, i) => {
                const hit = m.similarity >= result.threshold
                return (
                <li
                  key={m.person_id}
                  className={`flex justify-between rounded-xl border px-3 py-2 text-sm ${
                    i === 0 && result.identified
                      ? 'border-emerald-300 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/30'
                      : 'border-line bg-panel'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    {m.name}
                    {i === 0 ? <StatusBadge status={result.identified ? 'match' : 'no_match'} /> : null}
                  </span>
                  <span className={`mono ${scoreClass(m.similarity, hit)}`}>{m.similarity.toFixed(4)}</span>
                </li>
                )
              })}
            </ul>
            {result.gallery_size === 0 ? (
              <p className="mt-3 text-sm text-muted">Gallery is empty — enroll someone first.</p>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}
