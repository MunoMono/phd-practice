import { expect, test } from '@playwright/test'

const runs = [
  { run_id: 'experiment-a', research_case: 'documentary', status: 'completed' },
  { run_id: 'experiment-b', research_case: 'missingness', status: 'completed_with_missingness' },
  { run_id: 'experiment-c', research_case: 'documentary', status: 'failed' },
]

const records = {
  'experiment-a': {
    ...runs[0], created_at: '2026-08-17T10:00:00Z', corpus_version: 'corpus-a', prompt: { question: 'Question A' }, retrieval: {}, context: { budget: {} }, model: { name: 'granite' }, authority_context: { used: false }, structured_response: {}, provenance_validation: { valid: true }, retrieved_evidence: [], assessment: { notes: 'Assessment A', failure_categories: [] },
  },
  'experiment-b': {
    ...runs[1], created_at: '2026-08-17T10:01:00Z', corpus_version: null, prompt: { question: 'Question B' }, retrieval: { result_count: 0 }, context: { budget: {} }, model: { name: null }, authority_context: { used: true, contexts: [{ authority_id: 'authority-b' }] }, structured_response: { missingness: [{ explanation: 'Scoped documentary limit.' }] }, provenance_validation: { valid: true }, retrieved_evidence: [], assessment: null,
  },
  'experiment-c': {
    ...runs[2], created_at: '2026-08-17T10:02:00Z', corpus_version: 'corpus-c', prompt: { question: 'Question C' }, retrieval: {}, context: { budget: {} }, model: { name: 'granite' }, authority_context: { used: false }, structured_response: { missingness: [{ explanation: 'Preserved validation failure.' }] }, provenance_validation: { valid: false }, error_code: 'provenance_validation_failure', error_message: 'Citation did not match supplied evidence.', retrieved_evidence: [{ rank: 1, chunk_id: 'chunk-c', document_id: 'document-c', pid: 'pid-c', page_start: 1, score: 0.9, included_in_context: true, excerpt: 'Preserved evidence.' }], assessment: null,
  },
}

const installApi = async (page, { delayedRunId, mismatchedRunId } = {}) => {
  const requests = []
  let releaseDelayedRun
  const delayed = new Promise((resolve) => { releaseDelayedRun = resolve })
  await page.route('**/api/experiments', async (route) => {
    requests.push({ method: route.request().method(), path: '/api/experiments' })
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ count: runs.length, experiment_runs: runs }) })
  })
  await page.route('**/api/experiments/**', async (route) => {
    const runId = route.request().url().split('/').pop()
    requests.push({ method: route.request().method(), path: `/api/experiments/${runId}` })
    if (runId === delayedRunId) await delayed
    if (!records[runId]) {
      await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Experiment run not found' }) })
      return
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(records[mismatchedRunId] || records[runId]) })
  })
  return { requests, releaseDelayedRun }
}

const detailRequests = (requests) => requests.filter((request) => request.path !== '/api/experiments')

test('ordinary load keeps saved runs unselected and makes no detail request', async ({ page }) => {
  const { requests } = await installApi(page)
  await page.goto('/research-runs')
  await expect(page.getByText('Select a saved run to inspect it.')).toBeVisible()
  await expect(page.locator('#saved-run')).toHaveValue('')
  await expect(page.locator('#assessment-notes')).toHaveCount(0)
  expect(detailRequests(requests)).toEqual([])
  expect(requests.every((request) => request.method === 'GET')).toBe(true)
})

test('selection and deep link fetch and render only the exact run_id', async ({ page }) => {
  const { requests } = await installApi(page)
  await page.goto('/research-runs')
  await page.locator('#saved-run').selectOption('experiment-b')
  await expect(page.getByText('Question B', { exact: true })).toBeVisible()
  await expect(page).toHaveURL(/runId=experiment-b/)
  await expect(page.getByText('Model: not invoked (persisted execution state)')).toBeVisible()
  expect(detailRequests(requests).every((request) => request.path === '/api/experiments/experiment-b')).toBe(true)
  expect(detailRequests(requests)).not.toHaveLength(0)

  await page.reload()
  await expect(page.getByText('Question B', { exact: true })).toBeVisible()
  await expect(page.locator('#saved-run')).toHaveValue('experiment-b')

  await page.unrouteAll()
  const deepLinkRequests = await installApi(page)
  await page.goto('/research-runs?runId=experiment-a')
  await expect(page.getByText('Question A', { exact: true })).toBeVisible()
  await expect(page.locator('#saved-run')).toHaveValue('experiment-a')
  expect(detailRequests(deepLinkRequests.requests).every((request) => request.path === '/api/experiments/experiment-a')).toBe(true)
  expect(detailRequests(deepLinkRequests.requests)).not.toHaveLength(0)
})

test('stale and mismatched identities produce a controlled state without substitution', async ({ page }) => {
  const stale = await installApi(page)
  await page.goto('/research-runs?runId=experiment-not-real')
  await expect(page.getByText('Saved run could not be loaded.')).toBeVisible()
  await expect(page.locator('#saved-run')).toHaveValue('experiment-not-real')
  await expect(page.getByText('Question A', { exact: true })).toHaveCount(0)
  expect(detailRequests(stale.requests).every((request) => request.path === '/api/experiments/experiment-not-real')).toBe(true)
  expect(detailRequests(stale.requests)).not.toHaveLength(0)

  await page.unrouteAll()
  await installApi(page, { mismatchedRunId: 'experiment-a' })
  await page.goto('/research-runs?runId=experiment-b')
  await expect(page.getByText('Saved run could not be loaded.')).toBeVisible()
  await expect(page.getByText('Question A', { exact: true })).toHaveCount(0)
})

test('selection transition clears run and assessment detail until the exact response arrives', async ({ page }) => {
  const { requests, releaseDelayedRun } = await installApi(page, { delayedRunId: 'experiment-b' })
  await page.goto('/research-runs?runId=experiment-a')
  await expect(page.locator('#assessment-notes')).toHaveValue('Assessment A')
  await page.locator('#saved-run').selectOption('experiment-b')
  await expect(page.getByText('Loading saved run...')).toBeVisible()
  await expect(page.getByText('Question A', { exact: true })).toHaveCount(0)
  await expect(page.locator('#assessment-notes')).toHaveCount(0)
  releaseDelayedRun()
  await expect(page.getByText('Question B', { exact: true })).toBeVisible()
  await expect(page.locator('#assessment-notes')).toHaveValue('')
  expect(requests.every((request) => request.method === 'GET')).toBe(true)
})

test('authority-only, zero-retrieval, and provenance-failure records retain their persisted meaning', async ({ page }) => {
  const { requests } = await installApi(page)
  await page.goto('/research-runs?runId=experiment-b')
  await expect(page.getByText('Model: not invoked (persisted execution state)')).toBeVisible()
  await expect(page.getByText('Run failure:', { exact: false })).toHaveCount(0)
  await expect(page.getByText('Missingness is limited to this query, supplied evidence and corpus; it is not a historical or archive-wide absence claim.')).toBeVisible()

  await page.locator('#saved-run').selectOption('experiment-c')
  await expect(page.getByText('Question C', { exact: true })).toBeVisible()
  await expect(page.getByText('Run failure: provenance_validation_failure')).toBeVisible()
  await expect(page.getByText('Preserved evidence.')).toBeVisible()
  expect(requests.every((request) => request.method === 'GET')).toBe(true)
  expect(requests.some((request) => request.path === '/api/experiments/experiment-c')).toBe(true)
})