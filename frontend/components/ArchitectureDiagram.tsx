'use client'

import { useState } from 'react'

type Node = { id: string; label: string; body: string }

const CHILDREN: Node[] = [
  { id: 'knowledge', label: 'Knowledge', body: 'Hybrid retrieval over your own documents, with citations attached to every answer that used them.' },
  { id: 'memory', label: 'Memory', body: 'Session memory scoped to a conversation, long-term semantic recall in Qdrant once a run is over.' },
  { id: 'tools', label: 'Tools', body: 'Any REST endpoint, registered once and callable inside a run — request, response, and latency all visible.' },
  { id: 'guardrails', label: 'Guardrails', body: 'Catches a prompt injection or a malformed output before it ships, not after.' },
  { id: 'models', label: 'Models', body: 'Model calls routed through one gateway and accounted for like every other call in the run.' },
]

const RUNTIME: Node = { id: 'runtime', label: 'Agent Runtime', body: 'Coordinates every call in a run through one place that knows what happened — not five bolted-together services.' }
const SINK: Node = { id: 'sink', label: 'Evaluation + Trace', body: 'Every run scored against a golden dataset; every call written to a real, inspectable timeline.' }
const COST: Node = { id: 'cost', label: 'Cost Optimization', body: "Caching, context compression, and model routing, so a run's cost is a decision, not a surprise." }
const APP: Node = { id: 'app', label: 'AI Application', body: 'Your product — the surface your users actually see and talk to.' }

const ALL: Node[] = [APP, RUNTIME, ...CHILDREN, SINK, COST]

export default function ArchitectureDiagram() {
  const [active, setActive] = useState<string | null>(null)

  const active2 = ALL.find((n) => n.id === active)
  // The trunk (AI Application -> Agent Runtime) sits on every path, so it stays lit regardless of hover.
  const childLit = (id: string) => active === null || active === id
  const sinkPath = active === null || active === 'sink' || CHILDREN.some((c) => c.id === active)
  const costPath = sinkPath || active === 'cost'

  return (
    <div className="punch-corner-lg card-stack-shadow border border-border bg-card p-6 sm:p-10">
      <div className="w-full min-w-0 overflow-x-auto">
        <div className="flex min-w-[560px] flex-col items-center sm:min-w-0">
          <DiagNode node={APP} lit onHover={setActive} />
          <Stem lit />
          <DiagNode node={RUNTIME} lit emphasized onHover={setActive} />

          <div className="relative mt-0 flex w-full justify-between px-[6%]">
            <div className="absolute top-8 right-[10%] left-[10%] h-px bg-border" aria-hidden="true" />
            <div
              className={`absolute bottom-8 right-[10%] left-[10%] h-px ${sinkPath ? 'bg-primary' : 'bg-border'}`}
              aria-hidden="true"
            />
            {CHILDREN.map((child) => {
              const lit = childLit(child.id)
              return (
                <div key={child.id} className="relative flex flex-col items-center gap-3 py-8">
                  <span
                    aria-hidden="true"
                    className={`absolute top-0 left-1/2 h-8 w-px -translate-x-1/2 ${lit ? 'bg-primary' : 'bg-border'}`}
                  />
                  <DiagNode node={child} lit={lit} small onHover={setActive} />
                  <span
                    aria-hidden="true"
                    className={`absolute bottom-0 left-1/2 h-8 w-px -translate-x-1/2 ${lit ? 'bg-primary' : 'bg-border'}`}
                  />
                </div>
              )
            })}
          </div>

          <Stem lit={sinkPath} />
          <DiagNode node={SINK} lit={sinkPath} onHover={setActive} />
          <Stem lit={costPath} />
          <DiagNode node={COST} lit={costPath} onHover={setActive} />
        </div>
      </div>

      <div className="mt-8 min-h-11 border-t border-border pt-4">
        <p className="text-sm text-muted-foreground">
          {active2 ? (
            <>
              <span className="font-heading font-bold text-foreground uppercase">{active2.label}. </span>
              {active2.body}
            </>
          ) : (
            'Hover or focus a node to see how it fits.'
          )}
        </p>
      </div>
    </div>
  )
}

function Stem({ lit = true }: { lit?: boolean }) {
  return <span aria-hidden="true" className={`h-8 w-px ${lit ? 'bg-primary' : 'bg-border'}`} />
}

function DiagNode({
  node,
  lit = true,
  emphasized,
  small,
  onHover,
}: {
  node: Node
  lit?: boolean
  emphasized?: boolean
  small?: boolean
  onHover: (id: string | null) => void
}) {
  return (
    <button
      type="button"
      onMouseEnter={() => onHover(node.id)}
      onMouseLeave={() => onHover(null)}
      onFocus={() => onHover(node.id)}
      onBlur={() => onHover(null)}
      onClick={() => onHover(node.id)}
      className={`punch-corner-sm border px-3 py-2 font-mono text-xs whitespace-nowrap transition-colors focus-visible:outline-none ${
        small ? '' : 'px-4 py-2.5'
      } ${
        lit
          ? 'border-primary bg-popover text-foreground'
          : 'border-border bg-card text-muted-foreground'
      } ${emphasized ? 'font-medium' : ''}`}
    >
      {node.label}
    </button>
  )
}
