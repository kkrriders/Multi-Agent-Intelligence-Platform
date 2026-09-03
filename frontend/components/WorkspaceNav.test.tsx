import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import WorkspaceNav from './WorkspaceNav'

describe('WorkspaceNav', () => {
  it('renders every tab as a clickable button', () => {
    const onSelect = vi.fn()
    render(<WorkspaceNav active="chat" onSelect={onSelect} />)

    expect(screen.getByRole('button', { name: /playground/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /tool manager/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /prompt manager/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /knowledge hub/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /memory explorer/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /guardrails/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /evaluation/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /observability/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /cost analytics/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /deployment/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /settings/i })).toBeInTheDocument()
  })

  it('calls onSelect with the clicked tab', () => {
    const onSelect = vi.fn()
    render(<WorkspaceNav active="chat" onSelect={onSelect} />)

    fireEvent.click(screen.getByRole('button', { name: /memory explorer/i }))
    expect(onSelect).toHaveBeenCalledWith('memory-explorer')
  })
})
