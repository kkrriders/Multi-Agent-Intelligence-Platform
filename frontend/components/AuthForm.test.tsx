import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const signInWithPassword = vi.fn().mockResolvedValue({ error: null })

vi.mock('@/lib/supabaseClient', () => ({
  supabase: { auth: { signInWithPassword, signUp: vi.fn() } },
}))

describe('AuthForm', () => {
  it('calls signInWithPassword with entered credentials in login mode', async () => {
    const { default: AuthForm } = await import('./AuthForm')
    const onSuccess = vi.fn()
    render(<AuthForm mode="login" onSuccess={onSuccess} />)

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'user@example.com' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'hunter2' } })
    fireEvent.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => expect(signInWithPassword).toHaveBeenCalledWith({ email: 'user@example.com', password: 'hunter2' }))
    await waitFor(() => expect(onSuccess).toHaveBeenCalled())
  })
})
