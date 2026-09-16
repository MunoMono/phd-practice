import { test, expect } from '@playwright/test'

test('analytical lens changes retain the loaded corpus search and filters', async ({ page }) => {
  await page.route('**/api/viz/umap**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        points: [{ id: 'chunk-1', chunk_id: 'chunk-1', document_id: 'document-1', title: 'Bruce Archer memorandum', x: 0, y: 0, year: 1974, source_type: 'letter', themes: ['education'] }],
        metadata: {
          projection_method: 'umap',
          evidence_surface_scope: { embedded_chunks: 1, documents_with_embeddings: 1 }
        }
      })
    })
  })

  await page.goto('/semantic-atlas')
  await page.getByRole('searchbox', { name: 'Search corpus' }).fill('Bruce Archer')
  await page.getByRole('textbox', { name: 'Theme' }).fill('education')
  await page.getByLabel('View').selectOption('neighbourhoods')

  await expect(page).toHaveURL(/\/semantic-atlas$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Semantic Neighbourhoods' })).toBeVisible()
  await expect(page.getByRole('searchbox', { name: 'Search corpus' })).toHaveValue('Bruce Archer')
  await expect(page.getByRole('textbox', { name: 'Theme' })).toHaveValue('education')
  await expect(page.getByText('Visible: 1')).toBeVisible()
})