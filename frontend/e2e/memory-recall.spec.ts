import { test, expect } from '@playwright/test'

test('recalls the first message when asked in the same conversation', async ({ page }) => {
  const email = `kartikarora1240+memory-${Date.now()}@gmail.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()

  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('Memory Test Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /memory test project/i }).click()

  await page.getByLabel(/message/i).fill("My favorite color is teal. Reply with just 'ok'.")
  await page.getByRole('button', { name: /send/i }).click()
  await expect(page.getByText(/ok/i)).toBeVisible({ timeout: 15000 })

  await page.getByLabel(/message/i).fill('What is my favorite color? Reply with just the color.')
  await page.getByRole('button', { name: /send/i }).click()
  await expect(page.getByText(/teal/i)).toBeVisible({ timeout: 15000 })
})

test('semantic search finds an earlier turn from a different conversation', async ({ page }) => {
  const email = `kartikarora1240+memsearch-${Date.now()}@gmail.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()

  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('Memory Search Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /memory search project/i }).click()

  await page.getByLabel(/message/i).fill('The launch codeword for our rocket is Bluebird.')
  await page.getByRole('button', { name: /send/i }).click()
  await expect(page.getByText('run_started')).toBeVisible({ timeout: 15000 })

  await page.getByRole('button', { name: /new conversation/i }).click()
  await page.getByRole('button', { name: /memory explorer/i }).click()

  await page.getByLabel(/search memory/i).fill('rocket launch codeword')
  await page.getByRole('button', { name: /search/i }).click()

  await expect(page.getByText(/Bluebird/i)).toBeVisible({ timeout: 15000 })
})
