import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const listConversations = vi.fn().mockResolvedValue([
  { id: 'conv-1', project_id: 'project-1', title: 'Thread A', created_at: '2026-01-01T00:00:00Z' },
])
const searchMemories = vi.fn().mockResolvedValue([
  {
    score: 0.87,
    project_id: 'project-1',
    conversation_id: 'conv-1',
    run_id: 'run-1',
    input: 'The launch codeword is Bluebird.',
    output: 'ok',
  },
])

vi.mock('@/lib/api', () => ({ listConversations, searchMemories }))

describe('MemoryExplorerPanel', () => {
  it('lists conversations and shows semantic search results', async () => {
    const { default: MemoryExplorerPanel } = await import('./MemoryExplorerPanel')
    render(<MemoryExplorerPanel projectId="project-1" />)

    await waitFor(() => expect(screen.getByText('Thread A')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText(/search memory/i), { target: { value: 'launch codeword' } })
    fireEvent.click(screen.getByRole('button', { name: /search/i }))

    await waitFor(() => expect(searchMemories).toHaveBeenCalledWith('project-1', 'launch codeword'))
    await waitFor(() => expect(screen.getByText(/Bluebird/)).toBeInTheDocument())
  })

  it('teaches the panel before a search and when there are no conversations', async () => {
    listConversations.mockResolvedValueOnce([])
    const { default: MemoryExplorerPanel } = await import('./MemoryExplorerPanel')
    render(<MemoryExplorerPanel projectId="project-1" />)

    await waitFor(() => expect(screen.getByText(/no conversations yet/i)).toBeInTheDocument())
    expect(screen.getByText(/search this project/i)).toBeInTheDocument()
  })
})
