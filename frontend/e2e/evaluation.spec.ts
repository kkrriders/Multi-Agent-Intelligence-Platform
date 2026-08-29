import { test, expect } from '@playwright/test'

test('create a golden dataset and run an evaluation', async ({ page }) => {
  const email = `anshuman.aroraak+eval-${Date.now()}@gmail.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()
  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('Eval Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /eval project/i }).click()

  await page.getByRole('button', { name: /evaluation/i }).click()
  await page.getByRole('button', { name: /new dataset/i }).click()
  await page.getByLabel(/dataset name/i).fill('basics')
  await page.getByLabel(/^input 1$/i).fill('What is 2 + 2? Reply with just the number.')
  await page.getByLabel(/^expected 1$/i).fill('4')
  await page.getByRole('button', { name: /add row/i }).click()
  await page.getByLabel(/^input 2$/i).fill('Capital of France? One word.')
  await page.getByLabel(/^expected 2$/i).fill('Paris')
  await page.getByRole('button', { name: /^create dataset$/i }).click()

  await page.getByRole('button', { name: /run evaluation/i }).click()
  await expect(page.getByText(/accuracy \d+%/i)).toBeVisible({ timeout: 120_000 })
})
