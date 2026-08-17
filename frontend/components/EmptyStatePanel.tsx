type Props = {
  title: string
  phase: number
  description: string
}

export default function EmptyStatePanel({ title, phase, description }: Props) {
  return (
    <div className="punch-corner-lg card-stack-shadow flex flex-col gap-4 border border-border bg-card p-8">
      <div className="flex items-center gap-3">
        <h2 className="font-heading text-xl font-bold uppercase">{title}</h2>
        <span className="text-xs tracking-wide text-muted-foreground uppercase">Phase {phase}</span>
      </div>
      <p className="text-sm text-muted-foreground">{description}</p>
      <div className="flex items-center gap-2 border border-dashed border-border px-4 py-3">
        <span aria-hidden="true" className="h-2.5 w-2.5 border border-border bg-muted" />
        <span className="text-xs tracking-wide text-muted-foreground uppercase">Undrafted — not built yet</span>
      </div>
    </div>
  )
}
