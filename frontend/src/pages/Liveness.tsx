import { useState } from 'react'
import type { LivenessResponse } from '../api/types'
import { ScanFrame } from '../components/ScanFrame'
import { Button, LabTabs, PageHeader, StatusBadge, cardClass } from '../components/ui'
import { useWebcam } from '../hooks/useWebcam'
import { checkBlinkChallenge } from '../lib/helpers'

function num(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export function LivenessPage() {
  const cam = useWebcam()
  const [result, setResult] = useState<LivenessResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [hint, setHint] = useState('Start the camera, then run the blink check.')

  async function run() {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      if (!cam.ready) await cam.start()
      const { result: res } = await checkBlinkChallenge(cam, setHint)
      setResult(res)
      setHint(
        res.live
          ? 'Live person confirmed.'
          : 'That did not look live. A photo or a screen video should fail. Face the camera, wait, then blink.',
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Liveness check failed')
    } finally {
      setBusy(false)
    }
  }

  const earMin = num(result?.blink.min_ear) ?? num(result?.blink.min)
  const earMax = num(result?.blink.max_ear) ?? num(result?.blink.max)
  const blinkPct = earMin != null && earMax != null && earMax > 0 ? Math.min(100, Math.round((1 - earMin / Math.max(earMax, 0.01)) * 100)) : 0
  const liveTexture = Boolean(result?.texture.live)

  return (
    <div>
      <PageHeader
        title="Blink liveness"
        subtitle="Wait, then blink when asked. A still photo or a screen video should fail."
      />
      <LabTabs />
      <div className={`max-w-xl overflow-hidden ${cardClass}`}>
        <div className="relative">
          <video ref={cam.videoRef} className="w-full aspect-video bg-black object-cover" playsInline muted />
          {cam.ready ? <ScanFrame active={busy} tone={result ? (result.live ? 'ok' : 'bad') : 'idle'} /> : null}
        </div>
        <div className="p-5">
          {!cam.ready ? (
            <Button onClick={() => void cam.start()}>Start camera</Button>
          ) : (
            <Button disabled={busy} onClick={() => void run()}>
              {busy ? 'Watching for a blink…' : 'Run blink check'}
            </Button>
          )}
          <p className="mt-3 text-sm text-muted">{hint}</p>
          {error ? <p className="mt-2 text-sm text-rose-600 dark:text-rose-400">{error}</p> : null}
          {result ? (
            <div className="mt-4 rounded-xl bg-soft p-4 text-sm">
              <div className="flex items-center gap-2">
                <StatusBadge status={result.live ? 'live' : 'spoof'} />
                <span className={`font-semibold ${result.live ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                  {result.live ? 'Live' : 'Not live'}
                </span>
              </div>
              <div className="mt-4">
                <div className="flex justify-between text-xs text-muted">
                  <span>Blink</span>
                  <span>{blinkPct}%</span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-panel">
                  <div className={`h-full ${result.live ? 'bg-emerald-500' : 'bg-rose-500'}`} style={{ width: `${blinkPct}%` }} />
                </div>
              </div>
              <p className="mt-3 text-xs text-muted">
                Texture {liveTexture ? 'looks like a real face' : 'looks printed or screen-like'}.
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
