'use client'

import { useEffect, useState } from 'react'

type TraceLine = { t: string; event: string; detail?: string }

const SCRIPT: TraceLine[] = [
  { t: '14:32:08', event: 'run_started' },
  { t: '14:32:09', event: 'guardrail.check', detail: 'PASS' },
  { t: '14:32:10', event: 'retrieval.completed', detail: '4 docs' },
  { t: '14:32:11', event: 'memory.lookup', detail: '3 memories' },
  { t: '14:32:12', event: 'tool.called', detail: 'github.search' },
  { t: '14:32:13', event: 'agent.verify', detail: 'PASS' },
  { t: '14:32:14', event: 'evaluation.score', detail: '0.93' },
  { t: '14:32:14', event: 'response_generated' },
]

const STEP_MS = 650
const HOLD_MS = 2200

export default function RunTrace() {
  const [visible, setVisible] = useState(0)

  useEffect(() => {
    if (visible >= SCRIPT.length) {
      const reset = setTimeout(() => setVisible(0), HOLD_MS)
      return () => clearTimeout(reset)
    }
    const step = setTimeout(() => setVisible((n) => n + 1), STEP_MS)
    return () => clearTimeout(step)
  }, [visible])

  return (
    <div className="punch-corner card-stack-shadow border border-border bg-card p-5" aria-label="Simulated run trace">
      <p className="mb-3 flex items-center gap-2 text-[10px] tracking-wide text-muted-foreground uppercase">
        <span aria-hidden="true" className="h-2 w-2 rounded-full border-2 border-success" />
        Watch a run
      </p>
      <div className="font-mono text-xs leading-relaxed sm:text-[13px]" role="log">
        {SCRIPT.slice(0, visible).map((line, i) => (
          <div key={i} className="animate-trace-line flex gap-3 text-muted-foreground">
            <span className="shrink-0 text-card-stock-muted">{line.t}</span>
            <span className="text-foreground">{line.event}</span>
            {line.detail && <span className="text-success">{line.detail}</span>}
          </div>
        ))}
        <span
          aria-hidden="true"
          className="ml-[76px] inline-block h-3.5 w-1.5 translate-y-0.5 animate-node-pulse bg-primary"
        />
      </div>
    </div>
  )
}
