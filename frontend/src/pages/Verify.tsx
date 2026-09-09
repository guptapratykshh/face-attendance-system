import { useState } from 'react'
import { api } from '../api/client'
import type { FaceInfo, VerifyResponse } from '../api/types'
import { FaceBoxOverlay } from '../components/FaceBoxOverlay'
import { ImageDropzone } from '../components/ImageDropzone'
import { ScoreGauge } from '../components/ScoreGauge'
import { WebcamCapture } from '../components/WebcamCapture'
import { Button, LabTabs, PageHeader } from '../components/ui'

export function VerifyPage() {
  const [a, setA] = useState<File | null>(null)
  const [b, setB] = useState<File | null>(null)
  const [target, setTarget] = useState<'a' | 'b'>('a')
  const [result, setResult] = useState<VerifyResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function run() {
    if (!a || !b) return
    setBusy(true)
    setError(null)
    try {
      setResult(await api.verify(a, b))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'verify failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <PageHeader title="Compare two faces" subtitle="Used to test the matcher. Employees check in from Check in, not here." />
      <LabTabs />
      <p className="mb-4 text-sm text-muted">Decision uses the FAR=1e-3 threshold.</p>

      <div className="mt-6 grid md:grid-cols-2 gap-4">
        <ImageDropzone label="Image A" file={a} onFile={setA} />
        <ImageDropzone label="Image B" file={b} onFile={setB} />
      </div>

      <div className="mt-4 grid md:grid-cols-2 gap-4">
        <div>
          <div className="mb-2 flex gap-2 text-sm">
            <button
              type="button"
              className={target === 'a' ? 'text-ink font-medium' : 'text-muted'}
              onClick={() => setTarget('a')}
            >
              Capture → A
            </button>
            <button
              type="button"
              className={target === 'b' ? 'text-ink font-medium' : 'text-muted'}
              onClick={() => setTarget('b')}
            >
              Capture → B
            </button>
          </div>
          <WebcamCapture onCapture={(f) => (target === 'a' ? setA(f) : setB(f))} />
        </div>
        <div className="flex flex-col justify-end gap-3">
          <Button disabled={!a || !b || busy} onClick={() => void run()}>
            {busy ? 'Comparing…' : 'Compare'}
          </Button>
          {error ? <p className="text-rose-600 dark:text-rose-400 text-sm">{error}</p> : null}
          {result ? (
            <ScoreGauge similarity={result.similarity} threshold={result.threshold} match={result.match} />
          ) : null}
        </div>
      </div>

      {result && a && b ? (
        <div className="mt-6 grid md:grid-cols-2 gap-4">
          <Preview file={a} face={result.face_a} />
          <Preview file={b} face={result.face_b} />
        </div>
      ) : null}
    </div>
  )
}

function Preview({ file, face }: { file: File; face: FaceInfo }) {
  const src = URL.createObjectURL(file)
  return <FaceBoxOverlay src={src} face={face} />
}
