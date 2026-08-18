import { test, expect } from '@playwright/test'

const installMemoDownloadCapture = async (page, { failObjectUrl = false } = {}) => {
  await page.addInitScript(({ shouldFailObjectUrl }) => {
    window.__retrievalMemoDownload = {}
    URL.createObjectURL = (blob) => {
      if (shouldFailObjectUrl) {
        throw new Error('Object URL unavailable')
      }
      window.__retrievalMemoDownload.blob = blob
      return 'blob:retrieval-memo'
    }
    URL.revokeObjectURL = (url) => { window.__retrievalMemoDownload.revokedUrl = url }
    HTMLAnchorElement.prototype.click = function click() {
      window.__retrievalMemoDownload.filename = this.download
      window.__retrievalMemoDownload.link = this
    }
  }, { shouldFailObjectUrl: failObjectUrl })
}

const readMemoDownload = (page) => page.evaluate(async () => ({
  content: await window.__retrievalMemoDownload.blob.text(),
  filename: window.__retrievalMemoDownload.filename,
  type: window.__retrievalMemoDownload.blob.type,
  revokedUrl: window.__retrievalMemoDownload.revokedUrl,
  anchorRemoved: !window.__retrievalMemoDownload.link.isConnected
}))

test('a failed structured interrogation preserves the source interrogation interface', async ({ page }) => {
  const pageErrors = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  await page.route('**/api/experiments/interrogate', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Granite runtime not ready for this query.' })
    })
  })

  await page.goto('/source-interrogation')
  const queryInput = page.getByRole('textbox', { name: 'Research query' })
  const query = 'Who worked at the DDR in 1980?'
  await queryInput.fill(query)
  await page.getByRole('button', { name: 'Run interrogation' }).evaluate((button) => button.click())

  await expect(page.getByText('Interrogation failed')).toBeVisible()
  await expect(queryInput).toHaveValue(query)
  await expect(page.getByRole('button', { name: 'Run interrogation' })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Copy retrieval memo' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Download retrieval memo' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Export retrieval trail' })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Source interrogation' })).toBeVisible()
  expect(pageErrors).toEqual([])
})

