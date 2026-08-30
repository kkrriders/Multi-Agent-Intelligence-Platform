import { test, expect } from '@playwright/test'

// Cache-hit correctness (history_len-sensitive key) is covered by the backend
// gated test test_identical_first_turn_in_same_project_hits_cache. This E2E
// verifies the panel renders real per-run cost/token data end-to-end.
test('Cost Analytics panel shows real cost and per-model data after runs', async ({ page }) => {
  const email = `anshuman.aroraak+cost-${Date.now()}@gmail.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()
  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('Cost Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /cost project/i }).click()

  await page.getByLabel(/message/i).fill('Give me a one-sentence answer: is water wet?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Send', exact: true })).toBeEnabled({
    timeout: 90_000,
  })

  await page.getByRole('button', { name: /cost analytics/i }).click()

  await expect(page.getByText(/total cost/i)).toBeVisible()
  await expect(page.getByRole('heading', { name: /by model/i })).toBeVisible()
  // the multi-agent run uses both tiers
  await expect(page.getByText('openai/gpt-oss-20b')).toBeVisible()
  await expect(page.getByText('openai/gpt-oss-120b')).toBeVisible()
  // recent-runs table has the completed run with a dollar cost
  await expect(page.getByRole('heading', { name: /recent runs/i })).toBeVisible()
  await expect(page.getByText(/^\$0\.\d{4}$/).first()).toBeVisible()
})
