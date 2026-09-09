type Props = {
  similarity: number
  threshold: number
  match: boolean
}

export function ScoreGauge({ similarity, threshold, match }: Props) {
  const pct = Math.max(0, Math.min(100, ((similarity + 1) / 2) * 100))
  const thrPct = Math.max(0, Math.min(100, ((threshold + 1) / 2) * 100))
  return (
    <div className="rounded-2xl border border-line bg-panel p-4">
      <div className="flex justify-between text-sm">
        <span className="text-muted">Match score</span>
        <span className={`font-semibold ${match ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
          {similarity.toFixed(4)} {match ? 'Match' : 'No match'}
        </span>
      </div>
      <div className="mt-3 h-3 rounded-full bg-soft relative overflow-hidden">
        <div className={`h-full ${match ? 'bg-emerald-500' : 'bg-rose-400'}`} style={{ width: `${pct}%` }} />
        <div
          className="absolute top-0 h-full w-0.5 bg-teal-500"
          style={{ left: `${thrPct}%` }}
          title={`threshold ${threshold.toFixed(3)}`}
        />
      </div>
      <div className="mt-2 text-xs text-muted">Need {threshold.toFixed(4)} or higher</div>
    </div>
  )
}