test('a successful structured interrogation renders separated evidence and source stack', async ({ page }) => {
  const pageErrors = []
  let structuredRouteUsed = false
  let copiedMemo = ''
  page.on('pageerror', (error) => pageErrors.push(error.message))

  await page.addInitScript(() => {
    let memo = ''
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async (text) => { memo = text },
        readText: async () => memo
      }
    })
  })
  await installMemoDownloadCapture(page)

  await page.route('**/api/experiments/interrogate', async (route) => {
    structuredRouteUsed = true
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'experiment-ddr-1980',
        created_at: '2026-08-17T12:00:00Z',
        research_case: 'known_relationship',
        corpus_version: 'corpus_f40d78dbce52',
        retrieval_method: 'postgresql_fts',
        status: 'completed',
        interpretative_status: 'unassessed',
        answer: 'Authority records indicate a DDR role history. Retrieved documents show an activity trace.',
        model: { name: 'granite-local' },
        provenance_validation: { valid: true },
        authority_evidence: [{
          authority_type: 'agent_employment',
          assertion: 'Kenneth Baynes',
          authority_id: 'KENNETHBAY',
          role: 'Research Fellow / later Tutor DEU / later Head of Department DEU',
          tenure: { start_date: '1976-01-01', end_date: '1985-12-31' }
        }],
        documentary_evidence: [{ claim: 'A dated staff record is available.', pid: 'PID-1980', page: 1, chunk_id: 'chunk-ddr-1980' }],
        inferences: [],
        contradictions: [],
        missingness: [],
        follow_up_queries: [],
        retrieval_diagnostics: {
          result_count: 1,
          min_score: 0.9,
          max_score: 0.9,
          possible_low_recall: false,
          retrieval_redundancy: false,
          evidence_concentration: false,
          provenance_incomplete: false,
          notes: []
        },
        retrieval: {
          normalised_query: 'Who worked at the DDR in 1980?',
          expanded_query: 'Who worked at the DDR in 1980? OR "Bruce Archer"',
          query_expansions: ['Bruce Archer']
        },
        retrieved_evidence: [{
          chunk_id: 'chunk-ddr-1980',
          rank: 1,
          document_id: 'document-ddr-1980',
          pid: 'PID-1980',
          archive_record_pid: 'record-1980',
          page_start: 1,
          score: 0.9,
          archive_resolution_status: 'resolved_current',
          excerpt: 'DDR staff record, 1980.',
          snapshot: { title: 'DDR staff record', provenance: { record_public_uri: 'https://ddrarchive.org/id/record/1980' } }
        }]
      })
    })
  })

  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('How did Ken Baynes appear across DDR records?')
  await page.getByRole('button', { name: 'Run interrogation' }).evaluate((button) => button.click())

  await expect(page.getByText('Authority records indicate a DDR role history. Retrieved documents show an activity trace.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Database authority context' })).toBeVisible()
  await expect(page.getByText('Kenneth Baynes | Staff code: KENNETHBAY | Research Fellow / later Tutor DEU / later Head of Department DEU | 1976-01-01 to 1985-12-31')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Documentary evidence' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Generated inference' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Retrieval diagnostics' })).toBeVisible()
  await expect(page.getByText('Retrieved passages: 1.')).toBeVisible()
  await expect(page.getByText('Lexical score range: 0.900 to 0.900.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Scoped evidential limits' })).toBeVisible()
  await expect(page.getByText('No scoped evidential limits were recorded.')).toBeVisible()
  const sourceCard = page.locator('.evidence-source-card')
  await expect(sourceCard.getByText('DDR staff record', { exact: true })).toBeVisible()
  await expect(sourceCard.getByText('PID-1980', { exact: true })).toBeVisible()
  await expect(sourceCard.getByText('Chunk ID: chunk-ddr-1980')).toBeVisible()
  await expect(sourceCard.getByText('Page/Section: 1')).toBeVisible()
  await expect(sourceCard.getByText('DDR staff record, 1980.')).toBeVisible()
  await expect(sourceCard.getByRole('button', { name: 'Copy citation' })).toBeVisible()
  await expect(sourceCard.getByRole('button', { name: 'Open in sources' })).toBeVisible()
  await expect(sourceCard.getByRole('button', { name: 'Locate in semantic atlas' })).toBeVisible()
  await expect(sourceCard.getByRole('button', { name: 'View provenance' })).toBeVisible()
  await expect(page.getByLabel('Validation status')).toHaveCount(0)
  await expect(page.locator('[id^="evidence-status-"]')).toHaveCount(0)
  await expect(page.getByLabel('Overall claim status')).not.toBeVisible()
  await expect(page.locator('#overall-evidence-status')).toHaveCount(0)
  await expect(page.locator('.tracer__answer-controls').getByText('Supported', { exact: true })).toHaveCount(0)
  await expect(page.locator('.tracer__answer-controls').getByText('Partially supported', { exact: true })).toHaveCount(0)
  await expect(page.locator('.tracer__answer-controls').getByText('Contradicted', { exact: true })).toHaveCount(0)
  await expect(page.locator('.tracer__answer-controls').getByText('Speculative', { exact: true })).toHaveCount(0)
  await expect(page.locator('.tracer__answer-controls').getByText('Needs review', { exact: true })).toHaveCount(0)
  const copyRequests = []
  const requestListener = (request) => {
    if (request.url().includes('/api/experiments')) copyRequests.push(request.method())
  }
  page.on('request', requestListener)
  await page.getByRole('button', { name: 'Copy retrieval memo' }).evaluate((button) => button.click())
  copiedMemo = await page.evaluate(() => navigator.clipboard.readText())
  page.off('request', requestListener)
  await expect(page.getByText('Retrieval memo copied')).toBeVisible()
  expect(copiedMemo).toContain('# Turin retrieval memo')
  expect(copiedMemo).toContain('How did Ken Baynes appear across DDR records?')
  expect(copiedMemo).not.toContain('Query: Not available')
  expect(copiedMemo).toContain('Run ID: experiment-ddr-1980')
  expect(copiedMemo).toContain('Corpus: corpus_f40d78dbce52')
  expect(copiedMemo).toContain('Lexical score range: 0.900 to 0.900')
  expect(copiedMemo).toContain('Archive record PID: record-1980')
  expect(copiedMemo).toContain('## Archive / database authority context')
  expect(copiedMemo).toContain('Staff code: KENNETHBAY')
  expect(copiedMemo).toContain('## Generated interpretation')
  expect(copiedMemo).toContain('## Provenance validation')
  expect(copiedMemo).not.toMatch(/validation status|partially supported|speculative|needs review/i)
  expect(copyRequests).toEqual([])
  const downloadRequests = []
  const downloadRequestListener = (request) => {
    if (request.url().includes('/api/experiments')) downloadRequests.push(request.method())
  }
  page.on('request', downloadRequestListener)
  await page.getByRole('button', { name: 'Download retrieval memo' }).evaluate((button) => button.click())
  const download = await readMemoDownload(page)
  page.off('request', downloadRequestListener)
  expect(download.content).toBe(copiedMemo)
  expect(download.filename).toBe('turin-retrieval-memo-experiment-ddr-1980.md')
  expect(download.type).toBe('text/markdown;charset=utf-8')
  expect(download.revokedUrl).toBe('blob:retrieval-memo')
  expect(download.anchorRemoved).toBe(true)
  expect(downloadRequests).toEqual([])
  await expect(page.getByRole('heading', { name: 'Source interrogation' })).toBeVisible()
  expect(structuredRouteUsed).toBe(true)
  expect(pageErrors).toEqual([])
})

