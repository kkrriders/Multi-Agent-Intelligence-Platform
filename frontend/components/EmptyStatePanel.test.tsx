import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import EmptyStatePanel from './EmptyStatePanel'

describe('EmptyStatePanel', () => {
  it('renders the title, phase badge, and description', () => {
    render(
      <EmptyStatePanel
        title="Memory Explorer"
        phase={1}
        description="Conversation history, semantic memory search."
      />
    )

    expect(screen.getByText('Memory Explorer')).toBeInTheDocument()
    expect(screen.getByText(/phase 1/i)).toBeInTheDocument()
    expect(screen.getByText('Conversation history, semantic memory search.')).toBeInTheDocument()
  })
})
