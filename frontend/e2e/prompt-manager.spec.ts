import { test, expect } from '@playwright/test'

test('create a template, test it, and run it from Chat/Run', async ({ page }) => {
  const email = `anshuman.aroraak+pm-${Date.now()}@gmail.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()
  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('PM Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /pm project/i }).click()

  await page.getByRole('button', { name: /prompt manager/i }).click()
  await page.getByRole('button', { name: /new template/i }).click()
  await page.getByLabel(/template name/i).fill('hello')
  await page.getByLabel(/template body/i).fill('Say hello to {{name}} in one word.')
  await page.getByRole('button', { name: /^create$/i }).click()

  await page.getByLabel(/var name/i).fill('World')
  await page.getByRole('button', { name: /run test/i }).click()
  await expect(page.getByTestId('test-output')).not.toBeEmpty({ timeout: 60_000 })

  await page.getByRole('button', { name: /chat \/ run/i }).click()
  await page.getByLabel(/template/i).selectOption({ label: 'hello' })
  await page.getByLabel(/var name/i).fill('Sam')
  await page.getByRole('button', { name: /send/i }).click()
  await expect(page.getByText('prompt_used').first()).toBeVisible({ timeout: 60_000 })
})
