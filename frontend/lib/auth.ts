const KEY = 'maip_access_token'
const API_URL = process.env.NEXT_PUBLIC_API_URL!

export type AuthMode = 'login' | 'signup'

export function getToken(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function signOut(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* storage unavailable: nothing to clear */
  }
}

export async function authenticate(
  mode: AuthMode,
  email: string,
  password: string,
): Promise<{ error?: string }> {
  let res: Response
  try {
    res = await fetch(`${API_URL}/auth/${mode}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
  } catch {
    return { error: 'Could not reach the server' }
  }
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    // FastAPI 422s carry a detail array; only plain string details are user-presentable.
    const detail = body?.detail
    if (typeof detail === 'string') return { error: detail }
    return { error: res.status === 422 ? 'Enter a valid email and a password of 8+ characters' : 'Request failed' }
  }
  try {
    localStorage.setItem(KEY, body.access_token)
  } catch {
    return { error: 'Your browser blocked storage, so you cannot stay signed in' }
  }
  return {}
}
