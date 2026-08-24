import { test, expect } from '@playwright/test'

test('uploads a document and cites it in a chat response', async ({ page }) => {
  const email = `kartikarora1240+rag-${Date.now()}@gmail.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()

  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('RAG Test Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /rag test project/i }).click()

  await page.getByRole('button', { name: /knowledge hub/i }).click()
  await page.setInputFiles('#document-file', {
    name: 'launch-notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('The launch codeword for our rocket is Bluebird.'),
  })
  await page.getByRole('button', { name: 'Upload', exact: true }).click()
  await expect(page.getByText('indexed')).toBeVisible({ timeout: 15000 })

  await page.getByRole('button', { name: /chat \/ run/i }).click()
  await page.getByLabel(/message/i).fill('What is the launch codeword? Reply with just the word.')
  await page.getByRole('button', { name: /send/i }).click()

  await expect(page.getByText(/bluebird/i)).toBeVisible({ timeout: 15000 })
  await expect(page.getByText(/launch-notes\.txt/i)).toBeVisible()
})
