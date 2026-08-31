'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  deleteAlertRule,
  getLimits,
  listAlertEvents,
  listAlertRules,
  patchAlertRule,
  saveAlertRule,
  type AlertEvent,
  type AlertKind,
  type AlertRule,
} from '@/lib/api'
import { EmptyState, Notice, PanelSection } from './PanelKit'

const KINDS: { kind: AlertKind; label: string; unit: string; hasWindow: boolean }[] = [
  { kind: 'error_rate', label: 'Error rate', unit: 'fraction 0–1', hasWindow: true },
  { kind: 'daily_spend', label: 'Daily spend', unit: 'USD', hasWindow: false },
  { kind: 'p95_latency', label: 'p95 latency', unit: 'ms', hasWindow: true },
]

type Draft = { threshold: string; window_n: string; webhook_url: string }

function draftFrom(rule?: AlertRule): Draft {
  return {
    threshold: rule ? String(rule.threshold) : '',
    window_n: rule ? String(rule.window_n) : '20',
    webhook_url: rule?.webhook_url ?? '',
  }
}

export default function SettingsPanel({ projectId }: { projectId: string }) {
  const [limit, setLimit] = useState<number | null>(null)
  const [rules, setRules] = useState<Record<string, AlertRule>>({})
  const [drafts, setDrafts] = useState<Record<string, Draft>>(() =>
    Object.fromEntries(KINDS.map((k) => [k.kind, draftFrom()]))
  )
  const [events, setEvents] = useState<AlertEvent[]>([])
  const [error, setError] = useState<string | null>(null)

  function applyRules(rs: AlertRule[], evs: AlertEvent[]) {
    const byKind: Record<string, AlertRule> = {}
    for (const r of rs) byKind[r.kind] = r
    setRules(byKind)
    // only refill drafts for kinds that actually have a saved rule — never
    // clobber a threshold the user is in the middle of typing for a new one
    setDrafts((prev) => {
      const next = { ...prev }
      for (const k of KINDS) if (byKind[k.kind]) next[k.kind] = draftFrom(byKind[k.kind])
      return next
    })
    setEvents(evs)
  }

  async function refresh() {
    const [rs, evs] = await Promise.all([listAlertRules(projectId), listAlertEvents(projectId)])
    applyRules(rs, evs)
  }

  useEffect(() => {
    getLimits()
      .then((l) => setLimit(l.run_rate_limit_per_min))
      .catch(() => setLimit(null))
    Promise.all([listAlertRules(projectId), listAlertEvents(projectId)])
      .then(([rs, evs]) => applyRules(rs, evs))
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load settings'))
  }, [projectId])

  function set(kind: string, field: keyof Draft, value: string) {
    setDrafts((d) => ({ ...d, [kind]: { ...(d[kind] ?? draftFrom()), [field]: value } }))
  }

  async function save(kind: AlertKind, hasWindow: boolean) {
    setError(null)
    const d = drafts[kind] ?? draftFrom()
    try {
      await saveAlertRule(projectId, {
        kind,
        threshold: Number(d.threshold),
        window_n: hasWindow ? Number(d.window_n) : undefined,
        webhook_url: d.webhook_url.trim() || null,
      })
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save rule')
    }
  }

  async function toggle(rule: AlertRule) {
    await patchAlertRule(projectId, rule.id, { enabled: !rule.enabled })
    await refresh()
  }

  async function remove(rule: AlertRule) {
    await deleteAlertRule(projectId, rule.id)
    await refresh()
  }

  return (
    <div className="flex flex-col gap-8">
      {error && <Notice>{error}</Notice>}

      <PanelSection title="Rate limit">
        <div className="punch-corner border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">
            {limit == null
              ? 'Server-enforced per-user run rate limit.'
              : `Max ${limit} runs per minute per user, enforced by the server.`}
          </p>
        </div>
      </PanelSection>

      <PanelSection title="Alert rules">
        <div className="flex flex-col gap-3">
          {KINDS.map(({ kind, label, unit, hasWindow }) => {
            const rule = rules[kind]
            const d = drafts[kind] ?? draftFrom()
            return (
              <div
                key={kind}
                className="punch-corner card-stack-shadow flex flex-col gap-2 border border-border bg-card p-3 sm:flex-row sm:items-end sm:gap-3"
              >
                <div className="min-w-32">
                  <p className="font-mono text-sm">{label}</p>
                  <p className="font-mono text-[0.65rem] text-muted-foreground">
                    {unit}
                    {rule && (
                      <span className={rule.enabled ? ' text-primary' : ' text-muted-foreground'}>
                        {' '}
                        · {rule.enabled ? 'on' : 'off'}
                      </span>
                    )}
                  </p>
                </div>
                <label className="flex flex-col gap-1 font-mono text-[0.65rem] text-muted-foreground">
                  threshold
                  <Input
                    aria-label={`${label} threshold`}
                    value={d.threshold}
                    onChange={(e) => set(kind, 'threshold', e.target.value)}
                  />
                </label>
                {hasWindow && (
                  <label className="flex flex-col gap-1 font-mono text-[0.65rem] text-muted-foreground">
                    window (runs)
                    <Input
                      aria-label={`${label} window`}
                      className="w-20"
                      value={d.window_n}
                      onChange={(e) => set(kind, 'window_n', e.target.value)}
                    />
                  </label>
                )}
                <label className="flex flex-1 flex-col gap-1 font-mono text-[0.65rem] text-muted-foreground">
                  webhook URL (optional)
                  <Input
                    aria-label={`${label} webhook`}
                    value={d.webhook_url}
                    onChange={(e) => set(kind, 'webhook_url', e.target.value)}
                  />
                </label>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    aria-label={`Save ${label}`}
                    onClick={() => save(kind, hasWindow)}
                  >
                    Save
                  </Button>
                  {rule && (
                    <>
                      <Button variant="outline" size="sm" onClick={() => toggle(rule)}>
                        {rule.enabled ? 'Disable' : 'Enable'}
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        aria-label={`Delete ${label}`}
                        onClick={() => remove(rule)}
                      >
                        Delete
                      </Button>
                    </>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </PanelSection>

      <PanelSection title="Alert history">
        {events.length === 0 ? (
          <EmptyState
            title="No alerts yet"
            description="When an enabled rule breaches its threshold after a run, it is recorded here (and its webhook fires, if set). Rate-limit hits also land in this log."
          />
        ) : (
          <div className="punch-corner-lg overflow-x-auto border border-border bg-card p-4">
            <table className="w-full font-mono text-xs">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="text-left font-normal">When</th>
                  <th className="text-left font-normal">Kind</th>
                  <th className="text-right font-normal">Observed</th>
                  <th className="text-right font-normal">Threshold</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id} className="border-t border-border">
                    <td className="py-1">{new Date(e.created_at).toLocaleString()}</td>
                    <td>{e.kind}</td>
                    <td className="text-right">{e.observed}</td>
                    <td className="text-right">{e.threshold}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </PanelSection>
    </div>
  )
}
