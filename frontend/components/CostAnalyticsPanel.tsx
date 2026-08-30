'use client'

import { useEffect, useState } from 'react'
import { getProjectCost, type ProjectCost } from '@/lib/api'

const usd = (n: number) => `$${n.toFixed(4)}`
const int = (n: number) => n.toLocaleString()

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="punch-corner card-stack-shadow bg-card-stock p-3 text-card-stock-foreground">
      <p className="font-mono text-[0.65rem] uppercase tracking-wide text-card-stock-muted">{label}</p>
      <p className="font-heading text-xl font-bold">{value}</p>
      {note && <p className="font-mono text-[0.65rem] text-card-stock-muted">{note}</p>}
    </div>
  )
}

export default function CostAnalyticsPanel({ projectId }: { projectId: string }) {
  const [cost, setCost] = useState<ProjectCost | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getProjectCost(projectId)
      .then(setCost)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load cost analytics'))
  }, [projectId])

  if (error) return <p className="text-sm text-destructive">{error}</p>
  if (!cost) return <p className="text-sm text-muted-foreground">Loading cost analytics…</p>

  const { totals, by_model, daily, recent_runs } = cost
  if (totals.run_count === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No runs yet — cost data appears after your first run.
      </p>
    )
  }

  const maxDaily = Math.max(1e-9, ...daily.map((d) => d.cost_usd))
  const totalModelCost = Math.max(1e-9, by_model.reduce((s, m) => s + m.cost_usd, 0))

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        <Tile label="Total cost" value={usd(totals.cost_usd)} />
        <Tile
          label="Tokens (in / out)"
          value={`${int(totals.prompt_tokens)} / ${int(totals.completion_tokens)}`}
        />
        <Tile label="Runs" value={int(totals.run_count)} />
        <Tile
          label="Cache hits"
          value={`${totals.cached_run_count} of ${totals.run_count}`}
        />
        <Tile
          label="Est. cache savings"
          value={usd(totals.estimated_cache_savings_usd)}
          note="estimated"
        />
      </div>
      {totals.runs_missing_cost > 0 && (
        <p className="font-mono text-xs text-muted-foreground">
          {totals.runs_missing_cost} run{totals.runs_missing_cost === 1 ? '' : 's'} predate cost
          tracking and count as $0.
        </p>
      )}

      <section>
        <h2 className="font-heading text-sm font-bold uppercase mb-2">Daily cost · 30 days</h2>
        <div className="flex h-24 items-end gap-[2px]">
          {daily.map((d) => (
            <span
              key={d.date}
              data-testid="cost-daily-bar"
              title={`${d.date} · ${usd(d.cost_usd)} · ${d.run_count} run(s)`}
              className="flex-1 bg-primary/70"
              style={{ height: `${Math.max(2, (d.cost_usd / maxDaily) * 100)}%` }}
            />
          ))}
        </div>
        <div className="mt-1 flex justify-between font-mono text-[0.65rem] text-muted-foreground">
          <span>{daily[0]?.date}</span>
          <span>{daily[daily.length - 1]?.date}</span>
        </div>
      </section>

      <section>
        <h2 className="font-heading text-sm font-bold uppercase mb-2">By model</h2>
        <table className="w-full font-mono text-xs">
          <thead className="text-muted-foreground">
            <tr>
              <th className="text-left font-normal">Model</th>
              <th className="text-right font-normal">Calls</th>
              <th className="text-right font-normal">In / Out</th>
              <th className="text-right font-normal">Cost</th>
              <th className="text-right font-normal">%</th>
            </tr>
          </thead>
          <tbody>
            {by_model.map((m) => (
              <tr key={m.model} className="border-t border-border">
                <td className="py-1">{m.model}</td>
                <td className="text-right">{int(m.calls)}</td>
                <td className="text-right">
                  {int(m.prompt_tokens)} / {int(m.completion_tokens)}
                </td>
                <td className="text-right">{usd(m.cost_usd)}</td>
                <td className="text-right">{((m.cost_usd / totalModelCost) * 100).toFixed(0)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2 className="font-heading text-sm font-bold uppercase mb-2">Recent runs</h2>
        <table className="w-full font-mono text-xs">
          <thead className="text-muted-foreground">
            <tr>
              <th className="text-left font-normal">Run</th>
              <th className="text-left font-normal">When</th>
              <th className="text-left font-normal">Status</th>
              <th className="text-right font-normal">In / Out</th>
              <th className="text-right font-normal">Cost</th>
            </tr>
          </thead>
          <tbody>
            {recent_runs.map((r) => (
              <tr key={r.id} className="border-t border-border">
                <td className="py-1">{r.id.slice(0, 8)}</td>
                <td>{new Date(r.created_at).toLocaleString()}</td>
                <td className={r.status === 'completed' ? '' : 'text-destructive'}>
                  {r.status}
                  {r.cache_hit && <span className="ml-1 text-primary">· cached</span>}
                </td>
                <td className="text-right">
                  {int(r.prompt_tokens)} / {int(r.completion_tokens)}
                </td>
                <td className="text-right">{r.cache_hit ? '$0' : usd(r.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
