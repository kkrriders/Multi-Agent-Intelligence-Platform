import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  // Serial: every spec signs up a fresh user against the one shared backend, and
  // /auth/signup is throttled per IP (10/min). Not a product bug, just this
  // single-backend test setup.
  workers: 1,
  // A multi-agent run is ~6-9 Groq calls; give it room.
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: 'http://localhost:3000',
    actionTimeout: 60_000,
  },
})
