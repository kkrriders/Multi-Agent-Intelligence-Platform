import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EmptyState, Notice, PanelSection, SkeletonRows } from './PanelKit'

describe('PanelKit', () => {
  it('EmptyState renders its title, description, and an optional action', () => {
    render(
      <EmptyState
        title="No tools registered"
        description="Register a GET endpoint below."
        action={<button type="button">Add one</button>}
      />
    )
    expect(screen.getByRole('heading', { name: /no tools registered/i })).toBeInTheDocument()
    expect(screen.getByText(/register a get endpoint below/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /add one/i })).toBeInTheDocument()
  })

  it('Notice is an alert by default and a status when informational', () => {
    const { rerender } = render(<Notice>Something broke</Notice>)
    expect(screen.getByRole('alert')).toHaveTextContent('Something broke')
    rerender(<Notice variant="info">Heads up</Notice>)
    expect(screen.getByRole('status')).toHaveTextContent('Heads up')
  })

  it('SkeletonRows renders the requested number of placeholder rows', () => {
    const { container } = render(<SkeletonRows rows={5} />)
    expect(container.querySelectorAll('.animate-pulse')).toHaveLength(5)
  })

  it('PanelSection renders a heading and its children', () => {
    render(
      <PanelSection title="Registered tools" right={<span>2</span>}>
        <p>body</p>
      </PanelSection>
    )
    expect(screen.getByRole('heading', { name: /registered tools/i })).toBeInTheDocument()
    expect(screen.getByText('body')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })
})
