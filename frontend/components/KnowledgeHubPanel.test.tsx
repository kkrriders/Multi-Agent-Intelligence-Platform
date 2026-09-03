import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const listDocuments = vi.fn().mockResolvedValue([])
const uploadDocument = vi.fn().mockResolvedValue({
  id: 'doc-1',
  project_id: 'project-1',
  filename: 'notes.txt',
  mime_type: 'text/plain',
  storage_path: 'project-1/doc-1/notes.txt',
  status: 'indexed',
  error: null,
  created_at: '2026-01-01T00:00:00Z',
})
const deleteDocument = vi.fn().mockResolvedValue(undefined)

vi.mock('@/lib/api', () => ({ listDocuments, uploadDocument, deleteDocument }))

describe('KnowledgeHubPanel', () => {
  it('uploads a file and shows it in the list', async () => {
    const { default: KnowledgeHubPanel } = await import('./KnowledgeHubPanel')
    render(<KnowledgeHubPanel projectId="project-1" />)

    await waitFor(() => expect(listDocuments).toHaveBeenCalledWith('project-1'))

    const file = new File(['hello'], 'notes.txt', { type: 'text/plain' })
    const input = screen.getByLabelText(/upload document/i) as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: /upload/i }))

    await waitFor(() => expect(uploadDocument).toHaveBeenCalledWith('project-1', file))
    await waitFor(() => expect(screen.getByText('notes.txt')).toBeInTheDocument())
    expect(screen.getByText('indexed')).toBeInTheDocument()
  })

  it('deletes a document from the list', async () => {
    listDocuments.mockResolvedValueOnce([
      {
        id: 'doc-1',
        project_id: 'project-1',
        filename: 'notes.txt',
        mime_type: 'text/plain',
        storage_path: 'project-1/doc-1/notes.txt',
        status: 'indexed',
        error: null,
        created_at: '2026-01-01T00:00:00Z',
      },
    ])
    const { default: KnowledgeHubPanel } = await import('./KnowledgeHubPanel')
    render(<KnowledgeHubPanel projectId="project-1" />)

    await waitFor(() => expect(screen.getByText('notes.txt')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /delete/i }))

    await waitFor(() => expect(deleteDocument).toHaveBeenCalledWith('project-1', 'doc-1'))
    await waitFor(() => expect(screen.queryByText('notes.txt')).not.toBeInTheDocument())
  })

  it('shows a teaching empty state when there are no documents', async () => {
    listDocuments.mockResolvedValueOnce([])
    const { default: KnowledgeHubPanel } = await import('./KnowledgeHubPanel')
    render(<KnowledgeHubPanel projectId="project-1" />)

    await waitFor(() => expect(screen.getByText(/no documents yet/i)).toBeInTheDocument())
  })
})
