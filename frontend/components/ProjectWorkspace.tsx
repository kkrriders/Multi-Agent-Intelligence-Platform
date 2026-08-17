'use client'

import { useState } from 'react'
import WorkspaceNav, { type WorkspaceTab } from './WorkspaceNav'
import ChatPanel from './ChatPanel'
import ToolManagerPanel from './ToolManagerPanel'
import MemoryExplorerPanel from './MemoryExplorerPanel'
import EmptyStatePanel from './EmptyStatePanel'

const EMPTY_STATES: Record<string, { title: string; phase: number; description: string }> = {
  'prompt-manager': {
    title: 'Prompt Manager',
    phase: 2,
    description: 'Template library with variables, version history, and test-run.',
  },
  'knowledge-hub': {
    title: 'Knowledge Hub',
    phase: 1,
    description: 'Upload, indexing status, search, chunk inspection, citations.',
  },
  guardrails: {
    title: 'Guardrails',
    phase: 2,
    description: 'Policies, validation rules, violations log.',
  },
  evaluation: {
    title: 'Evaluation',
    phase: 2,
    description: 'Accuracy, hallucination rate, confidence, benchmark results.',
  },
  observability: {
    title: 'Observability',
    phase: 2,
    description: 'Trace viewer, retrieval path, tool calls, timings.',
  },
  'cost-analytics': {
    title: 'Cost Analytics',
    phase: 3,
    description: 'Token usage, model costs, cache hits/savings.',
  },
  deployment: {
    title: 'Deployment',
    phase: 3,
    description: 'Docker/cloud config, environments, deployment history.',
  },
  settings: {
    title: 'Settings',
    phase: 3,
    description: 'Project and account configuration.',
  },
}

export default function ProjectWorkspace({ projectId }: { projectId: string }) {
  const [tab, setTab] = useState<WorkspaceTab>('chat')
  const emptyState = EMPTY_STATES[tab]

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
        {tab === 'memory-explorer' && (
          <>
            <h1 className="font-heading text-2xl font-bold uppercase mb-6">Memory Explorer</h1>
            <MemoryExplorerPanel projectId={projectId} />
          </>
        )}
        {emptyState && <EmptyStatePanel {...emptyState} />}
      </div>
    </div>
  )
}
