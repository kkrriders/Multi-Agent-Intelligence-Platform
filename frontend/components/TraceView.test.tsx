import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import TraceView from './TraceView'

const run = {
  id: 'r1',
  status: 'completed',
  output: 'done',
  citations: [],
  events: [
    { id: 'e1', step_name: 'run_started', payload: {}, created_at: '2026-01-01T10:00:00.000Z' },
    {
      id: 'e2',
      step_name: 'orchestrator_decision',
      payload: { turn: 1, next: 'executor' },
      created_at: '2026-01-01T10:00:01.300Z',
    },
    { id: 'e3', step_name: 'tool_called', payload: { turn: 1, tool: 'W', status: 200 }, created_at: '2026-01-01T10:00:02.200Z' },
    { id: 'e4', step_name: 'worker_executor', payload: { turn: 1 }, created_at: '2026-01-01T10:00:05.000Z' },
  ],
  guardrails: [
    { id: 'g1', phase: 'pre', kind: 'injection', outcome: 'pass', detail: {}, created_at: '2026-01-01T10:00:00.500Z' },
  ],
}

describe('TraceView', () => {
  it('renders a header with total duration, turns and tool count', () => {
    render(<TraceView run={run as never} />)
    expect(screen.getByText(/completed/i)).toBeInTheDocument()
    expect(screen.getByText(/5\.0s/)).toBeInTheDocument()
    expect(screen.getByText(/1 turn/i)).toBeInTheDocument()
    expect(screen.getByText(/1 tool/i)).toBeInTheDocument()
  })

  it('shows per-step deltas between consecutive rows (guardrails interleaved)', () => {
    render(<TraceView run={run as never} />)
    // rows sorted: run_started 0.0, guardrail_pre 0.5, orchestrator 1.3, tool 2.2, executor 5.0
    expect(screen.getByText(/\+0\.5s/)).toBeInTheDocument() // guardrail_pre after run_started
    expect(screen.getByText(/\+0\.8s/)).toBeInTheDocument() // orchestrator after guardrail_pre
    expect(screen.getByText(/\+2\.8s/)).toBeInTheDocument() // executor after tool_called
  })

  it('interleaves guardrail rows by time', () => {
    render(<TraceView run={run as never} />)
    const names = screen.getAllByTestId('trace-row-name').map((n) => n.textContent)
    expect(names).toEqual([
      'run_started',
      'guardrail_pre',
      'orchestrator_decision',
      'tool_called',
      'worker_executor',
    ])
  })

  it('shows per-node model + tokens + cost from llm_calls, and run cost in the header', () => {
    const costed = {
      ...run,
      cost_usd: 0.0123,
      cache_hit: false,
      llm_calls: [
        { node: 'executor', model: 'openai/gpt-oss-120b', prompt_tokens: 400, completion_tokens: 60, cost_usd: 0.011 },
        { node: 'orchestrator', model: 'openai/gpt-oss-20b', prompt_tokens: 120, completion_tokens: 15, cost_usd: 0.0013 },
      ],
    }
    render(<TraceView run={costed as never} />)
    expect(screen.getByText(/\$0\.0123/)).toBeInTheDocument()
    expect(screen.getByText(/openai\/gpt-oss-120b/)).toBeInTheDocument()
    expect(screen.getByText(/400\+60 tok/)).toBeInTheDocument()
  })

  it('shows "$0 (cached)" in the header for a cache-hit run', () => {
    const cached = { ...run, cache_hit: true, cost_usd: 0, llm_calls: [] }
    render(<TraceView run={cached as never} />)
    expect(screen.getByText(/\$0 \(cached\)/)).toBeInTheDocument()
  })

  it('highlights an error row and shows its detail', () => {
    const errRun = {
      ...run,
      events: [
        { id: 'e1', step_name: 'run_started', payload: {}, created_at: '2026-01-01T10:00:00.000Z' },
        { id: 'e2', step_name: 'error', payload: { detail: 'boom' }, created_at: '2026-01-01T10:00:01.000Z' },
      ],
      guardrails: [],
    }
    render(<TraceView run={errRun as never} />)
    expect(screen.getByText(/boom/)).toBeInTheDocument()
  })
})