test('a project authority interrogation renders job records without documentary claims', async ({ page }) => {
  const pageErrors = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  await page.route('**/api/experiments/interrogate', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'experiment-project-97',
        status: 'completed',
        interpretative_status: 'unassessed',
        answer: 'Matching DDR project records are listed as database authority context.',
        model: {},
        provenance_validation: { valid: true },
        authority_evidence: [{
          authority_type: 'ddr_projects',
          authority_id: '97',
          job_number: 97,
          title: 'The application of computer aided architectural design to METHOD building: Phase 1',
          funder_name: 'Consortium for METHOD building',
          duration_text: '<= 12 months',
          project_lead_name: 'Andrew Garnett'
        }],
        documentary_evidence: [],
        inferences: [],
        contradictions: [],
        missingness: [],
        follow_up_queries: [],
        retrieved_evidence: []
      })
    })
  })

  await page.goto('/source-interrogation')
  const queryInput = page.getByRole('textbox', { name: 'Research query' })
  await queryInput.fill('What was DDR job 97?')
  await page.getByRole('button', { name: 'Run interrogation' }).evaluate((button) => button.click())

  await expect(queryInput).toHaveValue('What was DDR job 97?')
  await expect(page.getByText('Job 97 | The application of computer aided architectural design to METHOD building: Phase 1 | Funder: Consortium for METHOD building | Duration: <= 12 months | Project lead: Andrew Garnett')).toBeVisible()
  await expect(page.getByText('No documentary claim is asserted beyond the retrieved source stack.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Source interrogation' })).toBeVisible()
  expect(pageErrors).toEqual([])
})

test('a structural database authority renders as labelled authority context', async ({ page }) => {
  await page.route('**/api/experiments/interrogate', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'experiment-fonds',
        status: 'completed',
        interpretative_status: 'unassessed',
        answer: 'Matching database authority records are listed as database authority context.',
        model: {},
        provenance_validation: { valid: true },
        authority_evidence: [{
          authority_type: 'ref_fonds',
          authority_id: 'fonds-1',
          label: 'DDR project files',
          description: 'Controlled fonds record.',
          authority_classification: 'database authority record'
        }],
        documentary_evidence: [], inferences: [], contradictions: [], missingness: [], follow_up_queries: [], retrieved_evidence: []
      })
    })
  })

  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('What fonds are represented in the system?')
  await page.getByRole('button', { name: 'Run interrogation' }).evaluate((button) => button.click())

  await expect(page.getByText('DDR project files | ref_fonds | database authority record | Controlled fonds record.')).toBeVisible()
  await expect(page.getByText('No documentary claim is asserted beyond the retrieved source stack.')).toBeVisible()
})

test('an interpretative authority is labelled as a database classification', async ({ page }) => {
  await page.route('**/api/experiments/interrogate', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'experiment-methodology',
        status: 'completed',
        interpretative_status: 'unassessed',
        answer: 'Matching database classification records are listed separately; they are system classifications, not source-document assertions.',
        model: {},
        provenance_validation: { valid: true },
        authority_evidence: [{
          authority_type: 'ref_methodology',
          authority_id: 'method-1',
          label: 'Action research',
          authority_classification: 'database authority classification'
        }],
        documentary_evidence: [], inferences: [], contradictions: [], missingness: [], follow_up_queries: [], retrieved_evidence: []
      })
    })
  })

  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('Which methodology classifications are available?')
  await page.getByRole('button', { name: 'Run interrogation' }).evaluate((button) => button.click())

  await expect(page.getByText('Action research | ref_methodology | database authority classification')).toBeVisible()
  await expect(page.getByText('they are system classifications, not source-document assertions.')).toBeVisible()
})

