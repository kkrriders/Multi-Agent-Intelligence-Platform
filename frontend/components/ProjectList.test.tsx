import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ProjectList from './ProjectList'

describe('ProjectList', () => {
  it('renders project names and calls onCreate with the entered name', () => {
    const onCreate = vi.fn()
    render(
      <ProjectList
        projects={[{ id: '1', name: 'Alpha', created_at: '2026-01-01T00:00:00Z' }]}
        onCreate={onCreate}
      />
    )

    expect(screen.getByText('Alpha')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/new project name/i), { target: { value: 'Beta' } })
    fireEvent.click(screen.getByRole('button', { name: /create/i }))

    expect(onCreate).toHaveBeenCalledWith('Beta')
  })

  it('shows an empty state when there are no projects', () => {
    render(<ProjectList projects={[]} onCreate={vi.fn()} />)
    expect(screen.getByText(/no projects yet/i)).toBeInTheDocument()
  })
})
