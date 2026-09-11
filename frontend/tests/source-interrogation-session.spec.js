import { expect, test } from '@playwright/test'

const responseFor = (query) => ({
  query_id: `session-${query.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
  mode: 'exploratory',
  status: 'completed',
  persisted: false,
  answer: `Answer for ${query}.`,
  answer_paragraphs: [{ claims: [{ text: `Answer for ${query}.`, source_numbers: [1] }] }],
  model: { name: 'qwen-fixture', display_name: 'Qwen fixture' },
  provenance_validation: { valid: true, source_count: 1 },
  retrieval: {},
  retrieval_diagnostics: { result_count: 1, notes: [] },
  retrieved_evidence: [{
    chunk_id: `chunk-${query}`, document_id: `document-${query}`, title: `Source for ${query}`,
    text: `Evidence for ${query}.`, rank: 1, score: 0.9, page_start: 1,
    provenance: { asset_pid: `pid-${query}` }, evidence_classification: { relationship_to_question: 'DIRECT_SUPPORT' }
  }],
  documentary_evidence: [], authority_evidence: [], archival_associations: [], contextual_evidence: [], inferences: [], contradictions: [], missingness: []
})

test('active Source Interrogation result survives analysis navigation until intentionally replaced or cleared', async ({ page }) => {
  await page.route('**/api/runtime/model-info', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ status: 'ready', display_name: 'Qwen fixture' }) }))
  await page.route('**/api/documents', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ count: 0, documents: [] }) }))
  await page.route('**/api/analysis/interrogate', async (route) => {
    const { query } = route.request().postDataJSON()
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(responseFor(query)) })
  })

  await page.goto('/source-interrogation')
  const input = page.getByRole('textbox', { name: 'Research query' })
  await input.fill('Query A')
  await page.getByRole('button', { name: 'Run interrogation' }).click()
  await expect(page.getByText('Answer for Query A.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Jump to source 1' })).toBeVisible()
  await expect(page.getByText('Source for Query A', { exact: true })).toBeVisible()

  await page.reload()
  await expect(page.getByText('Answer for Query A.')).toBeVisible()
  await expect(page.getByText('Source for Query A', { exact: true })).toBeVisible()

  await page.goto('/absences')
  await page.goto('/source-interrogation')
  await expect(page.getByText('Answer for Query A.')).toBeVisible()
  await expect(page.getByText('Source for Query A', { exact: true })).toBeVisible()

  await page.goto('/semantic-atlas')
  await page.goto('/cross-readings')
  await page.goto('/source-interrogation')
  await expect(page.getByText('Answer for Query A.')).toBeVisible()

  await input.fill('Query B')
  await expect(page.getByText('Answer for Query A.')).toBeVisible()
  await page.getByRole('button', { name: 'Run interrogation' }).click()
  await expect(page.getByText('Answer for Query B.')).toBeVisible()
  await expect(page.getByText('Answer for Query A.')).toHaveCount(0)

  await page.getByRole('button', { name: 'Clear current research' }).click()
  await expect(input).toHaveValue('')
  await expect(page.getByText('No answer returned yet. Submit a query to begin evidence tracing.')).toBeVisible()
  await page.goto('/absences')
  await page.goto('/source-interrogation')
  await expect(page.getByText('No answer returned yet. Submit a query to begin evidence tracing.')).toBeVisible()
})

test('a malformed saved Source Interrogation trace is discarded before rendering', async ({ page }) => {
  await page.addInitScript(() => {
    window.sessionStorage.setItem('innovation-design.source-interrogation.active.v1', JSON.stringify({
      query: 'Interrupted query',
      mode: 'runtime',
      traceData: { answer: 'Partial response without a source stack.' }
    }))
  })

  await page.goto('/source-interrogation')

  await expect(page.getByText('No answer returned yet. Submit a query to begin evidence tracing.')).toBeVisible()
  await expect.poll(() => page.evaluate(() => window.sessionStorage.getItem('innovation-design.source-interrogation.active.v1'))).toBeNull()
})