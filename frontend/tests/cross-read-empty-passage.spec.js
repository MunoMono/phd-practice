import { expect, test } from '@playwright/test'

test('blank and whitespace passage text show required validation without creating a passage', async ({ page }) => {
  const requests = []

  await page.route('**/api/cross-read/passages', async (route) => {
    requests.push(route.request().method())
    if (route.request().method() === 'GET') {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ count: 0, passages: [] }) })
      return
    }

    await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Unexpected write' }) })
  })

  await page.goto('/cross-readings')

  const passageText = page.getByRole('textbox', { name: 'Passage text' })
  const createPassage = page.getByRole('button', { name: 'Create passage' })
  const requiredError = 'Passage text is required before creating a passage.'

  await expect(page.getByText('No persisted testimony passages are available yet. This surface remains intentionally empty until passages are created or ingested.')).toBeVisible()
  await expect(createPassage).toBeEnabled()

  await createPassage.click()
  await expect(page.getByText(requiredError)).toBeVisible()
  await expect(passageText).toHaveAttribute('aria-invalid', 'true')
  expect(requests.filter((method) => method === 'POST')).toEqual([])

  await passageText.fill(' \n\t ')
  await createPassage.click()
  await expect(page.getByText(requiredError)).toBeVisible()
  expect(requests.filter((method) => method === 'POST')).toEqual([])

  await passageText.fill('Researcher draft text')
  await expect(page.getByText(requiredError)).not.toBeVisible()
  await expect(passageText).toHaveAttribute('aria-invalid', 'false')
  expect(requests.filter((method) => method === 'POST')).toEqual([])
})