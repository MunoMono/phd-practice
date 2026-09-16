import { test, expect } from '@playwright/test'

const documents = [
  {
    document_id: 'doc_964614721622_ba420b8ee1f2',
    pid: '964614721622',
    attached_media_pid: '964614721622',
    archive_record_pid: '880612075513',
    asset_pid: '711095685552',
    title: 'RCA calendar',
    publication_year: 1965,
    processing_status: 'completed',
    used_for_ml: true,
    ml_policy_status: 'eligible_page_restricted',
    ml_page_scope: '82'
  },
  {
    document_id: 'doc_964614721622_3584e2e064ab',
    pid: '964614721622',
    attached_media_pid: '964614721622',
    archive_record_pid: '880612075513',
    asset_pid: '320734278529',
    title: 'RCA calendar',
    publication_year: 1975,
    processing_status: 'completed',
    used_for_ml: true,
    ml_policy_status: 'eligible_page_restricted',
    ml_page_scope: '51-52'
  },
  {
    document_id: 'doc_521129471965_08fe2073b7ae',
    pid: '521129471965',
    attached_media_pid: '521129471965',
    archive_record_pid: '788065484899',
    asset_pid: '397420947420',
    title: "Rector's report",
    publication_year: 1980,
    processing_status: 'completed',
    used_for_ml: true,
    ml_policy_status: 'eligible_page_restricted',
    ml_page_scope: '17-19'
  }
]

const getDocument = (documentId) => documents.find((document) => document.document_id === documentId)

const mockSourcesApi = async (page) => {
  await page.route('**/api/documents', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ count: documents.length, documents }) })
  })
  await page.route('**/api/documents/**', async (route) => {
    const match = new URL(route.request().url()).pathname.match(/^\/api\/documents\/([^/]+)(\/ml-annotations)?$/)
    const document = match ? getDocument(decodeURIComponent(match[1])) : null
    if (!document) {
      await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Document not found' }) })
      return
    }

    if (match[2]) {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({
        ...document,
        source_filename: `${document.asset_pid}.pdf`,
        record_public_uri: `https://ddrarchive.org/id/record/${document.archive_record_pid}`
      }) })
      return
    }

    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(document) })
  })
  await page.route('**/api/authorities/summary', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ count: 0, totalRecords: 0 }) })
  })
}

const sourceDetail = (page) => page.locator('h3.corpus-panel__section-title').locator('xpath=..')

const expectExactDetail = async (page, document) => {
  const detail = sourceDetail(page)
  await expect(detail).toContainText(document.title)
  await expect(detail).toContainText(String(document.publication_year))
  await expect(detail).toContainText(document.document_id)
  await expect(detail).toContainText(document.pid)
  await expect(detail).toContainText(document.archive_record_pid)
  await expect(detail).toContainText(document.asset_pid)
  await expect(detail).toContainText('ML eligibility: Included')
  await expect(detail).toContainText(`ML page scope: pp. ${document.ml_page_scope.replace('-', '\u2013')}`)
}

test('a Rector source handoff selects the exact local document and its page scope', async ({ page }) => {
  await mockSourcesApi(page)
  const rector = getDocument('doc_521129471965_08fe2073b7ae')

  await page.goto(`/sources?documentId=${rector.document_id}&pid=${rector.pid}`)

  await expect(page).toHaveURL(new RegExp(`documentId=${rector.document_id}`))
  await expectExactDetail(page, rector)
  await expect(sourceDetail(page)).not.toContainText('doc_964614721622_ba420b8ee1f2')
  await expect(sourceDetail(page)).not.toContainText('RCA calendar')
})

test('an RCA calendar handoff uses document ID rather than a sibling sharing its PID', async ({ page }) => {
  await mockSourcesApi(page)
  const calendar1975 = getDocument('doc_964614721622_3584e2e064ab')

  await page.goto(`/sources?documentId=${calendar1975.document_id}&pid=${calendar1975.pid}`)

  await expectExactDetail(page, calendar1975)
  await expect(sourceDetail(page)).not.toContainText('doc_964614721622_ba420b8ee1f2')
  await expect(sourceDetail(page)).not.toContainText('ML page scope: pp. 82')
})

test('a mismatched, invalid, or PID-only handoff shows a scoped failure without default selection', async ({ page }) => {
  await mockSourcesApi(page)
  const rector = getDocument('doc_521129471965_08fe2073b7ae')

  for (const path of [
    `/sources?documentId=${rector.document_id}&pid=964614721622`,
    '/sources?documentId=not-a-document',
    '/sources?documentId=',
    '/sources?pid=964614721622'
  ]) {
    await page.goto(path)
    await expect(page.getByText('Requested source could not be loaded')).toBeVisible()
    await expect(page.getByRole('heading', { level: 3, name: 'Source detail' })).toBeVisible()
    await expect(page.getByRole('heading', { level: 3, name: 'RCA calendar' })).toHaveCount(0)
  }
})

test('ordinary Sources navigation retains its existing default selection', async ({ page }) => {
  await mockSourcesApi(page)

  await page.goto('/sources')

  await expectExactDetail(page, documents[0])
  await expect(page.getByText('Requested source could not be loaded')).toHaveCount(0)
})

test('a persisted Source interrogation handoff preserves exact selection and browser Back', async ({ page }) => {
  await mockSourcesApi(page)
  const rector = getDocument('doc_521129471965_08fe2073b7ae')
  const requests = []
  const persistedRun = {
    run_id: 'experiment-handoff',
    created_at: '2026-08-17T12:00:00Z',
    research_case: 'known_relationship',
    corpus_version: 'corpus_f40d78dbce52',
    retrieval_method: 'postgresql_fts',
    retrieval: {},
    retrieval_diagnostics: { result_count: 1, notes: [] },
    authority_context: { contexts: [] },
    model: {},
    structured_response: { answer: 'Persisted source handoff.', evidence: [], inferences: [], contradictions: [], missingness: [], follow_up_queries: [] },
    provenance_validation: { valid: true },
    status: 'completed',
    interpretative_status: 'unassessed',
    retrieved_evidence: [{
      chunk_id: 'chunk-rector-1980',
      document_id: rector.document_id,
      pid: rector.pid,
      archive_record_pid: rector.archive_record_pid,
      page_start: 17,
      score: 0.9,
      archive_resolution_status: 'resolved_current',
      excerpt: 'Rector source evidence.',
      snapshot: { title: rector.title, provenance: {} }
    }],
    prompt: { question: 'Restore the Rector source handoff.' }
  }

  await page.route('**/api/experiments/experiment-handoff', async (route) => {
    requests.push(route.request().method())
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(persistedRun) })
  })

  await page.goto('/source-interrogation?runId=experiment-handoff')
  await page.locator('.evidence-source-card').getByRole('button', { name: 'Open in sources' }).evaluate((button) => button.click())

  await expectExactDetail(page, rector)
  await page.goBack()
  await expect(page).toHaveURL(/source-interrogation\?runId=experiment-handoff/)
  await expect(page.getByText('Persisted source handoff.')).toBeVisible()
  await expect(page.locator('.evidence-source-card').getByText("Rector's report", { exact: true })).toBeVisible()
  expect(requests).toEqual(['GET', 'GET'])
})
