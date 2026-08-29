import type { GuardrailEvent, Run, RunEvent } from '@/lib/api'

type Row = {
  key: string
  name: string
  at: number
  payload: Record<string, unknown>
  isError: boolean
}

function toRows(run: Run): Row[] {
  const events: Row[] = (run.events ?? []).map((e: RunEvent) => ({
    key: e.id,
    name: e.step_name,
    at: Date.parse(e.created_at),
    payload: e.payload ?? {},
    isError: e.step_name === 'error',
  }))
  const guards: Row[] = (run.guardrails ?? []).map((g: GuardrailEvent) => ({
    key: g.id,
    name: `guardrail_${g.phase}`,
    at: Date.parse(g.created_at),
    payload: { kind: g.kind, outcome: g.outcome, ...(g.detail ?? {}) },
    isError: false,
  }))
  return [...events, ...guards].sort((a, b) => a.at - b.at)
}

function fmt(ms: number): string {
  return `${(ms / 1000).toFixed(1)}s`
}

function guardrailSummary(run: Run): string {
  const outs = (run.guardrails ?? []).map((g) => g.outcome)
  if (outs.length === 0) return '—'
  if (outs.includes('blocked')) return '⛔ blocked'
  if (outs.includes('masked') || outs.includes('warned')) return '⚠'
  return '✓'
}

export default function TraceView({ run }: { run: Run }) {
  const rows = toRows(run)
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">No trace for this run.</p>
  }

  const deltas = rows.map((r, i) => (i === 0 ? 0 : r.at - rows[i - 1].at))
  const maxDelta = Math.max(1, ...deltas)
  const total = rows[rows.length - 1].at - rows[0].at
  const turns = new Set(
    (run.events ?? [])
      .map((e) => e.payload?.turn)
      .filter((t): t is number => typeof t === 'number' && t >= 1)
  ).size
  const tools = (run.events ?? []).filter((e) => e.step_name === 'tool_called').length

  return (
    <div
      className="punch-corner-lg card-stack-shadow bg-card-stock p-4 text-card-stock-foreground"
      aria-label="Run trace"
    >
      <p className="mb-3 font-mono text-xs text-card-stock-muted">
        {run.status} · {fmt(total)} · {turns} turn{turns === 1 ? '' : 's'} · {tools} tool
        {tools === 1 ? '' : 's'} · {guardrailSummary(run)}
      </p>

      <ol className="flex flex-col gap-1">
        {rows.map((row, i) => (
          <li key={row.key} className="font-mono text-xs">
            <div className="flex items-baseline gap-2">
              <span
                data-testid="trace-row-name"
                className={row.isError ? 'text-destructive' : 'text-card-stock-foreground'}
              >
                {row.name}
              </span>
              <span className="text-card-stock-muted">{i === 0 ? '' : `+${fmt(deltas[i])}`}</span>
              <span className="h-1 flex-1 bg-card-stock-muted/20">
                <span
                  className="block h-1 bg-card-stock-muted/60"
                  style={{ width: `${(deltas[i] / maxDelta) * 100}%` }}
                />
              </span>
            </div>
            {row.isError ? (
              <pre className="mt-0.5 overflow-x-auto text-destructive">
                {JSON.stringify(row.payload, null, 2)}
              </pre>
            ) : (
              Object.keys(row.payload).length > 0 && (
                <details className="mt-0.5">
                  <summary className="cursor-pointer text-card-stock-muted">payload</summary>
                  <pre className="overflow-x-auto text-card-stock-muted">
                    {JSON.stringify(row.payload, null, 2)}
                  </pre>
                </details>
              )
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}
