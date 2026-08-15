import { test, expect } from '@playwright/test'

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
  await expect(page.getByRole('heading', { name: 'Source interrogation' })).toBeVisible()
  expect(pageErrors).toEqual([])
})

test('a successful structured interrogation renders separated evidence and source stack', async ({ page }) => {
  const pageErrors = []
  let structuredRouteUsed = false
  page.on('pageerror', (error) => pageErrors.push(error.message))

  await page.route('**/api/experiments/interrogate', async (route) => {
    structuredRouteUsed = true
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'experiment-ddr-1980',
        status: 'completed',
        interpretative_status: 'unassessed',
        answer: 'The authority context identifies a DDR staff record spanning 1980.',
        model: { name: 'granite-local' },
        provenance_validation: { valid: true },
        authority_evidence: [{
          authority_type: 'agent_employment',
          assertion: 'Bruce Archer',
          authority_id: 'BRUCEARCHE',
          role: 'Director of Research',
          tenure: { start_date: '1961-01-01', end_date: '1988-12-31' }
        }],
        documentary_evidence: [{ claim: 'A dated staff record is available.', pid: 'PID-1980', page: 1, chunk_id: 'chunk-ddr-1980' }],
        inferences: [],
        contradictions: [],
        missingness: [],
        follow_up_queries: [],
        retrieved_evidence: [{
          chunk_id: 'chunk-ddr-1980',
          document_id: 'document-ddr-1980',
          pid: 'PID-1980',
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
  await page.getByRole('textbox', { name: 'Research query' }).fill('Who worked at the DDR in 1980?')
  await page.getByRole('button', { name: 'Run interrogation' }).evaluate((button) => button.click())

  await expect(page.getByText('The authority context identifies a DDR staff record spanning 1980.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Database authority context' })).toBeVisible()
  await expect(page.getByText('Bruce Archer | Director of Research | 1961-01-01 to 1988-12-31')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Documentary evidence' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Generated inference' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Scoped missingness' })).toBeVisible()
  await expect(page.locator('.evidence-source-card').getByText('DDR staff record', { exact: true })).toBeVisible()
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