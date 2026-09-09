import { BrandMark } from './Logo'

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string
  body: string
  action?: React.ReactNode
}) {
  return (
    <div className="px-4 py-14 text-center">
      <BrandMark className="mx-auto h-14 w-14 text-muted opacity-40" />
      <div className="mt-4 text-sm font-medium text-ink">{title}</div>
      <p className="mt-1 text-sm text-muted">{body}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton rounded-xl ${className}`} />
}

export function MetricSkeleton() {
  return (
    <div className="rounded-2xl border border-line bg-panel p-5">
      <Skeleton className="h-3 w-20" />
      <Skeleton className="mt-3 h-8 w-16" />
      <Skeleton className="mt-2 h-3 w-28" />
    </div>
  )
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-11 w-full" />
      ))}
    </div>
  )
}
