import type { SVGProps } from 'react'

type MarkProps = SVGProps<SVGSVGElement>

export function BrandMark({ className, ...props }: MarkProps) {
  return (
    <svg viewBox="0 0 64 64" fill="none" aria-hidden className={className} {...props}>
      <path
        d="M16 24v-6h8M40 18h8v6M16 40v6h8M40 46h8v-6"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="32" cy="32" r="18.5" stroke="currentColor" strokeWidth="1.7" opacity="0.55" />
      <circle cx="32" cy="32" r="14.2" stroke="currentColor" strokeWidth="1.2" opacity="0.85" />
      <path
        d="M32 21.2c-4.4 0-8 3.5-8 8.1 0 3.2 1.9 5.6 4.4 6.9-6.6 1.7-10.9 6.2-10.9 11.3h29c0-5.1-4.3-9.6-10.9-11.3 2.5-1.3 4.4-3.7 4.4-6.9 0-4.6-3.6-8.1-8-8.1z"
        fill="currentColor"
        opacity="0.92"
      />
      <line
        x1="11"
        y1="32"
        x2="53"
        y2="32"
        stroke="var(--ink)"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function Logo({
  compact = false,
  wordmark = true,
  ghost = false,
  subtitle,
  className = '',
}: {
  compact?: boolean
  wordmark?: boolean
  ghost?: boolean
  subtitle?: string
  className?: string
}) {
  const showText = wordmark && !compact
  return (
    <div className={`flex items-center gap-2.5 min-w-0 ${className}`}>
      <span
        className={
          ghost
            ? 'grid h-10 w-10 shrink-0 place-items-center'
            : 'grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-ink text-accent-fg shadow-sm'
        }
      >
        <BrandMark className={ghost ? 'h-10 w-10' : 'h-7 w-7'} />
      </span>
      {showText ? (
        <div className="min-w-0">
          <div className="text-base font-semibold tracking-tight leading-none">Sentinel</div>
          {subtitle ? (
            <div className="mt-0.5 text-[10px] uppercase tracking-[0.16em] text-current/55">{subtitle}</div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
