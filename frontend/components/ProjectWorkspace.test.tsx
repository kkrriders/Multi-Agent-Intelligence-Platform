import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('./ChatPanel', () => ({ default: () => <div>chat-panel</div> }))
vi.mock('./ToolManagerPanel', () => ({ default: () => <div>tool-panel</div> }))
vi.mock('./MemoryExplorerPanel', () => ({ default: () => <div>memory-panel</div> }))
vi.mock('./KnowledgeHubPanel', () => ({ default: () => <div>knowledge-hub-panel</div> }))
vi.mock('./GuardrailsPanel', () => ({ default: () => <div>guardrails-panel</div> }))
vi.mock('./ObservabilityPanel', () => ({ default: () => <div>observability-panel</div> }))
vi.mock('./PromptManagerPanel', () => ({ default: () => <div>prompt-manager-panel</div> }))
vi.mock('./EvaluationPanel', () => ({ default: () => <div>evaluation-panel</div> }))

describe('ProjectWorkspace', () => {
  it('switches between Chat/Run, Tool Manager, and Memory Explorer panels', async () => {
    const { default: ProjectWorkspace } = await import('./ProjectWorkspace')
    render(<ProjectWorkspace projectId="p1" />)

    expect(screen.getByText('chat-panel')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /tool manager/i }))
    expect(screen.getByText('tool-panel')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /memory explorer/i }))
    expect(screen.getByText('memory-panel')).toBeInTheDocument()
  })

  it('renders the Prompt Manager panel for its tab', async () => {
    const { default: ProjectWorkspace } = await import('./ProjectWorkspace')
    render(<ProjectWorkspace projectId="p1" />)

    fireEvent.click(screen.getByRole('button', { name: /prompt manager/i }))
    expect(screen.getByText('prompt-manager-panel')).toBeInTheDocument()
  })

  it('shows an empty-state panel for a not-yet-built tab', async () => {
    const { default: ProjectWorkspace } = await import('./ProjectWorkspace')
    render(<ProjectWorkspace projectId="p1" />)

    fireEvent.click(screen.getByRole('button', { name: /cost analytics/i }))
    expect(screen.getByText(/token usage/i)).toBeInTheDocument()
  })
})
