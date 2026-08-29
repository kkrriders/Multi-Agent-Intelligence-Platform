import { test, expect } from '@playwright/test'

test('register a tool, invoke it, and see the result', async ({ page }) => {
  const email = `anshuman.aroraak+tools-${Date.now()}@gmail.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()

  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('Tool Test Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /tool test project/i }).click()

  await page.getByRole('button', { name: /tool manager/i }).click()

  await page.getByLabel(/^name$/i).fill('Public Echo')
  // example.com: IANA-run, effectively never down. httpbin.org (the old target)
  // 503'd/timed out and made this spec flaky. The test only checks the invoke
  // returns 200, so any stable external endpoint works.
  await page.getByLabel(/^url$/i).fill('https://example.com')
  await page.getByRole('button', { name: /register tool/i }).click()

  await expect(page.getByText('Public Echo')).toBeVisible()

  await page.getByRole('button', { name: /test/i }).click()
  await expect(page.getByText('200')).toBeVisible({ timeout: 15000 })
})
