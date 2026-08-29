import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const listProjectRuns = vi.fn()
vi.mock('@/lib/api', () => ({ listProjectRuns }))
vi.mock('./TraceView', () => ({
  default: ({ run }: { run: { id: string } }) => <div>trace-for-{run.id}</div>,
}))

const mkRun = (id: string, over = {}) => ({
  id,
  status: 'completed',
  output: 'x',
  citations: [],
  events: [
    { id: `${id}-a`, step_name: 'run_started', payload: {}, created_at: '2026-01-01T10:00:00.000Z' },
    { id: `${id}-b`, step_name: 'worker_executor', payload: { turn: 1 }, created_at: '2026-01-01T10:00:02.000Z' },
  ],
  guardrails: [],
  ...over,
})

describe('ObservabilityPanel', () => {
  it('lists runs and shows a trace for the first by default', async () => {
    listProjectRuns.mockResolvedValue([mkRun('aaaaaaaa1111'), mkRun('bbbbbbbb2222')])
    const { default: ObservabilityPanel } = await import('./ObservabilityPanel')
    render(<ObservabilityPanel projectId="p1" />)

    await waitFor(() => expect(screen.getByText(/aaaaaaaa · completed/)).toBeInTheDocument())
    expect(screen.getByText(/bbbbbbbb · completed/)).toBeInTheDocument()
    expect(screen.getByText('trace-for-aaaaaaaa1111')).toBeInTheDocument()
  })

  it('selects a run on click', async () => {
    listProjectRuns.mockResolvedValue([mkRun('aaaaaaaa1111'), mkRun('bbbbbbbb2222')])
    const { default: ObservabilityPanel } = await import('./ObservabilityPanel')
    render(<ObservabilityPanel projectId="p1" />)

    await waitFor(() => expect(screen.getByText(/bbbbbbbb · completed/)).toBeInTheDocument())
    fireEvent.click(screen.getByText(/bbbbbbbb · completed/))
    expect(screen.getByText('trace-for-bbbbbbbb2222')).toBeInTheDocument()
  })

  it('shows an empty state with no runs', async () => {
    listProjectRuns.mockResolvedValue([])
    const { default: ObservabilityPanel } = await import('./ObservabilityPanel')
    render(<ObservabilityPanel projectId="p1" />)
    await waitFor(() => expect(screen.getByText(/no runs yet/i)).toBeInTheDocument())
  })
})
