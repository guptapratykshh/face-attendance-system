import { type FormEvent, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { AssistCitation, AssistMessage } from '../api/types'
import { Alert, Button, PageHeader, inputClass } from '../components/ui'

type Bubble = {
  role: 'user' | 'assistant'
  content: string
  citations?: AssistCitation[]
}

export function AssistPage() {
  const [history, setHistory] = useState<Bubble[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    api
      .assistHistory()
      .then((rows) =>
        setHistory(
          rows.map((r: AssistMessage) => ({
            role: r.role === 'assistant' ? 'assistant' : 'user',
            content: r.content,
            citations: r.citations,
          })),
        ),
      )
      .catch((e) => setError(e.detail ?? String(e)))
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history, busy])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const text = message.trim()
    if (!text || busy) return
    setBusy(true)
    setError(null)
    setMessage('')
    setHistory((h) => [...h, { role: 'user', content: text }])
    try {
      const res = await api.assistChat(text)
      setHistory((h) => [...h, { role: 'assistant', content: res.answer, citations: res.citations }])
    } catch (err: unknown) {
      const detail =
        typeof err === 'object' && err && 'detail' in err
          ? String((err as { detail: unknown }).detail)
          : String(err)
      setError(
        detail === 'llm_not_configured'
          ? 'Set FRS_LLM_API_KEY on the API to enable Assist.'
          : detail,
      )
    } finally {
      setBusy(false)
    }
  }

  const suggestions = ['Who is late today?', 'Who still needs to check in?', 'How does geofence work?']

  return (
    <div className="flex h-[calc(100dvh-8rem)] flex-col">
      <PageHeader
        eyebrow="Language modality"
        title="Assist"
        subtitle="Ask about today's attendance and people. Answers cite records — Assist never marks anyone present."
      />
      {error ? (
        <div className="mb-3">
          <Alert kind="error">{error}</Alert>
        </div>
      ) : null}
      <div className="mb-3 flex flex-wrap gap-2">
        {suggestions.map((s) => (
          <button
            key={s}
            type="button"
            className="rounded-full border border-line bg-panel px-3 py-1 text-xs text-muted hover:text-ink"
            onClick={() => setMessage(s)}
          >
            {s}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto rounded-2xl border border-line bg-soft/40 p-4">
        {history.length === 0 ? (
          <p className="text-sm text-muted">Try “Who is late today?” after people have checked in.</p>
        ) : null}
        {history.map((b, i) => (
          <div
            key={`${b.role}-${i}`}
            className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 ${
              b.role === 'user' ? 'ml-auto bg-ink text-accent-fg' : 'bg-panel text-ink ring-1 ring-line'
            }`}
          >
            <div className="whitespace-pre-wrap">{b.content}</div>
            {b.citations && b.citations.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {b.citations.map((c) => (
                  <span
                    key={`${c.type}-${c.id}`}
                    className="rounded-md bg-soft px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted"
                  >
                    {c.type} #{c.id}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
        {busy ? <p className="text-sm text-muted">Thinking…</p> : null}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={(e) => void onSubmit(e)} className="mt-3 flex gap-2">
        <input
          className={`flex-1 ${inputClass}`}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Ask about attendance…"
          disabled={busy}
        />
        <Button type="submit" disabled={busy || !message.trim()}>
          Send
        </Button>
      </form>
    </div>
  )
}