test('a zero retrieval result distinguishes retrieval scope from historical absence', async ({ page }) => {
  await page.addInitScript(() => {
    let memo = ''
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async (text) => { memo = text }, readText: async () => memo } })
  })
  await installMemoDownloadCapture(page)
  await page.route('**/api/experiments/interrogate', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'experiment-zero', status: 'completed_with_missingness', interpretative_status: 'researcher_review_required',
        answer: 'The supplied authority and retrieved corpus do not establish this.', model: {}, provenance_validation: { valid: true },
        authority_evidence: [], documentary_evidence: [], inferences: [], contradictions: [], follow_up_queries: [], retrieved_evidence: [],
        missingness: [{ scope: 'retrieved corpus', category: 'zero_retrieval', explanation: 'No source passage was retrieved by this query.' }],
        retrieval_diagnostics: { result_count: 0, possible_low_recall: true, notes: ['No source passage was retrieved by this query. This is a retrieval-scope result, not evidence of historical absence.'], extraction_issue_present: false }
      })
    })
  })

  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('What does the frozen corpus establish about xylophonic counterfactual nomenclature?')
  await page.getByRole('button', { name: 'Run interrogation' }).evaluate((button) => button.click())

  await expect(page.getByRole('heading', { name: 'Retrieval diagnostics' })).toBeVisible()
  await expect(page.getByText('Retrieved passages: 0.')).toBeVisible()
  await expect(page.getByText('This is a retrieval-scope result, not evidence of historical absence.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Scoped evidential limits' })).toBeVisible()
  await expect(page.getByText(/System-derived:.*No source passage was retrieved/)).toBeVisible()
  await expect(page.getByText(/Generated-response validation failure/)).not.toBeVisible()
  await expect(page.getByText(/OCR|extraction/i)).not.toBeVisible()
  await expect(page.getByRole('button', { name: 'Copy retrieval memo' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Export retrieval trail' })).toBeVisible()
  await page.getByRole('button', { name: 'Copy retrieval memo' }).evaluate((button) => button.click())
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain('This is a retrieval-scope result, not evidence of historical absence.')
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain('System-derived | Scope: retrieved corpus | Category: zero_retrieval')
  await expect(page.getByRole('button', { name: 'Download retrieval memo' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Export retrieval trail' })).toBeVisible()
  await page.getByRole('button', { name: 'Download retrieval memo' }).evaluate((button) => button.click())
  const download = await readMemoDownload(page)
  expect(download.content).toContain('This is a retrieval-scope result, not evidence of historical absence.')
  expect(download.content).not.toContain('historical or archive-wide absence is established')
})

test('a temporal evidential limit preserves the requested-year scope', async ({ page }) => {
  await page.route('**/api/experiments/interrogate', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'experiment-temporal', status: 'completed_with_missingness', interpretative_status: 'researcher_review_required', answer: 'The supplied authority and retrieved corpus do not establish this.',
        model: {}, provenance_validation: { valid: true }, authority_evidence: [], documentary_evidence: [], inferences: [], contradictions: [], follow_up_queries: [], retrieved_evidence: [],
        missingness: [{ scope: 'retrieved corpus for 1970', category: 'insufficient_temporally_valid_evidence', explanation: 'No retrieved source passage had an explicit temporal basis for the requested claim.' }],
        retrieval_diagnostics: { result_count: 0, requested_years: [1970], temporally_valid_result_count: 0, temporal_rejections: [], possible_low_recall: true, notes: ['No source passage was retrieved by this query. This is a retrieval-scope result, not evidence of historical absence.'] }
      })
    })
  })

  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('What does the corpus establish about women working in the DDR in 1970?')
  await page.getByRole('button', { name: 'Run interrogation' }).evaluate((button) => button.click())

  await expect(page.getByText('Requested temporal scope: 1970.')).toBeVisible()
  await expect(page.getByText('Temporally valid retrieved passages: 0.')).toBeVisible()
  await expect(page.getByText(/System-derived:.*explicit temporal basis/)).toBeVisible()
  await expect(page.getByText(/women working in the DDR were absent/i)).not.toBeVisible()
})

