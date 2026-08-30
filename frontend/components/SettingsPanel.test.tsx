import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const getLimits = vi.fn()
const listAlertRules = vi.fn()
const saveAlertRule = vi.fn()
const patchAlertRule = vi.fn()
const deleteAlertRule = vi.fn()
const listAlertEvents = vi.fn()

vi.mock('@/lib/api', () => ({
  getLimits,
  listAlertRules,
  saveAlertRule,
  patchAlertRule,
  deleteAlertRule,
  listAlertEvents,
}))

function setup() {
  getLimits.mockResolvedValue({ run_rate_limit_per_min: 20 })
  listAlertRules.mockResolvedValue([])
  listAlertEvents.mockResolvedValue([])
}

describe('SettingsPanel', () => {
  it('shows the server-enforced rate limit', async () => {
    setup()
    const { default: SettingsPanel } = await import('./SettingsPanel')
    render(<SettingsPanel projectId="p1" />)
    expect(await screen.findByText(/20 runs per minute/i)).toBeInTheDocument()
  })

  it('renders a row for each alert kind', async () => {
    setup()
    const { default: SettingsPanel } = await import('./SettingsPanel')
    render(<SettingsPanel projectId="p1" />)
    expect(await screen.findByText(/error rate/i)).toBeInTheDocument()
    expect(screen.getByText(/daily spend/i)).toBeInTheDocument()
    expect(screen.getByText(/p95 latency/i)).toBeInTheDocument()
  })

  it('saves a rule via saveAlertRule', async () => {
    setup()
    saveAlertRule.mockResolvedValue({
      id: 'r1',
      kind: 'daily_spend',
      threshold: 5,
      window_n: 20,
      webhook_url: null,
      enabled: true,
      created_at: '',
    })
    const { default: SettingsPanel } = await import('./SettingsPanel')
    render(<SettingsPanel projectId="p1" />)
    await screen.findByText(/daily spend/i)

    fireEvent.change(screen.getByLabelText(/daily spend threshold/i), { target: { value: '5' } })
    fireEvent.click(screen.getByRole('button', { name: /save daily spend/i }))

    await waitFor(() =>
      expect(saveAlertRule).toHaveBeenCalledWith('p1', expect.objectContaining({ kind: 'daily_spend', threshold: 5 })),
    )
  })

  it('can save a rule before the initial rules fetch resolves', async () => {
    getLimits.mockResolvedValue({ run_rate_limit_per_min: 20 })
    let releaseRules: (v: unknown) => void = () => {}
    listAlertRules.mockReturnValue(new Promise((r) => (releaseRules = r)))
    listAlertEvents.mockResolvedValue([])
    saveAlertRule.mockResolvedValue({
      id: 'r1', kind: 'daily_spend', threshold: 0, window_n: 20, webhook_url: null, enabled: true, created_at: '',
    })

    const { default: SettingsPanel } = await import('./SettingsPanel')
    render(<SettingsPanel projectId="p1" />)

    // rules fetch still pending; the row + Save must already work
    fireEvent.change(screen.getByLabelText(/daily spend threshold/i), { target: { value: '0' } })
    fireEvent.click(screen.getByRole('button', { name: /save daily spend/i }))

    await waitFor(() =>
      expect(saveAlertRule).toHaveBeenCalledWith('p1', expect.objectContaining({ kind: 'daily_spend', threshold: 0 })),
    )
    releaseRules([])
  })

  it('lists alert history including rate_limit rows', async () => {
    setup()
    listAlertEvents.mockResolvedValue([
      {
        id: 'e1',
        kind: 'rate_limit',
        observed: 2,
        threshold: 2,
        detail: { limit: 2, window_s: 60 },
        created_at: '2026-08-30T12:00:00Z',
      },
      {
        id: 'e2',
        kind: 'error_rate',
        observed: 1,
        threshold: 0,
        detail: {},
        created_at: '2026-08-30T12:05:00Z',
      },
    ])
    const { default: SettingsPanel } = await import('./SettingsPanel')
    render(<SettingsPanel projectId="p1" />)
    expect(await screen.findByText(/rate_limit/i)).toBeInTheDocument()
    expect(screen.getByText(/error_rate/i)).toBeInTheDocument()
  })
})
