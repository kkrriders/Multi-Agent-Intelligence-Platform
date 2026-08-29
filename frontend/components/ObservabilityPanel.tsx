'use client'

import { useEffect, useState } from 'react'
import { listProjectRuns, type Run } from '@/lib/api'
import TraceView from './TraceView'

function totalSecs(run: Run): string {
  const ev = run.events ?? []
  if (ev.length < 2) return '—'
  const ms = Date.parse(ev[ev.length - 1].created_at) - Date.parse(ev[0].created_at)
  return `${(ms / 1000).toFixed(1)}s`
}

function turnCount(run: Run): number {
  return new Set(
    (run.events ?? [])
      .map((e) => e.payload?.turn)
      .filter((t): t is number => typeof t === 'number' && t >= 1)
  ).size
}

function toolCount(run: Run): number {
  return (run.events ?? []).filter((e) => e.step_name === 'tool_called').length
}

function guardrailGlyph(run: Run): string {
  const outs = (run.guardrails ?? []).map((g) => g.outcome)
  if (outs.length === 0) return ''
  if (outs.includes('blocked')) return '⛔'
  if (outs.includes('masked') || outs.includes('warned')) return '⚠'
  return '✓'
}

export default function ObservabilityPanel({ projectId }: { projectId: string }) {
  const [runs, setRuns] = useState<Run[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listProjectRuns(projectId)
      .then((list) => {
        setRuns(list)
        setSelectedId(list[0]?.id ?? null)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load runs'))
  }, [projectId])

  const selected = runs.find((r) => r.id === selectedId) ?? null

  if (error) return <p className="text-sm text-destructive">{error}</p>
  if (runs.length === 0) return <p className="text-sm text-muted-foreground">No runs yet.</p>

  return (
    <div className="flex flex-col gap-4 sm:flex-row">
      <ul className="flex shrink-0 flex-col gap-1 sm:w-72">
        {runs.map((run) => (
          <li key={run.id}>
            <button
              type="button"
              onClick={() => setSelectedId(run.id)}
              className={`w-full border border-border p-2 text-left font-mono text-xs ${
                run.id === selectedId ? 'border-primary font-bold' : 'hover:bg-muted'
              }`}
            >
              <span className={run.status === 'completed' ? '' : 'text-destructive'}>
                {run.id.slice(0, 8)} · {run.status}
              </span>
              <br />
              {totalSecs(run)} · {turnCount(run)}t · {toolCount(run)} tool · {guardrailGlyph(run)}
            </button>
          </li>
        ))}
      </ul>
      <div className="min-w-0 flex-1">{selected && <TraceView run={selected} />}</div>
    </div>
  )
}
