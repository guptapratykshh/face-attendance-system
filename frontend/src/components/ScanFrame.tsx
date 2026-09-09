type Props = {
  active?: boolean
  tone?: 'idle' | 'ok' | 'bad'
}

const tones = {
  idle: 'border-white/70 text-white',
  ok: 'border-emerald-400 text-emerald-300',
  bad: 'border-rose-400 text-rose-300',
}

export function ScanFrame({ active = true, tone = 'idle' }: Props) {
  return (
    <div className={`pointer-events-none absolute inset-0 ${tones[tone]}`}>
      <div className="absolute inset-[10%] rounded-[46%] border-2 shadow-[0_0_0_999px_rgba(0,0,0,0.28)]" />
      <div className="absolute left-[12%] top-[12%] h-7 w-7 border-l-2 border-t-2" />
      <div className="absolute right-[12%] top-[12%] h-7 w-7 border-r-2 border-t-2" />
      <div className="absolute bottom-[12%] left-[12%] h-7 w-7 border-b-2 border-l-2" />
      <div className="absolute bottom-[12%] right-[12%] h-7 w-7 border-b-2 border-r-2" />
      {active ? <div className="scan-line" /> : null}
    </div>
  )
}
