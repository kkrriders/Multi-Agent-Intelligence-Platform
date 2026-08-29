import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const listTools = vi.fn().mockResolvedValue([])
const createTool = vi.fn().mockResolvedValue({
  id: 't1',
  name: 'Echo',
  type: 'rest',
  config: {},
  permissions: {},
  created_at: '2026-01-01T00:00:00Z',
})
const invokeTool = vi.fn().mockResolvedValue({ status: 200, body: 'ok' })

vi.mock('@/lib/api', () => ({ listTools, createTool, invokeTool }))

describe('ToolManagerPanel', () => {
  it('registers a tool and shows it in the list', async () => {
    const { default: ToolManagerPanel } = await import('./ToolManagerPanel')
    render(<ToolManagerPanel projectId="project-1" />)

    await waitFor(() => expect(listTools).toHaveBeenCalledWith('project-1'))

    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Echo' } })
    fireEvent.change(screen.getByLabelText(/^url$/i), { target: { value: 'https://example.com' } })
    fireEvent.click(screen.getByRole('button', { name: /register tool/i }))

    await waitFor(() =>
      expect(createTool).toHaveBeenCalledWith('project-1', {
        name: 'Echo',
        type: 'rest',
        config: { url: 'https://example.com', method: 'GET' },
      })
    )
    await waitFor(() => expect(screen.getByText('Echo')).toBeInTheDocument())
  })

  it('tests a tool via the invoke endpoint and shows status and latency', async () => {
    listTools.mockResolvedValueOnce([
      { id: 't1', name: 'Echo', type: 'rest', config: {}, permissions: {}, created_at: '2026-01-01T00:00:00Z' },
    ])
    const { default: ToolManagerPanel } = await import('./ToolManagerPanel')
    render(<ToolManagerPanel projectId="project-1" />)

    await waitFor(() => expect(screen.getByText('Echo')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /test/i }))

    await waitFor(() => expect(invokeTool).toHaveBeenCalledWith('t1', {}))
    await waitFor(() => expect(screen.getByText('200')).toBeInTheDocument())
    await waitFor(() => expect(screen.getByText(/^\d+ms$/)).toBeInTheDocument())
  })

  it('sends parsed parameters JSON schema in the tool config', async () => {
    const { default: ToolManagerPanel } = await import('./ToolManagerPanel')
    render(<ToolManagerPanel projectId="project-1" />)

    await waitFor(() => expect(listTools).toHaveBeenCalledWith('project-1'))

    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Weather' } })
    fireEvent.change(screen.getByLabelText(/^url$/i), { target: { value: 'https://api.example.com/weather' } })
    fireEvent.change(screen.getByLabelText(/parameters \(json schema\)/i), {
      target: { value: '{"type":"object","properties":{"city":{"type":"string"}}}' },
    })
    fireEvent.click(screen.getByRole('button', { name: /register tool/i }))

    await waitFor(() =>
      expect(createTool).toHaveBeenCalledWith('project-1', {
        name: 'Weather',
        type: 'rest',
        config: {
          url: 'https://api.example.com/weather',
          method: 'GET',
          parameters: { type: 'object', properties: { city: { type: 'string' } } },
        },
      })
    )
  })

  it('shows an error and does not submit when parameters JSON is invalid', async () => {
    createTool.mockClear()
    const { default: ToolManagerPanel } = await import('./ToolManagerPanel')
    render(<ToolManagerPanel projectId="project-1" />)

    await waitFor(() => expect(listTools).toHaveBeenCalledWith('project-1'))

    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Weather' } })
    fireEvent.change(screen.getByLabelText(/^url$/i), { target: { value: 'https://api.example.com/weather' } })
    fireEvent.change(screen.getByLabelText(/parameters \(json schema\)/i), { target: { value: '{not json' } })
    fireEvent.click(screen.getByRole('button', { name: /register tool/i }))

    await waitFor(() => expect(screen.getByText(/parameters must be valid json/i)).toBeInTheDocument())
    expect(createTool).not.toHaveBeenCalled()
  })

  it('shows permissions when a tool has any', async () => {
    listTools.mockResolvedValueOnce([
      {
        id: 't2',
        name: 'Read-only DB',
        type: 'rest',
        config: {},
        permissions: { allow_write: false },
        created_at: '2026-01-01T00:00:00Z',
      },
    ])
    const { default: ToolManagerPanel } = await import('./ToolManagerPanel')
    render(<ToolManagerPanel projectId="project-1" />)

    await waitFor(() => expect(screen.getByText(/allow_write/i)).toBeInTheDocument())
  })
})
