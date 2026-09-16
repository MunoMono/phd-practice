import { expect, test } from '@playwright/test'

test('legacy semantic-neighbourhood URL opens the unified atlas lens', async ({ page }) => {
  await page.goto('/semantic-neighbourhoods')
  await expect(page).toHaveURL(/\/semantic-atlas\?view=neighbourhoods/)
  await expect(page.getByRole('heading', { level: 1, name: 'Semantic Neighbourhoods' })).toBeVisible()
})