test('a parse failure preserves retrieved evidence and labels generated-response validation separately', async ({ page }) => {
  await page.addInitScript(() => {
    let memo = ''
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async (text) => { memo = text }, readText: async () => memo } })
  })
  await installMemoDownloadCapture(page)
  await page.route('**/api/experiments/interrogate', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'experiment-parse', status: 'failed', interpretative_status: 'researcher_review_required', error_code: 'parse_failure', error_message: 'Required response field missing.',
        answer: 'No generated documentary claim is shown because structured response validation failed.', model: { name: 'granite-local' }, provenance_validation: { valid: false }, authority_evidence: [], documentary_evidence: [], inferences: [], contradictions: [], follow_up_queries: [],
        missingness: [{ scope: 'generated response', category: 'parse_failure', explanation: 'A required structured response field was missing.' }],
        retrieval_diagnostics: { result_count: 1, max_score: 0.7, min_score: 0.7, possible_low_recall: false, retrieval_redundancy: false, notes: [] },
        retrieved_evidence: [{ chunk_id: 'chunk-parse', document_id: 'document-parse', pid: 'PID-PARSE', page_start: 2, score: 0.7, archive_resolution_status: 'resolved_current', excerpt: 'Retrieved documentary evidence.', snapshot: { title: 'Retrieved source', provenance: {} } }]
      })
    })
  })

  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('What relationship does the supplied archival evidence establish between Bruce Archer and design education?')
  await page.getByRole('button', { name: 'Run interrogation' }).evaluate((button) => button.click())

  await expect(page.getByText('Generated-response validation failure')).toBeVisible()
  await expect(page.getByText(/Documentary evidence may have been retrieved/)).toBeVisible()
  await expect(page.getByText('Retrieved passages: 1.')).toBeVisible()
  await expect(page.locator('.evidence-source-card').getByText('Retrieved source', { exact: true })).toBeVisible()
  await expect(page.getByText('No scoped evidential limits were recorded.')).toBeVisible()
  await expect(page.getByText('Retrieval / provenance issue')).not.toBeVisible()
  await page.getByRole('button', { name: 'Copy retrieval memo' }).evaluate((button) => button.click())
  await expect(page.getByText('Retrieval memo copied')).toBeVisible()
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain('Retrieved source')
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain('Generated-response validation failure')
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).not.toContain('No source passage was retrieved by this query.')
  await expect(page.getByRole('button', { name: 'Download retrieval memo' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Export retrieval trail' })).toBeVisible()
  await page.getByRole('button', { name: 'Download retrieval memo' }).evaluate((button) => button.click())
  const download = await readMemoDownload(page)
  expect(download.content).toContain('Retrieved source')
  expect(download.content).toContain('Generated-response validation failure')
})

test('a Granite runtime failure keeps retrieved evidence without claiming corpus absence', async ({ page }) => {
  await page.addInitScript(() => {
    let memo = ''
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async (text) => { memo = text }, readText: async () => memo } })
  })
  await installMemoDownloadCapture(page)
  await page.route('**/api/experiments/interrogate', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'experiment-runtime', status: 'failed', interpretative_status: 'researcher_review_required', error_code: 'granite_failure', answer: 'No generated response is available.', model: {}, provenance_validation: { valid: false },
        authority_evidence: [], documentary_evidence: [], inferences: [], contradictions: [], missingness: [], follow_up_queries: [], retrieval_diagnostics: { result_count: 1, notes: [] },
        retrieved_evidence: [{ chunk_id: 'chunk-runtime', document_id: 'document-runtime', pid: 'PID-RUNTIME', page_start: 1, score: 0.8, archive_resolution_status: 'resolved_current', excerpt: 'Retrieved before runtime failure.', snapshot: { title: 'Runtime source', provenance: {} } }]
      })
    })
  })

  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('A query with a Granite timeout')
  await page.getByRole('button', { name: 'Run interrogation' }).evaluate((button) => button.click())

  await expect(page.getByText('Model runtime failure')).toBeVisible()
  await expect(page.getByText('Retrieved passages: 1.')).toBeVisible()
  await expect(page.locator('.evidence-source-card').getByText('Runtime source', { exact: true })).toBeVisible()
  await expect(page.getByText(/historical absence/i)).toBeVisible()
  await expect(page.getByText('Generated-response validation failure')).not.toBeVisible()
  await page.getByRole('button', { name: 'Copy retrieval memo' }).evaluate((button) => button.click())
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain('Runtime source')
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain('Model runtime failure')
  await expect(page.getByRole('button', { name: 'Download retrieval memo' })).toBeVisible()
  await page.getByRole('button', { name: 'Download retrieval memo' }).evaluate((button) => button.click())
  const download = await readMemoDownload(page)
  expect(download.content).toContain('Runtime source')
  expect(download.content).toContain('Model runtime failure')
})

