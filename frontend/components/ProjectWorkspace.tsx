'use client'

import { useState } from 'react'
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

export default function ProjectWorkspace({ projectId }: { projectId: string }) {
  const [tab, setTab] = useState<WorkspaceTab>('chat')

  return (
    <div className="flex flex-col gap-8 sm:flex-row">
      <WorkspaceNav active={tab} onSelect={setTab} />
      <div className="min-w-0 flex-1">
        {tab === 'chat' && (
          <>
            <h1 className="font-heading text-2xl font-bold uppercase mb-6">Chat / Run</h1>
            <ChatPanel projectId={projectId} />
          </>
        )}
        {tab === 'tools' && (
          <>
            <h1 className="font-heading text-2xl font-bold uppercase mb-6">Tool Manager</h1>
            <ToolManagerPanel projectId={projectId} />
          </>
        )}
        {tab === 'knowledge-hub' && (
          <>
            <h1 className="font-heading text-2xl font-bold uppercase mb-6">Knowledge Hub</h1>
            <KnowledgeHubPanel projectId={projectId} />
          </>
        )}
        {tab === 'memory-explorer' && (
          <>
            <h1 className="font-heading text-2xl font-bold uppercase mb-6">Memory Explorer</h1>
            <MemoryExplorerPanel projectId={projectId} />
          </>
        )}
        {tab === 'guardrails' && (
          <>
            <h1 className="font-heading text-2xl font-bold uppercase mb-6">Guardrails</h1>
            <GuardrailsPanel projectId={projectId} />
          </>
        )}
        {tab === 'observability' && (
          <>
            <h1 className="font-heading text-2xl font-bold uppercase mb-6">Observability</h1>
            <ObservabilityPanel projectId={projectId} />
          </>
        )}
        {tab === 'prompt-manager' && (
          <>
            <h1 className="font-heading text-2xl font-bold uppercase mb-6">Prompt Manager</h1>
            <PromptManagerPanel projectId={projectId} />
          </>
        )}
        {tab === 'evaluation' && (
          <>
            <h1 className="font-heading text-2xl font-bold uppercase mb-6">Evaluation</h1>
            <EvaluationPanel projectId={projectId} />
          </>
        )}
        {tab === 'cost-analytics' && (
          <>
            <h1 className="font-heading text-2xl font-bold uppercase mb-6">Cost Analytics</h1>
            <CostAnalyticsPanel projectId={projectId} />
          </>
        )}
        {tab === 'settings' && (
          <>
            <h1 className="font-heading text-2xl font-bold uppercase mb-6">Settings</h1>
            <SettingsPanel projectId={projectId} />
          </>
        )}
        {tab === 'deployment' && (
          <>
            <h1 className="font-heading text-2xl font-bold uppercase mb-6">Deployment</h1>
            <DeploymentPanel />
          </>
        )}
      </div>
    </div>
  )
}
