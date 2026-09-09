import type { ReactNode } from 'react'

type Props = {
  label: string
  value: ReactNode
  hint?: string
  tone?: 'default' | 'ok' | 'warn' | 'bad'
}

const tones = {
  default: 'text-ink',
  ok: 'text-emerald-600 dark:text-emerald-400',
  warn: 'text-amber-600 dark:text-amber-400',
  bad: 'text-rose-600 dark:text-rose-400',
}

export function MetricCard({ label, value, hint, tone = 'default' }: Props) {
  return (
    <div className="rounded-2xl border border-line bg-panel p-5 shadow-[0_1px_2px_rgba(0,0,0,0.06)] transition hover:shadow-md">
      <div className="text-xs font-semibold uppercase tracking-wider text-muted">{label}</div>
      <div className={`mt-2 text-3xl font-semibold tracking-tight ${tones[tone]}`}>{value}</div>
      {hint ? <div className="mt-1 text-xs text-muted">{hint}</div> : null}
    </div>
  )
}