test('clipboard rejection preserves the current result and shows a controlled copy failure', async ({ page }) => {
  const pageErrors = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async () => { throw new Error('Clipboard rejected') } } })
  })
  await page.route('**/api/experiments/interrogate', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'experiment-copy-error', status: 'completed', interpretative_status: 'unassessed', answer: 'Current answer remains visible.', model: {}, provenance_validation: { valid: true },
        authority_evidence: [], documentary_evidence: [], inferences: [], contradictions: [], missingness: [], follow_up_queries: [], retrieved_evidence: [], retrieval_diagnostics: { result_count: 0, notes: [] }
      })
    })
  })

  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('Clipboard rejection')
  await page.getByRole('button', { name: 'Run interrogation' }).evaluate((button) => button.click())
  await page.getByRole('button', { name: 'Copy retrieval memo' }).evaluate((button) => button.click())

  await expect(page.getByText('Retrieval memo could not be copied to the clipboard')).toBeVisible()
  await expect(page.getByText('Current answer remains visible.')).toBeVisible()
  expect(pageErrors).toEqual([])
})

test('a usable result without a run ID uses the deterministic retrieval memo filename fallback', async ({ page }) => {
  await installMemoDownloadCapture(page)
  await page.route('**/api/experiments/interrogate', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'completed', interpretative_status: 'unassessed', answer: 'Current result without a run ID.', model: {}, provenance_validation: { valid: true },
        authority_evidence: [], documentary_evidence: [], inferences: [], contradictions: [], missingness: [], follow_up_queries: [], retrieved_evidence: [], retrieval_diagnostics: { result_count: 0, notes: [] }
      })
    })
  })

  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('A question that must not determine the filename')
  await page.getByRole('button', { name: 'Run interrogation' }).evaluate((button) => button.click())
  await page.getByRole('button', { name: 'Download retrieval memo' }).evaluate((button) => button.click())

  const download = await readMemoDownload(page)
  expect(download.filename).toBe('turin-retrieval-memo.md')
  expect(download.filename).not.toContain('question')
})

test('download failure preserves the current result and shows controlled feedback', async ({ page }) => {
  const pageErrors = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  await installMemoDownloadCapture(page, { failObjectUrl: true })
  await page.route('**/api/experiments/interrogate', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'experiment-download-error', status: 'completed', interpretative_status: 'unassessed', answer: 'Current answer remains visible.', model: {}, provenance_validation: { valid: true },
        authority_evidence: [], documentary_evidence: [], inferences: [], contradictions: [], missingness: [], follow_up_queries: [], retrieved_evidence: [], retrieval_diagnostics: { result_count: 0, notes: [] }
      })
    })
  })

  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('Object URL failure')
  await page.getByRole('button', { name: 'Run interrogation' }).evaluate((button) => button.click())
  const requests = []
  const requestListener = (request) => {
    if (request.url().includes('/api/experiments')) requests.push(request.method())
  }
  page.on('request', requestListener)
  await page.getByRole('button', { name: 'Download retrieval memo' }).evaluate((button) => button.click())
  page.off('request', requestListener)

  await expect(page.getByText('Retrieval memo could not be downloaded')).toBeVisible()
  await expect(page.getByText('The current result remains unchanged.')).toBeVisible()
  await expect(page.getByText('Current answer remains visible.')).toBeVisible()
  expect(requests).toEqual([])
  expect(pageErrors).toEqual([])
})

test('a persisted interrogation exports only the authoritative retrieval trail JSON', async ({ page }) => {
  await installMemoDownloadCapture(page)
  const exportedRun = {
    run_id: 'experiment-trail-1', status: 'completed', assessment: { notes: 'Separate assessment snapshot.' }, retrieved_evidence: [],
    prompt: { question: 'Authoritative export question' }, retrieval: { normalised_query: 'Authoritative export question' }
  }
  await page.route('**/api/experiments/interrogate', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'experiment-trail-1', status: 'completed', interpretative_status: 'unassessed', answer: 'Persisted answer.', model: {}, provenance_validation: { valid: true },
        authority_evidence: [], documentary_evidence: [], inferences: [], contradictions: [], missingness: [], follow_up_queries: [], retrieved_evidence: [], retrieval_diagnostics: { result_count: 0, notes: [] }
      })
    })
  })
  await page.route('**/api/experiments/experiment-trail-1/export', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(exportedRun) }))

  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('Authoritative export question')
  await page.getByRole('button', { name: 'Run interrogation' }).evaluate((button) => button.click())
  await expect(page).toHaveURL(/runId=experiment-trail-1/)
  await page.getByRole('button', { name: 'Export retrieval trail' }).evaluate((button) => button.click())

  const download = await readMemoDownload(page)
  expect(download.filename).toBe('turin-retrieval-trail-experiment-trail-1.json')
  expect(download.type).toBe('application/json;charset=utf-8')
  expect(JSON.parse(download.content)).toEqual(exportedRun)
  expect(download.content).not.toMatch(/validation[_ ]status|partially supported|speculative|needs review/i)
  expect(download.revokedUrl).toBe('blob:retrieval-memo')
  expect(download.anchorRemoved).toBe(true)
})

