import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const authenticate = vi.fn().mockResolvedValue({})

vi.mock('@/lib/auth', () => ({ authenticate }))

describe('AuthForm', () => {
  it('authenticates with entered credentials in login mode', async () => {
    const { default: AuthForm } = await import('./AuthForm')
    const onSuccess = vi.fn()
    render(<AuthForm mode="login" onSuccess={onSuccess} />)

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'user@example.com' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'hunter2' } })
    fireEvent.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => expect(authenticate).toHaveBeenCalledWith('login', 'user@example.com', 'hunter2'))
    await waitFor(() => expect(onSuccess).toHaveBeenCalled())
  })
})
