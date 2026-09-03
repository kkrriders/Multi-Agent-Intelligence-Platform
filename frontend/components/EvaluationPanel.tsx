'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  createEvalDataset,
  getEvalDataset,
  listEvalDatasets,
  listEvalRuns,
  runEval,
  type EvalDataset,
  type EvalDatasetDetail,
  type EvalRun,
  type EvalRunSummary,
} from '@/lib/api'
import { EmptyState, Notice, SkeletonRows } from './PanelKit'

const MAX_ROWS = 20
const pct = (x: number) => `${Math.round(x * 100)}%`

type Row = { input: string; expected: string }

export default function EvaluationPanel({ projectId }: { projectId: string }) {
  const [datasets, setDatasets] = useState<EvalDataset[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<EvalDatasetDetail | null>(null)
  const [runs, setRuns] = useState<EvalRunSummary[]>([])
  const [lastRun, setLastRun] = useState<EvalRun | null>(null)
  const [running, setRunning] = useState(false)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [rows, setRows] = useState<Row[]>([{ input: '', expected: '' }])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listEvalDatasets(projectId)
      .then((list) => {
        setDatasets(list)
        setSelectedId((cur) => cur ?? list[0]?.id ?? null)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load datasets'))
      .finally(() => setLoading(false))
  }, [projectId])

  useEffect(() => {
    if (!selectedId) return
    // Reset the last-run view when the selected dataset changes, then load the
    // new dataset's detail and run history.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLastRun(null)
    getEvalDataset(selectedId).then(setDetail).catch(() => setDetail(null))
    listEvalRuns(selectedId).then(setRuns).catch(() => setRuns([]))
  }, [selectedId])

  async function handleCreate() {
    const items = rows
      .map((r) => ({ input: r.input.trim(), expected: r.expected.trim() }))
      .filter((r) => r.input && r.expected)
    if (!name.trim() || items.length === 0) return
    try {
      const created = await createEvalDataset(projectId, { name, items })
      setDatasets((prev) => [
        {
          id: created.id,
          name: created.name,
          item_count: created.item_count,
          latest_run: null,
          created_at: created.created_at,
        },
        ...prev,
      ])
      setSelectedId(created.id)
      setCreating(false)
      setName('')
      setRows([{ input: '', expected: '' }])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create dataset')
    }
  }

  async function handleRun() {
    if (!detail) return
    setRunning(true)
    setError(null)
    try {
      const run = await runEval(detail.id)
      setLastRun(run)
      setRuns((prev) => [run, ...prev])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Evaluation run failed')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 sm:flex-row">
      <div className="flex shrink-0 flex-col gap-2 sm:w-64">
        {error && <Notice>{error}</Notice>}
        <Button size="sm" variant="outline" onClick={() => setCreating((c) => !c)}>
          New dataset
        </Button>
        {creating && (
          <div className="punch-corner flex flex-col gap-2 border border-border bg-card p-3">
            <label
              htmlFor="ds-name"
              className="text-xs tracking-wide text-muted-foreground uppercase"
            >
              Dataset name
            </label>
            <Input id="ds-name" value={name} onChange={(e) => setName(e.target.value)} />
            {rows.map((row, i) => (
              <div key={i} className="flex flex-col gap-1">
                <Input
                  aria-label={`input ${i + 1}`}
                  placeholder="input"
                  value={row.input}
                  onChange={(e) =>
                    setRows((prev) =>
                      prev.map((r, j) => (j === i ? { ...r, input: e.target.value } : r))
                    )
                  }
                />
                <Input
                  aria-label={`expected ${i + 1}`}
                  placeholder="expected"
                  value={row.expected}
                  onChange={(e) =>
                    setRows((prev) =>
                      prev.map((r, j) => (j === i ? { ...r, expected: e.target.value } : r))
                    )
                  }
                />
              </div>
            ))}
            <Button
              size="sm"
              variant="outline"
              disabled={rows.length >= MAX_ROWS}
              onClick={() => setRows((prev) => [...prev, { input: '', expected: '' }])}
            >
              Add row
            </Button>
            <Button size="sm" onClick={handleCreate}>
              Create dataset
            </Button>
          </div>
        )}
        {loading ? (
          <SkeletonRows rows={2} />
        ) : (
          <ul className="flex flex-col gap-1">
            {datasets.map((d) => (
              <li key={d.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(d.id)}
                  className={`punch-corner-sm w-full border p-2 text-left font-mono text-xs transition-colors ${
                    d.id === selectedId
                      ? 'border-primary bg-muted font-bold'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  {d.name} · {d.item_count} items
                  <br />
                  <span className="text-muted-foreground">
                    {d.latest_run
                      ? `acc ${pct(d.latest_run.accuracy)} · halluc ${pct(
                          d.latest_run.hallucination_rate
                        )}`
                      : 'not run'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {detail ? (
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <div className="punch-corner-lg card-stack-shadow border border-border bg-card p-4">
            <div className="mb-2 flex items-center gap-3">
              <Button size="sm" onClick={handleRun} disabled={running}>
                {running ? 'Running…' : 'Run evaluation'}
              </Button>
              {lastRun && (
                <span className="font-mono text-xs">
                  accuracy {pct(lastRun.accuracy)} · hallucination {pct(lastRun.hallucination_rate)} ·
                  mean {lastRun.mean_score.toFixed(2)}
                </span>
              )}
            </div>
            <ul className="flex flex-col gap-1">
              {detail.items.map((it, i) => {
                const result = lastRun?.results.find((r) => r.item_id === it.id)
                return (
                  <li key={it.id} className="font-mono text-xs">
                    <span className="text-muted-foreground">
                      {i + 1}. {it.input} → {it.expected}
                    </span>
                    {result && (
                      <div className="ml-3">
                        score {result.score.toFixed(2)} ·{' '}
                        <span className={result.hallucinated ? 'text-destructive' : ''}>
                          {result.hallucinated ? 'hallucinated' : 'no hallucination'}
                        </span>{' '}
                        · <span>{result.reason}</span>
                        <details>
                          <summary className="cursor-pointer">output</summary>
                          <pre className="overflow-x-auto text-muted-foreground">{result.output}</pre>
                        </details>
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          </div>

          {runs.length > 0 && (
            <div className="punch-corner-lg card-stack-shadow border border-border bg-card p-4">
              <p className="mb-2 text-xs tracking-wide text-muted-foreground uppercase">Past runs</p>
              <ul className="flex flex-col gap-1 font-mono text-xs">
                {runs.map((r) => (
                  <li key={r.id}>
                    acc {pct(r.accuracy)} · halluc {pct(r.hallucination_rate)} · mean{' '}
                    {r.mean_score.toFixed(2)} ·{' '}
                    {r.created_at ? new Date(r.created_at).toLocaleString() : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        !creating && (
          <div className="min-w-0 flex-1">
            <EmptyState
              title="No dataset selected"
              description="Create a golden dataset of input / expected pairs, then Run evaluation to score each answer with a Groq judge. You get per-item score and hallucination flags plus aggregate accuracy, hallucination rate, and mean score."
            />
          </div>
        )
      )}
    </div>
  )
}
