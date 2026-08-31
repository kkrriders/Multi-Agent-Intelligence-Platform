'use client'

import { useEffect, useState } from 'react'
import { listProjectRuns, type Run } from '@/lib/api'
import { EmptyState, Notice, SkeletonRows } from './PanelKit'
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

function guardrailMark(run: Run): string {
  const outs = (run.guardrails ?? []).map((g) => g.outcome)
  if (outs.includes('blocked')) return 'blocked'
  if (outs.includes('masked') || outs.includes('warned')) return 'masked'
  return ''
}

export default function ObservabilityPanel({ projectId }: { projectId: string }) {
  const [runs, setRuns] = useState<Run[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listProjectRuns(projectId)
      .then((list) => {
        setRuns(list)
        setSelectedId(list[0]?.id ?? null)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load runs'))
      .finally(() => setLoading(false))
  }, [projectId])

  const selected = runs.find((r) => r.id === selectedId) ?? null

  if (error) return <Notice>{error}</Notice>
  if (loading) return <SkeletonRows rows={5} />
  if (runs.length === 0) {
    return (
      <EmptyState
        title="No runs yet"
        description="Every run across this project appears here, newest first. Select one to expand its full execution trace — graph steps, guardrail checks, tool I/O, retrieval, and per-step timing."
      />
    )
  }

  return (
    <div className="flex flex-col gap-4 sm:flex-row">
      <ul className="flex shrink-0 flex-col gap-1 sm:w-72">
        {runs.map((run) => {
          const mark = guardrailMark(run)
          return (
            <li key={run.id}>
              <button
                type="button"
                onClick={() => setSelectedId(run.id)}
                className={`punch-corner-sm w-full border p-2 text-left font-mono text-xs transition-colors ${
                  run.id === selectedId
                    ? 'border-primary bg-muted font-bold'
                    : 'border-border hover:bg-muted'
                }`}
              >
                <span className={run.status === 'completed' ? '' : 'text-destructive'}>
                  {run.id.slice(0, 8)} · {run.status}
                </span>
                <br />
                <span className="text-muted-foreground">
                  {totalSecs(run)} · {turnCount(run)}t · {toolCount(run)} tool
                  {mark && (
                    <span className={mark === 'blocked' ? ' text-destructive' : ''}> · {mark}</span>
                  )}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
      <div className="min-w-0 flex-1">{selected && <TraceView run={selected} />}</div>
    </div>
  )
}
