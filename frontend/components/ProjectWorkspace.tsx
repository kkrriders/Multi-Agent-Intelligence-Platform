'use client'

import { useState, type ReactNode } from 'react'
import WorkspaceNav, { type WorkspaceTab } from './WorkspaceNav'
import ChatPanel from './ChatPanel'
import ToolManagerPanel from './ToolManagerPanel'
import MemoryExplorerPanel from './MemoryExplorerPanel'
import KnowledgeHubPanel from './KnowledgeHubPanel'
import GuardrailsPanel from './GuardrailsPanel'
import ObservabilityPanel from './ObservabilityPanel'
import PromptManagerPanel from './PromptManagerPanel'
import EvaluationPanel from './EvaluationPanel'
import CostAnalyticsPanel from './CostAnalyticsPanel'
import SettingsPanel from './SettingsPanel'
import DeploymentPanel from './DeploymentPanel'

type PanelMeta = { title: string; subtitle: string; render: (projectId: string) => ReactNode }

const PANELS: Record<WorkspaceTab, PanelMeta> = {
  chat: {
    title: 'Playground',
    subtitle:
      'Hand-test prompts and agents here — this is a console, not the production chat. Your users reach the same pipeline through the REST API. Every send runs the full lifecycle and returns the woven execution record.',
    render: (id) => <ChatPanel projectId={id} />,
  },
  tools: {
    title: 'Tool Manager',
    subtitle:
      'Register GET REST endpoints the agent may call mid-run. GET only — the model never sets the URL or headers.',
    render: (id) => <ToolManagerPanel projectId={id} />,
  },
  'prompt-manager': {
    title: 'Prompt Manager',
    subtitle:
      'Versioned, append-only prompt templates. A run renders the latest version from its {{variables}}.',
    render: (id) => <PromptManagerPanel projectId={id} />,
  },
  'knowledge-hub': {
    title: 'Knowledge Hub',
    subtitle:
      'Upload documents for chunking, embedding, and cited hybrid retrieval during runs.',
    render: (id) => <KnowledgeHubPanel projectId={id} />,
  },
  'memory-explorer': {
    title: 'Memory Explorer',
    subtitle:
      "Browse conversation threads and search this project's run history by meaning, not keywords.",
    render: (id) => <MemoryExplorerPanel projectId={id} />,
  },
  guardrails: {
    title: 'Guardrails',
    subtitle:
      'Prompt-injection screening and PII masking, with a log of every intervention on a run.',
    render: (id) => <GuardrailsPanel projectId={id} />,
  },
  evaluation: {
    title: 'Evaluation',
    subtitle:
      'Score answers against golden datasets with an LLM judge for accuracy and hallucination.',
    render: (id) => <EvaluationPanel projectId={id} />,
  },
  observability: {
    title: 'Observability',
    subtitle:
      'Every run across the project, each one expandable into its full step-by-step trace.',
    render: (id) => <ObservabilityPanel projectId={id} />,
  },
  'cost-analytics': {
    title: 'Cost Analytics',
    subtitle:
      'Token and USD cost per run, aggregated by model and by day, with estimated cache savings.',
    render: (id) => <CostAnalyticsPanel projectId={id} />,
  },
  deployment: {
    title: 'Deployment',
    subtitle:
      'Deploy-target config and a build/publish history for the hardened container images.',
    render: () => <DeploymentPanel />,
  },
  settings: {
    title: 'Settings',
    subtitle:
      'Per-user run rate limits and per-project alert rules for error rate, spend, and latency.',
    render: (id) => <SettingsPanel projectId={id} />,
  },
}

export default function ProjectWorkspace({ projectId }: { projectId: string }) {
  const [tab, setTab] = useState<WorkspaceTab>('chat')
  const panel = PANELS[tab]

  return (
    <div className="flex flex-col gap-8 sm:flex-row">
      <WorkspaceNav active={tab} onSelect={setTab} />
      <div className="min-w-0 flex-1">
        <header className="mb-6">
          <h1 className="font-heading text-2xl font-bold uppercase">{panel.title}</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{panel.subtitle}</p>
        </header>
        {panel.render(projectId)}
      </div>
    </div>
  )
}
