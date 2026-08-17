import { test, expect } from '@playwright/test'

test('returns to the expanded abstract from another documentation record', async ({ page }) => {
  await page.goto('/documentation/using-the-turin-research-instrument')

  await page.getByRole('button', {
    name: 'Return to the expanded abstract as the foundational documentation record'
  }).click()

  await expect(page).toHaveURL(/\/documentation\/expanded-abstract$/)
  await expect(page.locator('.documentation-page__catalogue-item--active')).toContainText('Expanded abstract')
  await expect(page.locator('.documentation-page__document-meta')).toContainText('Expanded abstract')
})