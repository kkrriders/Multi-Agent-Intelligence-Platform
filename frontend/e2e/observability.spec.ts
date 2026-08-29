import { test, expect } from '@playwright/test'

test('a run appears in the Observability panel with a trace', async ({ page }) => {
  const email = `anshuman.aroraak+obs-${Date.now()}@gmail.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()
  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('Obs Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /obs project/i }).click()

  await page.getByLabel(/message/i).fill('One sentence: why is the sky blue?')
  await page.getByRole('button', { name: /send/i }).click()
  await expect(page.getByText(/sky|blue|rayleigh/i).first()).toBeVisible({ timeout: 60_000 })

  await page.getByRole('button', { name: /observability/i }).click()
  await expect(page.getByText(/turns/i).first()).toBeVisible()
  await expect(page.getByText('worker_executor').first()).toBeVisible()
})