test('retrieval-trail export failure preserves the persisted result without a transient fallback', async ({ page }) => {
  await installMemoDownloadCapture(page)
  await page.route('**/api/experiments/interrogate', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'experiment-export-error', status: 'completed', interpretative_status: 'unassessed', answer: 'Persisted answer remains visible.', model: {}, provenance_validation: { valid: true },
        authority_evidence: [], documentary_evidence: [], inferences: [], contradictions: [], missingness: [], follow_up_queries: [], retrieved_evidence: [], retrieval_diagnostics: { result_count: 0, notes: [] }
      })
    })
  })
  await page.route('**/api/experiments/experiment-export-error/export', async (route) => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Export unavailable' }) }))

  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('Export failure')
  await page.getByRole('button', { name: 'Run interrogation' }).evaluate((button) => button.click())
  await page.getByRole('button', { name: 'Export retrieval trail' }).evaluate((button) => button.click())

  await expect(page.getByText('Retrieval trail could not be exported')).toBeVisible()
  await expect(page.getByText('The current interrogation result remains unchanged.')).toBeVisible()
  await expect(page.getByText('Persisted answer remains visible.')).toBeVisible()
  await expect.poll(() => page.evaluate(() => window.__retrievalMemoDownload.blob)).toBeFalsy()
})

test('returning to a persisted run URL rehydrates immutable evidence without a new interrogation', async ({ page }) => {
  const requests = []
  const persistedRun = {
    run_id: 'experiment-restore-1', created_at: '2026-08-17T12:00:00Z', research_case: 'known_relationship', corpus_version: 'corpus_f40d78dbce52', retrieval_method: 'postgresql_fts',
    retrieval: { normalised_query: 'Restore this run', expanded_query: 'Restore this run' }, retrieval_diagnostics: { result_count: 1, min_score: 0.5, max_score: 0.5, notes: [] },
    authority_context: { contexts: [] }, model: { name: 'granite-local' }, structured_response: { answer: 'Restored immutable answer.', evidence: [], inferences: [], contradictions: [], missingness: [], follow_up_queries: [] },
    provenance_validation: { valid: true }, status: 'completed', interpretative_status: 'unassessed', error_code: null, error_message: null, assessment: { notes: 'Researcher-only snapshot.' },
    retrieved_evidence: [{ chunk_id: 'chunk-restored', rank: 1, document_id: 'document-restored', pid: 'PID-RESTORED', archive_record_pid: 'record-restored', page_start: 4, score: 0.5, archive_resolution_status: 'resolved_current', excerpt: 'Restored evidence.', snapshot: { title: 'Restored source', provenance: {} } }],
    prompt: { question: 'Restore this run' }
  }
  await page.route('**/api/experiments/**', async (route) => {
    requests.push({ url: route.request().url(), method: route.request().method() })
    if (route.request().url().endsWith('/experiment-restore-1')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(persistedRun) })
      return
    }
    await route.continue()
  })

  await page.goto('/source-interrogation?runId=experiment-restore-1')
  await expect(page.getByText('Restored immutable answer.')).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Research query' })).toHaveValue('Restore this run')
  await expect(page.locator('.evidence-source-card').getByText('Restored source', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Validation status')).toHaveCount(0)
  await expect(page.locator('[id^="evidence-status-"]')).toHaveCount(0)
  await expect(page.getByText('Researcher-only snapshot.')).toHaveCount(0)
  await page.goto('/sources')
  await page.goBack()
  await expect(page.getByText('Restored immutable answer.')).toBeVisible()

  const experimentRequests = requests.filter((request) => request.url.includes('/api/experiments'))
  expect(experimentRequests).toHaveLength(2)
  expect(experimentRequests.every((request) => request.method === 'GET')).toBe(true)
  expect(experimentRequests.every((request) => request.url.endsWith('/experiment-restore-1'))).toBe(true)
})

test('an invalid saved interrogation URL shows controlled load feedback without rerunning retrieval', async ({ page }) => {
  const requests = []
  page.on('request', (request) => {
    if (request.url().includes('/api/experiments')) requests.push(request.method())
  })

  await page.goto('/source-interrogation?runId=not-a-persisted-run')

  await expect(page.getByText('Saved interrogation could not be loaded')).toBeVisible()
  await expect(page.getByText('The requested saved interrogation identifier is invalid.')).toBeVisible()
  await expect(page.getByText('No answer returned yet. Submit a query to begin evidence tracing.')).toBeVisible()
  expect(requests).not.toContain('POST')
})

