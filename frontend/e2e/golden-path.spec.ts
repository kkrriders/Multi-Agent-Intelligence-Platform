import { test, expect } from '@playwright/test'

test('signup, create project, run a message, see the response and timeline', async ({ page }) => {
  const email = `anshuman.aroraak+golden-${Date.now()}@gmail.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()

  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('Golden Path Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /golden path project/i }).click()

  await page.getByLabel(/message/i).fill("Say the word 'pong' and nothing else.")
  await page.getByRole('button', { name: /send/i }).click()

  await expect(page.getByText(/pong/i)).toBeVisible({ timeout: 15000 })
  await expect(page.getByText('run_started')).toBeVisible()
  await expect(page.getByText('agent_responded')).toBeVisible()
})
