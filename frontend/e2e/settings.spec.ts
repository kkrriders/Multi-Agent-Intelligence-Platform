import { test, expect } from '@playwright/test'

test('a daily_spend alert rule accrues an alert-history row after a run', async ({ page }) => {
  const email = `anshuman.aroraak+settings-${Date.now()}@gmail.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()
  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('Settings Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /settings project/i }).click()

  // Settings tab: a rule that any spend breaches
  await page.getByRole('button', { name: /^settings$/i }).click()
  await expect(page.getByText(/runs per minute per user/i)).toBeVisible()
  await page.getByLabel(/daily spend threshold/i).fill('0')
  await page.getByRole('button', { name: /save daily spend/i }).click()
  await expect(page.getByText(/daily spend/i).first()).toBeVisible()

  // one real run -> non-zero cost -> breach
  await page.getByRole('button', { name: /chat \/ run/i }).click()
  await page.getByLabel(/message/i).fill('Give me a one-sentence answer: is water wet?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Send', exact: true })).toBeEnabled({ timeout: 90_000 })

  await page.getByRole('button', { name: /^settings$/i }).click()
  await expect(page.getByRole('heading', { name: /alert history/i })).toBeVisible()
  await expect(page.getByText('daily_spend')).toBeVisible()
})
