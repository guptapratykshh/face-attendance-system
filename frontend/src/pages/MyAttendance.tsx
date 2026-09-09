import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type { AttendanceRecord } from '../api/types'
import { Alert, Button, PageHeader } from '../components/ui'

function ymd(d: Date) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function MyAttendancePage() {
  const [rows, setRows] = useState<AttendanceRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [cursor, setCursor] = useState(() => new Date())

  useEffect(() => {
    api.myAttendance().then(setRows).catch((e) => setError(e.detail ?? String(e)))
  }, [])

  const year = cursor.getFullYear()
  const month = cursor.getMonth()
  const byDay = useMemo(() => {
    const map = new Map<string, AttendanceRecord>()
    for (const row of rows) {
      if (row.decision !== 'present') continue
      map.set(ymd(new Date(row.created_at)), row)
    }
    return map
  }, [rows])

  const first = new Date(year, month, 1)
  const startWeekday = first.getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells = Array.from({ length: startWeekday + daysInMonth }, (_, i) => {
    if (i < startWeekday) return null
    return i - startWeekday + 1
  })

  function downloadCsv() {
    const lines = ['date,in,out,result,late']
    for (const r of rows) {
      lines.push([new Date(r.created_at).toISOString(), r.created_at, r.checked_out_at ?? '', r.decision, String(r.late)].join(','))
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'my-attendance.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <PageHeader
        title="My days"
        subtitle="Green days are days you checked in. Amber means you arrived late."
        actions={<Button variant="secondary" onClick={downloadCsv}>Download CSV</Button>}
      />
      {error ? <Alert kind="error">{error}</Alert> : null}
      <div className="flex items-center gap-3">
        <Button variant="ghost" onClick={() => setCursor(new Date(year, month - 1, 1))}>Previous</Button>
        <div className="font-semibold text-ink">
          {cursor.toLocaleString(undefined, { month: 'long', year: 'numeric' })}
        </div>
        <Button variant="ghost" onClick={() => setCursor(new Date(year, month + 1, 1))}>Next</Button>
      </div>
      <div className="mt-4 grid grid-cols-7 gap-1.5 text-center text-xs">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
          <div key={d} className="py-1 font-medium text-muted">{d}</div>
        ))}
        {cells.map((day, i) => {
          if (day == null) return <div key={`e-${i}`} />
          const key = ymd(new Date(year, month, day))
          const hit = byDay.get(key)
          return (
            <div
              key={key}
              className={`rounded-xl border py-3 ${hit ? (hit.late ? 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300' : 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300') : 'border-line bg-panel text-muted'}`}
            >
              <div className="font-medium">{day}</div>
              {hit ? <div className="mt-1 text-[10px]">{hit.late ? 'late' : 'in'}</div> : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
