export type PipelineStage = {
  id: string
  label: string
  status: 'live' | 'planned'
}

export default function PipelineFlow({ stages }: { stages: PipelineStage[] }) {
  return (
    <div className="flex items-start" role="list" aria-label="Request lifecycle">
      {stages.map((stage, index) => {
        const next = stages[index + 1]
        const connectorLive = stage.status === 'live' && next?.status === 'live'
        return (
          <div key={stage.id} className="flex items-start" role="listitem">
            <div className="flex flex-col items-center gap-2 px-1">
              {stage.status === 'live' ? (
                <span
                  aria-hidden="true"
                  className="h-3 w-3 animate-node-pulse rounded-full border-2 border-primary bg-background"
                  style={{ animationDelay: `${index * 0.35}s` }}
                  title="Punched: live today"
                />
              ) : (
                <span
                  aria-hidden="true"
                  className="h-3 w-3 border border-border bg-muted"
                  title="Undrafted: planned"
                />
              )}
              <span className="font-mono text-xs whitespace-nowrap text-foreground">{stage.label}</span>
              <span
                className={`text-[10px] tracking-wide uppercase ${
                  stage.status === 'live' ? 'text-success' : 'text-muted-foreground'
                }`}
              >
                {stage.status === 'live' ? 'LIVE' : 'PLANNED'}
              </span>
            </div>
            {next && (
              <div
                className={`relative mt-[5px] h-px w-10 sm:w-16 ${
                  connectorLive ? 'bg-primary/40' : 'border-t border-dashed border-border'
                }`}
              >
                {connectorLive && (
                  <span
                    aria-hidden="true"
                    className="animate-flow-move absolute top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-primary"
                    style={{ animationDelay: `${index * 0.35}s` }}
                  />
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