test('rehydration preserves persisted zero-retrieval and model failure states', async ({ page }) => {
  const persistedRuns = {
    'experiment-rehydrate-zero': {
      run_id: 'experiment-rehydrate-zero', created_at: '2026-08-17T12:00:00Z', research_case: 'scoped_missingness', corpus_version: 'corpus_f40d78dbce52', retrieval_method: 'postgresql_fts', retrieval: {},
      retrieval_diagnostics: { result_count: 0, possible_low_recall: true, notes: ['No source passage was retrieved by this query. This is a retrieval-scope result, not evidence of historical absence.'] }, authority_context: { contexts: [] }, model: {},
      structured_response: { answer: 'The supplied authority and retrieved corpus do not establish this.', evidence: [], inferences: [], contradictions: [], missingness: [{ scope: 'retrieved corpus', category: 'zero_retrieval', explanation: 'No source passage was retrieved by this query.' }], follow_up_queries: [] }, provenance_validation: { valid: true }, status: 'completed_with_missingness', interpretative_status: 'researcher_review_required', retrieved_evidence: [], prompt: { question: 'Zero retrieval restoration' }
    },
    'experiment-rehydrate-parse': {
      run_id: 'experiment-rehydrate-parse', created_at: '2026-08-17T12:00:00Z', research_case: 'known_relationship', corpus_version: 'corpus_f40d78dbce52', retrieval_method: 'postgresql_fts', retrieval: {}, retrieval_diagnostics: { result_count: 1, notes: [] }, authority_context: { contexts: [] }, model: {},
      structured_response: { answer: 'No generated documentary claim is shown because structured response validation failed.', evidence: [], inferences: [], contradictions: [], missingness: [{ scope: 'generated response', category: 'parse_failure', explanation: 'Response could not be parsed.' }], follow_up_queries: [] }, provenance_validation: { valid: false }, status: 'failed', interpretative_status: 'researcher_review_required', error_code: 'parse_failure', error_message: 'Response could not be parsed.', prompt: { question: 'Parse failure restoration' },
      retrieved_evidence: [{ chunk_id: 'chunk-parse-restore', rank: 1, document_id: 'document-parse-restore', pid: 'PID-PARSE-RESTORE', page_start: 2, score: 0.7, archive_resolution_status: 'resolved_current', excerpt: 'Retained parse evidence.', snapshot: { title: 'Parse restored source', provenance: {} } }]
    },
    'experiment-rehydrate-runtime': {
      run_id: 'experiment-rehydrate-runtime', created_at: '2026-08-17T12:00:00Z', research_case: 'known_relationship', corpus_version: 'corpus_f40d78dbce52', retrieval_method: 'postgresql_fts', retrieval: {}, retrieval_diagnostics: { result_count: 1, notes: [] }, authority_context: { contexts: [] }, model: {},
      structured_response: { answer: 'No generated response is available.', evidence: [], inferences: [], contradictions: [], missingness: [], follow_up_queries: [] }, provenance_validation: { valid: false }, status: 'failed', interpretative_status: 'researcher_review_required', error_code: 'granite_failure', error_message: 'Granite timeout.', prompt: { question: 'Runtime failure restoration' },
      retrieved_evidence: [{ chunk_id: 'chunk-runtime-restore', rank: 1, document_id: 'document-runtime-restore', pid: 'PID-RUNTIME-RESTORE', page_start: 1, score: 0.8, archive_resolution_status: 'resolved_current', excerpt: 'Retained runtime evidence.', snapshot: { title: 'Runtime restored source', provenance: {} } }]
    }
  }
  await page.route('**/api/experiments/experiment-rehydrate-*', async (route) => {
    const runId = route.request().url().split('/').pop()
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(persistedRuns[runId]) })
  })

  await page.goto('/source-interrogation?runId=experiment-rehydrate-zero')
  await expect(page.getByText('This is a retrieval-scope result, not evidence of historical absence.')).toBeVisible()
  await page.goto('/source-interrogation?runId=experiment-rehydrate-parse')
  await expect(page.getByText('Generated-response validation failure')).toBeVisible()
  await expect(page.locator('.evidence-source-card').getByText('Parse restored source', { exact: true })).toBeVisible()
  await page.goto('/source-interrogation?runId=experiment-rehydrate-runtime')
  await expect(page.getByText('Model runtime failure')).toBeVisible()
  await expect(page.locator('.evidence-source-card').getByText('Runtime restored source', { exact: true })).toBeVisible()
})