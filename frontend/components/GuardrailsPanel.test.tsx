import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const listGuardrailPolicies = vi.fn()
const putGuardrailPolicy = vi.fn()
const listGuardrailEvents = vi.fn()

vi.mock('@/lib/api', () => ({ listGuardrailPolicies, putGuardrailPolicy, listGuardrailEvents }))

const policy = (kind: string, over = {}) => ({
  id: null,
  kind,
  enabled: false,
  config: {},
  created_at: null,
  ...over,
})

describe('GuardrailsPanel', () => {
  it('renders a card per policy kind and the violations log', async () => {
    listGuardrailPolicies.mockResolvedValue([policy('input_constraint'), policy('output_constraint')])
    listGuardrailEvents.mockResolvedValue([
      {
        id: 'g1',
        phase: 'pre',
        kind: 'injection',
        outcome: 'blocked',
        detail: { reason: 'x' },
        created_at: '2026-01-01T10:00:00Z',
      },
    ])
    const { default: GuardrailsPanel } = await import('./GuardrailsPanel')
    render(<GuardrailsPanel projectId="p1" />)

    await waitFor(() => expect(screen.getByText('input_constraint')).toBeInTheDocument())
    expect(screen.getByText('output_constraint')).toBeInTheDocument()
    expect(screen.getByText(/pre · injection · blocked/i)).toBeInTheDocument()
  })

  it('saves a policy with parsed max_length and blocklist', async () => {
    listGuardrailPolicies.mockResolvedValue([policy('input_constraint'), policy('output_constraint')])
    listGuardrailEvents.mockResolvedValue([])
    putGuardrailPolicy.mockResolvedValue(policy('input_constraint', { id: 'x', enabled: true }))
    const { default: GuardrailsPanel } = await import('./GuardrailsPanel')
    render(<GuardrailsPanel projectId="p1" />)

    await waitFor(() => expect(screen.getByText('input_constraint')).toBeInTheDocument())
    fireEvent.click(screen.getByLabelText(/enable input_constraint/i))
    fireEvent.change(screen.getByLabelText(/input_constraint max length/i), { target: { value: '120' } })
    fireEvent.change(screen.getByLabelText(/input_constraint blocklist/i), {
      target: { value: 'secret\ntoken' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save input_constraint/i }))

    await waitFor(() =>
      expect(putGuardrailPolicy).toHaveBeenCalledWith('p1', 'input_constraint', {
        enabled: true,
        config: { max_length: 120, blocklist: ['secret', 'token'] },
      })
    )
  })

  it('shows a teaching empty state when there are no guardrail events', async () => {
    listGuardrailPolicies.mockResolvedValue([policy('input_constraint'), policy('output_constraint')])
    listGuardrailEvents.mockResolvedValue([])
    const { default: GuardrailsPanel } = await import('./GuardrailsPanel')
    render(<GuardrailsPanel projectId="p1" />)

    await waitFor(() => expect(screen.getByText(/no guardrail events yet/i)).toBeInTheDocument())
  })
})
