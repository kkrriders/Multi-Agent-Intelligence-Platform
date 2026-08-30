import { test, expect } from '@playwright/test'

test('Deployment panel manages targets; Build & Publish is gated by the deploy API', async ({
  page,
}) => {
  const email = `anshuman.aroraak+deploy-${Date.now()}@gmail.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()
  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('Deploy Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /deploy project/i }).click()

  await page.getByRole('button', { name: /^deployment$/i }).click()
  await expect(page.getByRole('heading', { name: /deploy targets/i })).toBeVisible()

  await page.getByLabel(/target name/i).fill('prod')
  await page.getByLabel(/image repo/i).fill('acme/ai-platform')
  await page.getByRole('button', { name: /add target/i }).click()
  await expect(page.getByText('prod · ghcr.io/acme/ai-platform')).toBeVisible()

  // deploy API is off by default → button disabled with a note, history renders
  await expect(page.getByText(/deploy api is disabled/i)).toBeVisible()
  await expect(page.getByRole('button', { name: /build & publish/i })).toBeDisabled()
  await expect(page.getByRole('heading', { name: /deployment history/i })).toBeVisible()
})
