'use client'

export type WorkspaceTab =
  | 'chat'
  | 'tools'
  | 'prompt-manager'
  | 'knowledge-hub'
  | 'memory-explorer'
  | 'guardrails'
  | 'evaluation'
  | 'observability'
  | 'cost-analytics'
  | 'deployment'
  | 'settings'

const TABS: { id: WorkspaceTab; label: string }[] = [
  { id: 'chat', label: 'Playground' },
  { id: 'tools', label: 'Tool Manager' },
  { id: 'prompt-manager', label: 'Prompt Manager' },
  { id: 'knowledge-hub', label: 'Knowledge Hub' },
  { id: 'memory-explorer', label: 'Memory Explorer' },
  { id: 'guardrails', label: 'Guardrails' },
  { id: 'evaluation', label: 'Evaluation' },
  { id: 'observability', label: 'Observability' },
  { id: 'cost-analytics', label: 'Cost Analytics' },
  { id: 'deployment', label: 'Deployment' },
  { id: 'settings', label: 'Settings' },
]

type Props = {
  active: WorkspaceTab
  onSelect: (tab: WorkspaceTab) => void
}

export default function WorkspaceNav({ active, onSelect }: Props) {
  return (
    <nav className="punch-corner-lg card-stack-shadow flex w-56 shrink-0 flex-col gap-1 self-start border border-border bg-card p-3">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onSelect(tab.id)}
          className={`px-3 py-2 text-left text-sm transition-colors ${active === tab.id ? 'font-bold text-primary' : 'text-muted-foreground hover:text-foreground'}`}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  )
}
