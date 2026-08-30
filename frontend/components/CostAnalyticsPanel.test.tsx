import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const getProjectCost = vi.fn()
vi.mock('@/lib/api', () => ({ getProjectCost }))

function daily(n: number) {
  return Array.from({ length: n }, (_, i) => ({
    date: `2026-08-${String(i + 1).padStart(2, '0')}`,
    run_count: i === n - 1 ? 2 : 0,
    cost_usd: i === n - 1 ? 0.03 : 0,
    cached_run_count: i === n - 1 ? 1 : 0,
  }))
}

const cost = (over = {}) => ({
  totals: {
    run_count: 12,
    cached_run_count: 4,
    prompt_tokens: 8000,
    completion_tokens: 1500,
    cost_usd: 0.1234,
    runs_missing_cost: 0,
    estimated_cache_savings_usd: 0.0456,
  },
  by_model: [
    { model: 'openai/gpt-oss-120b', calls: 20, prompt_tokens: 6000, completion_tokens: 1200, cost_usd: 0.11 },
    { model: 'openai/gpt-oss-20b', calls: 40, prompt_tokens: 2000, completion_tokens: 300, cost_usd: 0.0134 },
  ],
  daily: daily(30),
  recent_runs: [
    {
      id: 'run-abcdef12',
      created_at: '2026-08-30T12:00:00Z',
      status: 'completed',
      cache_hit: false,
      prompt_tokens: 500,
      completion_tokens: 80,
      cost_usd: 0.014,
      models: ['openai/gpt-oss-120b'],
    },
    {
      id: 'run-cached01',
      created_at: '2026-08-30T12:01:00Z',
      status: 'completed',
      cache_hit: true,
      prompt_tokens: 0,
      completion_tokens: 0,
      cost_usd: 0,
      models: [],
    },
  ],
  ...over,
})

describe('CostAnalyticsPanel', () => {
  it('renders summary tiles from getProjectCost', async () => {
    getProjectCost.mockResolvedValue(cost())
    const { default: CostAnalyticsPanel } = await import('./CostAnalyticsPanel')
    render(<CostAnalyticsPanel projectId="p1" />)

    expect(await screen.findByText(/\$0\.1234/)).toBeInTheDocument()
    expect(screen.getByText(/4 of 12/)).toBeInTheDocument()
    expect(screen.getByText(/\$0\.0456/)).toBeInTheDocument()
  })

  it('shows a by-model row per model', async () => {
    getProjectCost.mockResolvedValue(cost())
    const { default: CostAnalyticsPanel } = await import('./CostAnalyticsPanel')
    render(<CostAnalyticsPanel projectId="p1" />)

    expect(await screen.findByText('openai/gpt-oss-120b')).toBeInTheDocument()
    expect(screen.getByText('openai/gpt-oss-20b')).toBeInTheDocument()
  })

  it('renders 30 daily bars', async () => {
    getProjectCost.mockResolvedValue(cost())
    const { default: CostAnalyticsPanel } = await import('./CostAnalyticsPanel')
    render(<CostAnalyticsPanel projectId="p1" />)

    await screen.findByText(/\$0\.1234/)
    expect(screen.getAllByTestId('cost-daily-bar')).toHaveLength(30)
  })

  it('shows an empty state when there are no runs', async () => {
    getProjectCost.mockResolvedValue(
      cost({ totals: { ...cost().totals, run_count: 0 }, recent_runs: [], by_model: [] }),
    )
    const { default: CostAnalyticsPanel } = await import('./CostAnalyticsPanel')
    render(<CostAnalyticsPanel projectId="p1" />)

    expect(await screen.findByText(/no runs yet/i)).toBeInTheDocument()
  })

  it('notes runs that predate cost tracking', async () => {
    getProjectCost.mockResolvedValue(cost({ totals: { ...cost().totals, runs_missing_cost: 3 } }))
    const { default: CostAnalyticsPanel } = await import('./CostAnalyticsPanel')
    render(<CostAnalyticsPanel projectId="p1" />)

    expect(await screen.findByText(/3 runs predate cost tracking/i)).toBeInTheDocument()
  })
})
