import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  // Serial: every spec signs up a fresh user against the one shared Supabase
  // project, and concurrent signups transiently rate-limit / contend. Not a
  // product bug — just this single-project test setup. Drop to parallel only
  // with per-worker Supabase projects.
  workers: 1,
  // A multi-agent run is ~6-9 Groq calls; give it room.
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: 'http://localhost:3000',
    actionTimeout: 60_000,
  },
})
