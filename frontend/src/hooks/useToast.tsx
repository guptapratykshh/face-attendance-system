import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

type Kind = 'ok' | 'error' | 'info'
type Toast = { id: number; kind: Kind; message: string }

type ToastState = {
  push: (kind: Kind, message: string) => void
}

const ToastContext = createContext<ToastState | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([])
  const push = useCallback((kind: Kind, message: string) => {
    const id = Date.now() + Math.random()
    setItems((xs) => [...xs.slice(-4), { id, kind, message }])
    window.setTimeout(() => setItems((xs) => xs.filter((t) => t.id !== id)), 4200)
  }, [])
  const value = useMemo(() => ({ push }), [push])
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-6 right-6 z-50 flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            className={`toast-enter rounded-xl border px-4 py-3 text-sm shadow-lg ${
              t.kind === 'error'
                ? 'border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-800 dark:bg-rose-950 dark:text-rose-200'
                : t.kind === 'ok'
                  ? 'border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200'
                  : 'border-line bg-panel text-ink'
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
