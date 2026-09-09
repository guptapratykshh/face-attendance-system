import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api/client'
import type { EvalReport, Health } from '../api/types'
import { MetricCard } from '../components/MetricCard'
import { LabTabs, PageHeader } from '../components/ui'
import { useTheme } from '../hooks/useTheme'

function pct(n: number) {
  return `${(n * 100).toFixed(2)}%`
}

export function DashboardPage() {
  const { theme } = useTheme()
  const [report, setReport] = useState<EvalReport | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.metrics(), api.health()])
      .then(([m, h]) => {
        setReport(m)
        setHealth(h)
      })
      .catch((e) => setError(e.detail ?? String(e)))
  }, [])

  const names = report ? Object.keys(report.results) : []
  const served = report?.served_encoder
  const servedRec = served ? report?.results[served] : undefined

  const rocData = servedRec
    ? servedRec.roc.far.map((far, i) => ({ far, tar: servedRec.roc.tar[i] }))
    : []

  const tarBars = names.flatMap((name) => {
    const rec = report!.results[name]
    return Object.entries(rec.tar_at_far).map(([far, p]) => ({
      name,
      far: `FAR=${far}`,
      tar: p.tar,
    }))
  })

  const grouped = ['0.01', '0.001', '0.0001'].map((far) => {
    const row: Record<string, string | number> = { far: `FAR=${far}` }
    for (const name of names) {
      row[name] = report!.results[name].tar_at_far[far]?.tar ?? 0
    }
    return row
  })

  const hist = servedRec?.score_histogram
  const histData =
    hist?.bin_centers.map((c, i) => ({
      cosine: Number(c.toFixed(3)),
      genuine: hist.genuine[i],
      impostor: hist.impostor[i],
    })) ?? []

  const palette = ['#14b8a6', '#818cf8', '#f59e0b', '#34d399']
  const genuine = '#34d399'
  const impostor = '#fb923c'
  const grid = theme === 'dark' ? '#3f3f46' : '#e4e4e7'
  const axis = theme === 'dark' ? '#a1a1aa' : '#71717a'
  const tooltipStyle = {
    background: theme === 'dark' ? '#18181b' : '#ffffff',
    border: `1px solid ${grid}`,
    borderRadius: 12,
    color: theme === 'dark' ? '#fafafa' : '#18181b',
  }

  return (
    <div>
      <PageHeader
        title="Recognition lab"
        subtitle="Accuracy on LFW View 2. The live check-in threshold is set at FAR = 1e-3."
      />
      <LabTabs />
      {error ? <p className="mt-4 text-rose-600 dark:text-rose-400">{error}</p> : null}

      <div className="mt-6 grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard label="Served encoder" value={served ?? '—'} hint={health?.device} />
        <MetricCard
          label="LFW accuracy"
          value={servedRec?.accuracy ? pct(servedRec.accuracy.mean) : '—'}
          hint={servedRec?.accuracy ? `± ${pct(servedRec.accuracy.std)} 10-fold` : undefined}
        />
        <MetricCard label="EER" value={servedRec ? pct(servedRec.eer) : '—'} />
        <MetricCard
          label="TAR @ FAR 1e-3"
          value={servedRec?.tar_at_far['0.001'] ? pct(servedRec.tar_at_far['0.001'].tar) : '—'}
          hint={
            servedRec?.tar_at_far['0.001']
              ? `thr ${servedRec.tar_at_far['0.001'].threshold.toFixed(4)}`
              : undefined
          }
        />
      </div>

      <div className="mt-8 grid lg:grid-cols-2 gap-6">
        <section className="rounded-2xl border border-line bg-panel p-4">
          <h2 className="text-sm font-medium text-ink mb-1">ROC (log FAR)</h2>
          <p className="mb-3 text-xs text-muted">How often the right person is accepted as the false-accept rate gets stricter.</p>
          <div className="h-64">
            <ResponsiveContainer>
              <LineChart>
                <CartesianGrid stroke={grid} />
                <XAxis
                  dataKey="far"
                  type="number"
                  scale="log"
                  domain={[0.0001, 1]}
                  tickFormatter={(v) => v.toExponential(0)}
                  stroke={axis}
                  tick={{ fill: axis, fontSize: 12 }}
                />
                <YAxis
                  domain={[0, 1]}
                  tickFormatter={(v) => `${Math.round(v * 100)}%`}
                  stroke={axis}
                  tick={{ fill: axis, fontSize: 12 }}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(v) => pct(Number(v ?? 0))}
                  labelFormatter={(v) => `FAR ${Number(v).toExponential(1)}`}
                />
                <Legend />
                {names.map((name, i) => {
                  const rec = report!.results[name]
                  const data = rec.roc.far.map((far, j) => ({ far, tar: rec.roc.tar[j], name }))
                  return (
                    <Line
                      key={name}
                      data={data}
                      dataKey="tar"
                      name={name}
                      stroke={palette[i % palette.length]}
                      dot={false}
                      strokeWidth={2}
                    />
                  )
                })}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="rounded-2xl border border-line bg-panel p-4">
          <h2 className="text-sm font-medium text-ink mb-1">TAR@FAR</h2>
          <p className="mb-3 text-xs text-muted">True-accept rate at fixed false-accept rates. Higher is better.</p>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={grouped}>
                <CartesianGrid stroke={grid} />
                <XAxis dataKey="far" stroke={axis} tick={{ fill: axis, fontSize: 12 }} />
                <YAxis
                  domain={[0, 1]}
                  tickFormatter={(v) => `${Math.round(v * 100)}%`}
                  stroke={axis}
                  tick={{ fill: axis, fontSize: 12 }}
                />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => pct(Number(v ?? 0))} />
                <Legend />
                {names.map((name, i) => (
                  <Bar key={name} dataKey={name} fill={palette[i % palette.length]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="rounded-2xl border border-line bg-panel p-4 lg:col-span-2">
          <h2 className="text-sm font-medium text-ink mb-1">
            Score distributions ({served ?? 'served encoder'})
          </h2>
          <p className="mb-3 text-xs text-muted">Genuine pairs should sit right of impostor pairs. Less overlap means easier matching.</p>
          <div className="h-64">
            <ResponsiveContainer>
              <LineChart data={histData}>
                <CartesianGrid stroke={grid} />
                <XAxis dataKey="cosine" stroke={axis} tick={{ fill: axis, fontSize: 12 }} />
                <YAxis stroke={axis} tick={{ fill: axis, fontSize: 12 }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend />
                <Line dataKey="genuine" stroke={genuine} dot={false} strokeWidth={2} />
                <Line dataKey="impostor" stroke={impostor} strokeDasharray="4 4" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      {rocData.length === 0 && tarBars.length === 0 ? (
        <p className="mt-6 text-muted text-sm">Run `python scripts/evaluate.py` to populate charts.</p>
      ) : null}
    </div>
  )
}
