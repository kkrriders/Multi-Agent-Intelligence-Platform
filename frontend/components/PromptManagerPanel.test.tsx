import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const listPromptTemplates = vi.fn()
const createPromptTemplate = vi.fn()
const updatePromptTemplate = vi.fn()
const listPromptTemplateVersions = vi.fn()
const runTemplateTest = vi.fn()

vi.mock('@/lib/api', () => ({
  listPromptTemplates,
  createPromptTemplate,
  updatePromptTemplate,
  listPromptTemplateVersions,
  runTemplateTest,
}))

const tpl = (over = {}) => ({
  id: 't1',
  name: 'greet',
  version: 1,
  body: 'Hi {{name}}',
  variables: ['name'],
  version_count: 1,
  created_at: '2026-01-01T00:00:00Z',
  ...over,
})
const ver1 = { id: 'v1', version: 1, body: 'Hi {{name}}', variables: ['name'], created_at: '2026-01-01T00:00:00Z' }

describe('PromptManagerPanel', () => {
  it('lists templates and shows the selected body + variables', async () => {
    listPromptTemplates.mockResolvedValue([tpl()])
    listPromptTemplateVersions.mockResolvedValue([ver1])
    const { default: P } = await import('./PromptManagerPanel')
    render(<P projectId="p1" />)
    await waitFor(() => expect(screen.getByText(/greet/)).toBeInTheDocument())
    await waitFor(() => expect(screen.getByDisplayValue('Hi {{name}}')).toBeInTheDocument())
    expect(screen.getByLabelText(/var name/i)).toBeInTheDocument()
  })

  it('creates a template', async () => {
    listPromptTemplates.mockResolvedValue([])
    createPromptTemplate.mockResolvedValue(tpl())
    const { default: P } = await import('./PromptManagerPanel')
    render(<P projectId="p1" />)
    await waitFor(() => expect(listPromptTemplates).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: /new template/i }))
    fireEvent.change(screen.getByLabelText(/template name/i), { target: { value: 'greet' } })
    fireEvent.change(screen.getByLabelText(/template body/i), { target: { value: 'Hi {{name}}' } })
    fireEvent.click(screen.getByRole('button', { name: /^create$/i }))
    await waitFor(() =>
      expect(createPromptTemplate).toHaveBeenCalledWith('p1', { name: 'greet', body: 'Hi {{name}}' })
    )
  })

  it('saves a new version', async () => {
    listPromptTemplates.mockResolvedValue([tpl()])
    listPromptTemplateVersions.mockResolvedValue([ver1])
    updatePromptTemplate.mockResolvedValue({
      id: 'v2',
      version: 2,
      body: 'Hello {{name}}',
      variables: ['name'],
      created_at: '2026-01-02T00:00:00Z',
    })
    const { default: P } = await import('./PromptManagerPanel')
    render(<P projectId="p1" />)
    await waitFor(() => expect(screen.getByDisplayValue('Hi {{name}}')).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText(/template body/i), { target: { value: 'Hello {{name}}' } })
    fireEvent.click(screen.getByRole('button', { name: /save as new version/i }))
    await waitFor(() => expect(updatePromptTemplate).toHaveBeenCalledWith('t1', { body: 'Hello {{name}}' }))
  })

  it('runs a test with the entered variables', async () => {
    listPromptTemplates.mockResolvedValue([tpl()])
    listPromptTemplateVersions.mockResolvedValue([ver1])
    runTemplateTest.mockResolvedValue({ id: 'r1', status: 'completed', output: 'Hi World', events: [], citations: [] })
    const { default: P } = await import('./PromptManagerPanel')
    render(<P projectId="p1" />)
    await waitFor(() => expect(screen.getByLabelText(/var name/i)).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText(/var name/i), { target: { value: 'World' } })
    fireEvent.click(screen.getByRole('button', { name: /run test/i }))
    await waitFor(() => expect(runTemplateTest).toHaveBeenCalledWith('p1', 't1', { name: 'World' }))
    await waitFor(() => expect(screen.getByText('Hi World')).toBeInTheDocument())
  })
})
