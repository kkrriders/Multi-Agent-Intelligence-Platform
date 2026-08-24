import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const listConversations = vi.fn().mockResolvedValue([])
const createConversation = vi.fn().mockResolvedValue({
  id: 'conv-1',
  project_id: 'project-1',
  title: 'New conversation',
  created_at: '2026-01-01T00:00:00Z',
})
const listConversationRuns = vi.fn().mockResolvedValue([])
const createRun = vi.fn().mockResolvedValue({
  id: 'run-1',
  status: 'completed',
  output: 'pong',
  events: [{ id: 'e1', step_name: 'run_started', payload: {}, created_at: '2026-01-01T00:00:00Z' }],
})

vi.mock('@/lib/api', () => ({ listConversations, createConversation, listConversationRuns, createRun }))

describe('ChatPanel', () => {
  it('sends input and displays the response and timeline', async () => {
    const { default: ChatPanel } = await import('./ChatPanel')
    render(<ChatPanel projectId="project-1" />)

    await waitFor(() => expect(listConversations).toHaveBeenCalledWith('project-1'))

    fireEvent.change(screen.getByLabelText(/message/i), { target: { value: 'ping' } })
    fireEvent.click(screen.getByRole('button', { name: /send/i }))

    await waitFor(() => expect(createConversation).toHaveBeenCalledWith('project-1'))
    await waitFor(() => expect(createRun).toHaveBeenCalledWith('conv-1', 'ping'))
    await waitFor(() => expect(screen.getByText('pong')).toBeInTheDocument())
    expect(screen.getByText('run_started')).toBeInTheDocument()
  })

  it('renders citations returned with a run', async () => {
    createRun.mockResolvedValueOnce({
      id: 'run-2',
      status: 'completed',
      output: 'Bluebird',
      events: [],
      citations: [{ index: 1, document_id: 'doc-1', filename: 'launch-notes.txt', content: 'The codeword is Bluebird.' }],
    })

    const { default: ChatPanel } = await import('./ChatPanel')
    render(<ChatPanel projectId="project-1" />)

    fireEvent.change(screen.getByLabelText(/message/i), { target: { value: 'what is the codeword' } })
    fireEvent.click(screen.getByRole('button', { name: /send/i }))

    await waitFor(() => expect(screen.getByText(/launch-notes\.txt/i)).toBeInTheDocument())
  })
})
