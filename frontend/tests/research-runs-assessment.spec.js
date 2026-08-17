import { expect, test } from '@playwright/test'

const scoreIds = ['retrieval_relevance', 'provenance_accuracy', 'interpretative_restraint', 'preservation_of_contestation', 'missingness_handling']

const run = (runId, question, assessment = null) => ({
  run_id: runId,
  research_case: 'fixture',
  status: 'completed',
  created_at: '2026-08-17T10:00:00Z',
  corpus_version: 'fixture-corpus',
  prompt: { question },
  retrieval: {},
  context: { budget: {} },
  model: {},
  authority_context: { used: false },
  structured_response: {},
  provenance_validation: { valid: true },
  retrieved_evidence: [],
  assessment,
})

const records = {
  'run-a': run('run-a', 'Run A', { retrieval_relevance: 0, provenance_accuracy: 2, interpretative_restraint: null, preservation_of_contestation: 3, missingness_handling: 1, failure_categories: ['parse'], notes: 'Persisted A', authority_influence_note: 'Authority note A' }),
  'run-b': run('run-b', 'Run B'),
}

const installApi = async (page, handler) => {
  const requests = []
  await page.route('**/api/experiments', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ count: 2, experiment_runs: Object.values(records).map(({ run_id, research_case, status }) => ({ run_id, research_case, status })) }),
  }))
  await page.route('**/api/experiments/run-a', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(records['run-a']) }))
  await page.route('**/api/experiments/run-b', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(records['run-b']) }))
  await page.route('**/api/experiments/*/assessment', async (route) => {
    requests.push({ method: route.request().method(), runId: route.request().url().split('/').at(-2), payload: route.request().postDataJSON() })
    await handler(route, requests.at(-1))
  })
  return requests
}

const selectScores = async (page, values) => {
  for (const [index, value] of values.entries()) await page.locator(`#${scoreIds[index]}`).selectOption(value)
}

test('unassessed defaults remain distinct from score zero and drafts are keyed by run_id', async ({ page }) => {
  const requests = await installApi(page, (route) => route.fulfill({ status: 500 }))
  await page.goto('/research-runs?runId=run-b')
  await expect(page.getByText('Run B', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Save assessment' })).toBeDisabled()
  for (const scoreId of scoreIds) await expect(page.locator(`#${scoreId}`)).toHaveValue('')
  expect(requests).toEqual([])

  await page.locator('#retrieval_relevance').selectOption('0')
  await page.locator('#assessment-notes').fill('Unsaved B draft')
  await expect(page.getByRole('button', { name: 'Save assessment' })).toBeEnabled()
  await page.locator('#saved-run').selectOption('run-a')
  await expect(page.locator('#retrieval_relevance')).toHaveValue('0')
  await expect(page.locator('#provenance_accuracy')).toHaveValue('2')
  await page.locator('#saved-run').selectOption('run-b')
  await expect(page.locator('#retrieval_relevance')).toHaveValue('0')
  await expect(page.locator('#assessment-notes')).toHaveValue('Unsaved B draft')
  expect(requests).toEqual([])
})

test('matching save captures the exact payload, rebases only its target, and becomes clean', async ({ page }) => {
  const requests = await installApi(page, async (route, request) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ run_id: request.runId, assessment: request.payload }) })
  })
  await page.goto('/research-runs?runId=run-b')
  await expect(page.getByText('Run B', { exact: true })).toBeVisible()
  await selectScores(page, ['0', '1', '2', '3', ''])
  await page.locator('#failure-categories').fill('parse, provenance')
  await page.locator('#assessment-notes').fill('Researcher evaluation')
  await page.locator('#authority-influence').fill('Authority observation')
  await page.getByRole('button', { name: 'Save assessment' }).dispatchEvent('click')
  await expect(page.getByText('Saved', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Save assessment' })).toBeDisabled()
  expect(requests).toEqual([{
    method: 'POST', runId: 'run-b', payload: {
      retrieval_relevance: 0, provenance_accuracy: 1, interpretative_restraint: 2, preservation_of_contestation: 3, missingness_handling: null,
      failure_categories: ['parse', 'provenance'], notes: 'Researcher evaluation', authority_influence_note: 'Authority observation',
    },
  }])
})

test('failed and mismatched saves preserve the target draft without false success', async ({ page }) => {
  let mismatch = false
  const requests = await installApi(page, async (route, request) => {
    if (!mismatch) {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'fixture failure' }) })
      return
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ run_id: 'run-b', assessment: request.payload }) })
  })
  await page.goto('/research-runs?runId=run-a')
  await page.locator('#retrieval_relevance').selectOption('3')
  await page.locator('#assessment-notes').fill('Keep A draft')
  await page.getByRole('button', { name: 'Save assessment' }).dispatchEvent('click')
  await expect(page.getByText('Assessment could not be saved.')).toBeVisible()
  await expect(page.getByText('Your local changes have not been lost.')).toBeVisible()
  await expect(page.locator('#retrieval_relevance')).toHaveValue('3')
  await expect(page.locator('#assessment-notes')).toHaveValue('Keep A draft')

  mismatch = true
  await page.getByRole('button', { name: 'Save assessment' }).dispatchEvent('click')
  await expect(page.getByText('Assessment could not be saved.')).toBeVisible()
  await expect(page.getByText('Saved', { exact: true })).toHaveCount(0)
  await expect(page.locator('#assessment-notes')).toHaveValue('Keep A draft')
  expect(requests).toHaveLength(2)
})

test('an in-flight A save cannot change B assessment controls or feedback', async ({ page }) => {
  let releaseSave
  const pending = new Promise((resolve) => { releaseSave = resolve })
  const requests = await installApi(page, async (route, request) => {
    await pending
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ run_id: request.runId, assessment: request.payload }) })
  })
  await page.goto('/research-runs?runId=run-a')
  await page.locator('#retrieval_relevance').selectOption('3')
  await page.getByRole('button', { name: 'Save assessment' }).dispatchEvent('click')
  await expect(page.getByRole('button', { name: 'Save assessment' })).toBeDisabled()
  await page.locator('#saved-run').selectOption('run-b')
  await expect(page.getByText('Run B', { exact: true })).toBeVisible()
  await expect(page.locator('#retrieval_relevance')).toHaveValue('')
  releaseSave()
  await expect(page.getByText('Saved', { exact: true })).toHaveCount(0)
  await expect(page.locator('#retrieval_relevance')).toHaveValue('')
  expect(requests).toHaveLength(1)
  expect(requests[0].runId).toBe('run-a')
})