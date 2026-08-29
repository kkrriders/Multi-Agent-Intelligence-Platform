import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Timeline from './Timeline'

const ev = (id: string, step_name: string, payload: Record<string, unknown> = {}) => ({
  id,
  step_name,
  payload,
  created_at: '2026-01-01T10:00:00Z',
})

describe('Timeline', () => {
  it('shows a placeholder when there are no events', () => {
    render(<Timeline events={[]} />)
    expect(screen.getByText('No events yet.')).toBeInTheDocument()
  })

  it('puts turn-0 and turn-less events in a Setup group', () => {
    render(
      <Timeline
        events={[ev('e1', 'run_started', {}), ev('e2', 'retrieval_performed', { turn: 0, count: 3 })]}
      />
    )
    expect(screen.getByText(/setup/i)).toBeInTheDocument()
    expect(screen.getByText('run_started')).toBeInTheDocument()
  })

  it('groups events into per-turn blocks with agent and tool count', () => {
    render(
      <Timeline
        events={[
          ev('e1', 'orchestrator_decision', { turn: 1, next: 'tool_runner' }),
          ev('e2', 'tool_called', { turn: 1, tool: 'Weather', status: 200 }),
          ev('e3', 'orchestrator_decision', { turn: 2, next: 'executor' }),
          ev('e4', 'worker_executor', { turn: 2 }),
          ev('e5', 'verifier_check', { turn: 3, supported: true, note: 'ok' }),
        ]}
      />
    )
    expect(screen.getByText(/turn 1.*tool_runner.*1 tool/i)).toBeInTheDocument()
    expect(screen.getByText(/turn 2.*executor/i)).toBeInTheDocument()
    expect(screen.getByText(/turn 3.*verifier/i)).toBeInTheDocument()
  })

  it('renders guardrail pre and post rows when provided', () => {
    render(
      <Timeline
        events={[ev('e1', 'worker_executor', { turn: 1 })]}
        guardrails={[
          { phase: 'pre', kind: 'injection', outcome: 'pass' },
          { phase: 'post', kind: 'pii', outcome: 'masked' },
        ]}
      />
    )
    expect(screen.getByText(/guardrail_pre · injection · pass/i)).toBeInTheDocument()
    expect(screen.getByText(/guardrail_post · pii · masked/i)).toBeInTheDocument()
  })

  it('summary line counts turns, tool calls, and verification', () => {
    render(
      <Timeline
        events={[
          ev('e1', 'tool_called', { turn: 1, tool: 'W', status: 200 }),
          ev('e2', 'worker_executor', { turn: 2 }),
          ev('e3', 'verifier_check', { turn: 3, supported: false, note: 'no source' }),
        ]}
      />
    )
    expect(screen.getByText(/3 turns/i)).toBeInTheDocument()
    expect(screen.getByText(/1 tool call/i)).toBeInTheDocument()
    expect(screen.getByText(/unverified/i)).toBeInTheDocument()
  })
})
