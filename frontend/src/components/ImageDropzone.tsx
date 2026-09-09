import { useState } from 'react'

type Props = {
  label: string
  file: File | null
  onFile: (file: File | null) => void
}

export function ImageDropzone({ label, file, onFile }: Props) {
  const [over, setOver] = useState(false)
  const preview = file ? URL.createObjectURL(file) : null
  return (
    <label
      className={`flex min-h-48 cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed p-4 ${
        over ? 'border-teal-500 bg-teal-50 dark:bg-teal-950/40' : 'border-line bg-panel'
      }`}
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setOver(false)
        const f = e.dataTransfer.files[0]
        if (f) onFile(f)
      }}
    >
      <span className="text-xs font-semibold uppercase tracking-wider text-muted">{label}</span>
      {preview ? (
        <img src={preview} alt="" className="max-h-40 rounded object-contain" />
      ) : (
        <span className="text-sm text-muted">Drop a photo here, or click to browse</span>
      )}
      <input type="file" accept="image/*" className="hidden" onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
    </label>
  )
}
