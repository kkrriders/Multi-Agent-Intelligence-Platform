import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Timeline from './Timeline'

describe('Timeline', () => {
  it('shows a placeholder when there are no events', () => {
    render(<Timeline events={[]} />)
    expect(screen.getByText('No events yet.')).toBeInTheDocument()
  })

  it('marks the last event active and earlier ones done, with a timestamp detail', () => {
    render(
      <Timeline
        events={[
          { id: 'e1', step_name: 'run_started', payload: {}, created_at: '2026-01-01T10:00:00Z' },
          { id: 'e2', step_name: 'agent_responded', payload: {}, created_at: '2026-01-01T10:00:05Z' },
        ]}
      />
    )

    expect(screen.getByText('run_started')).toBeInTheDocument()
    expect(screen.getByText('agent_responded')).toBeInTheDocument()
    expect(screen.getByText(new Date('2026-01-01T10:00:00Z').toLocaleTimeString())).toBeInTheDocument()
  })
})
