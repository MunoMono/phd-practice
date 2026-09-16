import { test, expect } from '@playwright/test'

test('Sources shows structural archive-record siblings without similarity scores', async ({ page }) => {
  await page.goto('/sources', { waitUntil: 'networkidle' })
  await page.getByRole('tab', { name: 'Provenance' }).click()

  await expect(page.getByRole('heading', { level: 4, name: 'Other documents in this archive record' })).toBeVisible()
  await expect(page.getByText('Similarity:', { exact: false })).toHaveCount(0)
  await expect(page.locator('.corpus-panel__section-title').filter({ hasText: 'Similar documents' })).toHaveCount(0)
})

test('Sources gives a scoped empty archive-record relationship state', async ({ page }) => {
  await page.route('**/api/search/archive-record-siblings/**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        sourceDocument: { documentId: 'source-without-sibling', archiveRecordPid: 'record-alone' },
        relatedDocuments: [],
        metadata: { relationship: 'shared_archive_record', count: 0 }
      })
    })
  })

  await page.goto('/sources', { waitUntil: 'networkidle' })
  await page.getByRole('tab', { name: 'Provenance' }).click()
  await expect(page.getByText('No related source documents are recorded for this item.')).toBeVisible()
  await expect(page.getByText('This refers to the current local archive-record relationship and does not indicate that no related material exists elsewhere in the archive.')).toBeVisible()
})