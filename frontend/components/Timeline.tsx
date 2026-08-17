import type { RunEvent } from '@/lib/api'

export default function Timeline({ events }: { events: RunEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-muted-foreground">No events yet.</p>
  }

  return (
    <ol
      className="punch-corner-lg card-stack-shadow bg-card-stock p-4 text-card-stock-foreground"
      aria-label="Execution timeline"
    >
      {events.map((event, index) => (
        <li key={event.id} className="flex gap-3">
          <div className="flex flex-col items-center">
            <div className="mt-1 h-2 w-2 shrink-0 rounded-full border-2 border-primary-deep bg-card-stock" />
            {index !== events.length - 1 && <div className="w-px flex-1 bg-card-stock-muted/40" />}
          </div>
          <div className={index !== events.length - 1 ? 'pb-4' : ''}>
            <p className="font-mono text-sm text-card-stock-foreground">{event.step_name}</p>
            <p className="font-mono text-xs text-card-stock-muted">
              {new Date(event.created_at).toLocaleTimeString()}
            </p>
          </div>
        </li>
      ))}
    </ol>
  )
}
