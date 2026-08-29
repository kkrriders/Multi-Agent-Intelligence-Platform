import type { GuardrailEvent, RunEvent } from '@/lib/api'

const AGENT_BY_STEP: Record<string, string> = {
  worker_researcher: 'researcher',
  worker_executor: 'executor',
  verifier_check: 'verifier',
  tool_called: 'tool_runner',
  no_tool_used: 'tool_runner',
}

function turnOf(e: RunEvent): number {
  const t = e.payload?.turn
  return typeof t === 'number' ? t : 0
}

function agentForTurn(events: RunEvent[]): string {
  for (const step of ['worker_researcher', 'worker_executor', 'verifier_check', 'tool_called']) {
    if (events.some((e) => e.step_name === step)) return AGENT_BY_STEP[step]
  }
  return 'orchestrator'
}

type GuardrailRow = Pick<GuardrailEvent, 'phase' | 'kind' | 'outcome'> & { detail?: Record<string, unknown> }

export default function Timeline({
  events,
  guardrails = [],
}: {
  events: RunEvent[]
  guardrails?: GuardrailRow[]
}) {
  if (events.length === 0 && guardrails.length === 0) {
    return <p className="text-sm text-muted-foreground">No events yet.</p>
  }

  const setup = events.filter((e) => turnOf(e) === 0)
  const turns = [...new Set(events.map(turnOf).filter((t) => t >= 1))].sort((a, b) => a - b)
  const toolCalls = events.filter((e) => e.step_name === 'tool_called').length
  const lastVerify = [...events].reverse().find((e) => e.step_name === 'verifier_check')
  const verification =
    lastVerify === undefined ? 'unchecked' : lastVerify.payload?.supported ? 'verified' : 'unverified'
  const preGuards = guardrails.filter((g) => g.phase === 'pre')
  const postGuards = guardrails.filter((g) => g.phase === 'post')

  return (
    <div
      className="punch-corner-lg card-stack-shadow bg-card-stock p-4 text-card-stock-foreground"
      aria-label="Execution timeline"
    >
      <p className="mb-3 font-mono text-xs text-card-stock-muted">
        {turns.length} turn{turns.length === 1 ? '' : 's'} · {toolCalls} tool call
        {toolCalls === 1 ? '' : 's'} · {verification}
      </p>

      {(setup.length > 0 || preGuards.length > 0) && (
        <details open className="mb-2">
          <summary className="cursor-pointer font-mono text-sm">Setup</summary>
          <EventRows events={setup} />
          <GuardrailRows phase="pre" rows={preGuards} />
        </details>
      )}

      {turns.map((t) => {
        const inTurn = events.filter((e) => turnOf(e) === t)
        const k = inTurn.filter((e) => e.step_name === 'tool_called').length
        return (
          <details key={t} open className="mb-2">
            <summary className="cursor-pointer font-mono text-sm">
              Turn {t} · {agentForTurn(inTurn)} · {k} tool{k === 1 ? '' : 's'}
            </summary>
            <EventRows events={inTurn} />
          </details>
        )
      })}

      {postGuards.length > 0 && (
        <details open className="mb-2">
          <summary className="cursor-pointer font-mono text-sm">Guardrails (post)</summary>
          <GuardrailRows phase="post" rows={postGuards} />
        </details>
      )}
    </div>
  )
}

function GuardrailRows({ phase, rows }: { phase: 'pre' | 'post'; rows: GuardrailRow[] }) {
  if (rows.length === 0) return null
  return (
    <ol className="ml-3 border-l border-card-stock-muted/40 pl-3">
      {rows.map((g, i) => (
        <li key={`${phase}-${i}`} className="py-1">
          <p className="font-mono text-sm text-card-stock-foreground">
            guardrail_{phase} · {g.kind} · {g.outcome}
          </p>
          {g.detail && Object.keys(g.detail).length > 0 && (
            <pre className="mt-1 overflow-x-auto font-mono text-xs text-card-stock-muted">
              {JSON.stringify(g.detail, null, 2)}
            </pre>
          )}
        </li>
      ))}
    </ol>
  )
}

function EventRows({ events }: { events: RunEvent[] }) {
  return (
    <ol className="ml-3 border-l border-card-stock-muted/40 pl-3">
      {events.map((event) => (
        <li key={event.id} className="py-1">
          <p className="font-mono text-sm text-card-stock-foreground">{event.step_name}</p>
          <p className="font-mono text-xs text-card-stock-muted">
            {new Date(event.created_at).toLocaleTimeString()}
          </p>
          {Object.keys(event.payload ?? {}).length > 0 && (
            <pre className="mt-1 overflow-x-auto font-mono text-xs text-card-stock-muted">
              {JSON.stringify(event.payload, null, 2)}
            </pre>
          )}
        </li>
      ))}
    </ol>
  )
}
