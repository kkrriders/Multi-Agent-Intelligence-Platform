import type { ReactNode } from 'react'

/**
 * Shared Operate-surface primitives for the workspace panels: a teaching empty
 * state, a loading skeleton, a standardized error/info notice, and a section
 * wrapper — all in The Loom's punch-card vocabulary.
 */

/** Punch-card motif: a short row of holes, drawn (no icon font, no emoji). */
function PunchRow({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 96 16" aria-hidden="true" className={className} fill="none">
      {[8, 26, 44, 62, 80].map((cx, i) => (
        <circle
          key={cx}
          cx={cx}
          cy="8"
          r={i === 2 ? 5 : 3.5}
          className={i === 2 ? 'stroke-primary' : 'stroke-muted-foreground'}
          strokeWidth="1.5"
        />
      ))}
    </svg>
  )
}

/** Empty state that teaches the panel: what lands here, why it matters, how to start. */
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="punch-corner-lg card-stack-shadow flex flex-col items-start gap-4 border border-border bg-card p-8">
      <PunchRow className="h-4 w-24" />
      <div className="flex flex-col gap-1.5">
        <h3 className="font-heading text-lg font-bold tracking-wide uppercase">{title}</h3>
        <p className="max-w-prose text-sm text-muted-foreground">{description}</p>
      </div>
      {action}
    </div>
  )
}

/** Bordered callout for a panel-level error (default) or an informational note. */
export function Notice({
  children,
  variant = 'error',
}: {
  children: ReactNode
  variant?: 'error' | 'info'
}) {
  const cls =
    variant === 'error'
      ? 'border-destructive/40 bg-destructive/10 text-destructive'
      : 'border-border bg-muted/40 text-muted-foreground'
  return (
    <p
      role={variant === 'error' ? 'alert' : 'status'}
      className={`punch-corner border px-3 py-2 text-sm ${cls}`}
    >
      {children}
    </p>
  )
}

/** Pulsing placeholder rows shown while a panel's data is loading. */
export function SkeletonRows({ rows = 3 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2" aria-hidden="true" data-testid="skeleton">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="punch-corner h-14 animate-pulse border border-border bg-card"
          style={{ opacity: 1 - i * 0.18 }}
        />
      ))}
    </div>
  )
}

/** Section heading + optional right-aligned control, consistent across panels. */
export function PanelSection({
  title,
  right,
  children,
}: {
  title: string
  right?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-sm font-bold tracking-wide uppercase">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  )
}
