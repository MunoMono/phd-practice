import { expect, test } from '@playwright/test'

test('an unrepresented highlighted Atlas source can create a scoped computational condition', async ({ page }) => {
  let requestBody
  await page.route('**/api/viz/umap**', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ points: [], clusters: [], metadata: { projection_id: 'atlas-fixture' } }) }))
  await page.route('**/api/viz/embedding-readiness', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ready_for_embedding: false, review: null }) }))
  await page.route('**/api/viz/atlas-coverage-missingness', async (route) => {
    requestBody = route.request().postDataJSON()
    await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ event_id: 'miss-atlas-fixture', document_id: 'document-known', type: 'computational' }) })
  })

  await page.goto('/semantic-atlas?documentId=document-known')
  const recordButton = page.getByRole('button', { name: 'Record computational coverage condition' })
  await expect(recordButton).toBeVisible()
  await recordButton.click()
  await expect.poll(() => requestBody).toEqual({ document_id: 'document-known', projection_id: 'atlas-fixture' })
  await expect(page).toHaveURL(/\/absences\?eventId=miss-atlas-fixture/)
})