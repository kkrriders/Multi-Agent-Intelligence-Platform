import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { authenticate, getToken, signOut } from './auth'

function stubFetch(status: number, body: unknown) {
  global.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }) as unknown as typeof fetch
}

describe('auth', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => vi.restoreAllMocks())

  it('stores the token on a successful login', async () => {
    stubFetch(200, { access_token: 'tok', user: { id: '1', email: 'a@b.dev' } })
    expect(await authenticate('login', 'a@b.dev', 'password1')).toEqual({})
    expect(getToken()).toBe('tok')
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/auth/login'), expect.objectContaining({ method: 'POST' }))
  })

  it('posts signup to /auth/signup', async () => {
    stubFetch(200, { access_token: 'tok2', user: { id: '1', email: 'a@b.dev' } })
    await authenticate('signup', 'a@b.dev', 'password1')
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/auth/signup'), expect.anything())
  })

  it('returns the server message and stores nothing on failure', async () => {
    stubFetch(401, { detail: 'Invalid email or password' })
    expect(await authenticate('login', 'a@b.dev', 'nope-nope')).toEqual({ error: 'Invalid email or password' })
    expect(getToken()).toBeNull()
  })

  it('gives a friendly message for 422 validation arrays', async () => {
    stubFetch(422, { detail: [{ msg: 'x' }] })
    const { error } = await authenticate('signup', 'bad', 'short')
    expect(error).toMatch(/valid email/i)
  })

  it('reports an unreachable server', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('down')) as unknown as typeof fetch
    expect(await authenticate('login', 'a@b.dev', 'password1')).toEqual({ error: 'Could not reach the server' })
  })

  it('signOut clears the token', async () => {
    stubFetch(200, { access_token: 'tok', user: { id: '1', email: 'a@b.dev' } })
    await authenticate('login', 'a@b.dev', 'password1')
    signOut()
    expect(getToken()).toBeNull()
  })
})
