'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  listGuardrailEvents,
  listGuardrailPolicies,
  putGuardrailPolicy,
  type GuardrailEvent,
  type GuardrailPolicy,
} from '@/lib/api'
import { EmptyState, Notice, PanelSection, SkeletonRows } from './PanelKit'

const OUTCOME_CLASS: Record<string, string> = {
  blocked: 'text-destructive',
  masked: 'text-muted-foreground',
  warned: 'text-muted-foreground',
  pass: 'text-muted-foreground/60',
}

type CardState = { enabled: boolean; maxLength: string; blocklist: string }

function seed(policy: GuardrailPolicy): CardState {
  const cfg = policy.config as { max_length?: number; blocklist?: string[] }
  return {
    enabled: policy.enabled,
    maxLength: cfg.max_length != null ? String(cfg.max_length) : '',
    blocklist: (cfg.blocklist ?? []).join('\n'),
  }
}

export default function GuardrailsPanel({ projectId }: { projectId: string }) {
  const [policies, setPolicies] = useState<GuardrailPolicy[]>([])
  const [cards, setCards] = useState<Record<string, CardState>>({})
  const [events, setEvents] = useState<GuardrailEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listGuardrailPolicies(projectId)
      .then((list) => {
        setPolicies(list)
        setCards(Object.fromEntries(list.map((p) => [p.kind, seed(p)])))
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load policies'))
      .finally(() => setLoading(false))
    listGuardrailEvents(projectId)
      .then(setEvents)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load events'))
  }, [projectId])

  function patch(kind: string, next: Partial<CardState>) {
    setCards((prev) => ({ ...prev, [kind]: { ...prev[kind], ...next } }))
  }

  async function save(kind: string) {
    const card = cards[kind]
    const config: Record<string, unknown> = {}
    if (card.maxLength.trim()) config.max_length = Number(card.maxLength)
    const terms = card.blocklist
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean)
    if (terms.length > 0) config.blocklist = terms
    try {
      await putGuardrailPolicy(projectId, kind, { enabled: card.enabled, config })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save policy')
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {error && <Notice>{error}</Notice>}

      <Notice variant="info">
        Prompt-injection screening and PII masking always run on every request. The policies below
        add optional input constraints on top.
      </Notice>

      <PanelSection title="Policies">
        {loading ? (
          <SkeletonRows rows={2} />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {policies.map((policy) => {
              const card = cards[policy.kind] ?? { enabled: false, maxLength: '', blocklist: '' }
              return (
                <div
                  key={policy.kind}
                  className="punch-corner-lg card-stack-shadow flex flex-col gap-2 border border-border bg-card p-4"
                >
                  <p className="font-mono text-sm">{policy.kind}</p>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      aria-label={`enable ${policy.kind}`}
                      checked={card.enabled}
                      onChange={(e) => patch(policy.kind, { enabled: e.target.checked })}
                    />
                    enabled
                  </label>
                  <label
                    htmlFor={`${policy.kind}-max`}
                    className="text-xs tracking-wide text-muted-foreground uppercase"
                  >
                    Max length
                  </label>
                  <Input
                    id={`${policy.kind}-max`}
                    aria-label={`${policy.kind} max length`}
                    value={card.maxLength}
                    onChange={(e) => patch(policy.kind, { maxLength: e.target.value })}
                    inputMode="numeric"
                  />
                  <label
                    htmlFor={`${policy.kind}-blocklist`}
                    className="mt-1 text-xs tracking-wide text-muted-foreground uppercase"
                  >
                    Blocklist (one term per line)
                  </label>
                  <textarea
                    id={`${policy.kind}-blocklist`}
                    aria-label={`${policy.kind} blocklist`}
                    value={card.blocklist}
                    onChange={(e) => patch(policy.kind, { blocklist: e.target.value })}
                    rows={3}
                    className="punch-corner border border-border bg-background p-2 font-mono text-xs"
                  />
                  <Button className="mt-2 self-start" size="sm" onClick={() => save(policy.kind)}>
                    Save {policy.kind}
                  </Button>
                </div>
              )
            })}
          </div>
        )}
      </PanelSection>

      <PanelSection title="Violations log">
        {events.length === 0 ? (
          <EmptyState
            title="No guardrail events yet"
            description="Blocked prompt injections and masked PII are recorded here after runs, with the phase, the check that fired, and its outcome."
          />
        ) : (
          <div className="punch-corner-lg card-stack-shadow border border-border bg-card p-4">
            <ul className="flex flex-col gap-1">
              {events.map((ev) => (
                <li key={ev.id} className="font-mono text-xs">
                  <span className={OUTCOME_CLASS[ev.outcome] ?? ''}>
                    {ev.phase} · {ev.kind} · {ev.outcome}
                  </span>{' '}
                  <span className="text-muted-foreground/60">
                    {new Date(ev.created_at).toLocaleTimeString()}
                  </span>
                  {Object.keys(ev.detail ?? {}).length > 0 && (
                    <pre className="mt-0.5 overflow-x-auto text-muted-foreground">
                      {JSON.stringify(ev.detail, null, 2)}
                    </pre>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </PanelSection>
    </div>
  )
}
