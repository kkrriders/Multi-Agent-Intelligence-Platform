import { test, expect } from '@playwright/test'

test('signup, create project, register a tool, run a multi-agent message, see grouped timeline', async ({ page }) => {
  const email = `anshuman.aroraak+golden-${Date.now()}@gmail.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()
  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('Golden Path Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /golden path project/i }).click()

  // register a GET tool the agent loop can call
  await page.getByRole('button', { name: /tool manager/i }).click()
  await page.getByLabel(/^name$/i).fill('Public Echo')
  await page.getByLabel(/^url$/i).fill('https://example.com')
  await page.getByRole('button', { name: /register tool/i }).click()
  await expect(page.getByText('Public Echo')).toBeVisible()

  // back to Chat / Run and send a message
  await page.getByRole('button', { name: /chat \/ run/i }).click()
  await page.getByLabel(/message/i).fill('Give me a one-sentence answer: is water wet?')
  await page.getByRole('button', { name: /send/i }).click()

  // response + grouped timeline (the answer <p> renders before the Timeline payload blocks)
  await expect(page.getByText(/water/i).first()).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText(/turn 1/i).first()).toBeVisible()
  await expect(page.getByText(/turns? · .*tool call/i)).toBeVisible()
})
