import { test, expect } from '@playwright/test'

const summary = {
  completeness_cards: [
    {
      label: 'Local metadata coverage',
      value: '88%',
      note: 'Title, PID, source filename, and publication year across 2 local documents.'
    },
    {
      label: 'Local documents with chunks',
      value: '1/2 documents with chunks',
      note: 'Local document representation in DocumentChunk. This is not frozen-corpus retrieval coverage.'
    },
    {
      label: 'Entity registry',
      value: '0 entity records available',
      note: 'No records are currently stored in the local entity registry when this value is zero.'
    },
    {
      label: 'Institutional missingness events',
      value: '1',
      note: 'Persisted MissingnessEvent rows of type institutional. Check event evidence and reviewer notes before interpretation.'
    }
  ]
}

const retrievalEvent = {
  event_id: 'dev-miss-001',
  type: 'retrieval',
  query_or_entity_or_field: 'women-led administration',
  evidence: 'Development seed: source interrogation returned no chunks for a targeted local query.',
  query_id: null,
  source_document_id: null,
  source_chunk_id: null,
  status: 'reviewing',
  reviewer_note: 'Development seed only. Treat as provisional until retrieval-trail persistence is in place.',
  created_at: '2026-08-17T12:00:00Z'
}

const institutionalEvent = {
  ...retrievalEvent,
  event_id: 'dev-miss-003',
  type: 'institutional',
  query_or_entity_or_field: 'institutional conflict',
  reviewer_note: 'Development seed only. Surface as caveat, not finding.'
}

const installMissingnessApi = async (page) => {
  await page.route('**/api/missingness/summary', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(summary) })
  })
  await page.route('**/api/missingness/events**', async (route) => {
    const type = new URL(route.request().url()).searchParams.get('type')
    const events = type === 'retrieval' ? [retrievalEvent] : [retrievalEvent, institutionalEvent]
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ count: events.length, events }) })
  })
}

test('Absences scopes global diagnostics and preserves typology-filtered events', async ({ page }) => {
  await installMissingnessApi(page)
  await page.goto('/absences')

  await expect(page.getByRole('heading', { name: 'Scoped coverage and missingness diagnostics' })).toBeVisible()
  await expect(page.getByText('Summary cards show global system state. Typology filters apply to the event log and events table below.')).toBeVisible()
  await expect(page.getByText('Local metadata coverage')).toBeVisible()
  await expect(page.getByText('88%')).toBeVisible()
  await expect(page.getByText('Title, PID, source filename, and publication year across 2 local documents.')).toBeVisible()
  await expect(page.getByText('Local documents with chunks')).toBeVisible()
  await expect(page.getByText('This is not frozen-corpus retrieval coverage.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Entity registry' })).toBeVisible()
  await expect(page.getByText('0 entity records available')).toBeVisible()
  await expect(page.getByText('No records are currently stored in the local entity registry when this value is zero.')).toBeVisible()
  await expect(page.getByText('Institutional missingness events')).toBeVisible()
  await expect(page.getByText('Persisted MissingnessEvent rows of type institutional.')).toBeVisible()
  await expect(page.getByText('it is not proof of historical absence.')).toBeVisible()
  await expect(page.getByText(/archive completeness|absent entities/i)).toHaveCount(0)

  const cardsBeforeFilter = await page.locator('.missingness-workbench__completeness-card').allTextContents()
  await page.getByLabel('Typology').selectOption('retrieval')
  await expect(page.getByRole('cell', { name: 'women-led administration' })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'institutional conflict' })).toHaveCount(0)
  await expect(page.locator('.app-list-item__title', { hasText: 'women-led administration' })).toBeVisible()
  expect(await page.locator('.missingness-workbench__completeness-card').allTextContents()).toEqual(cardsBeforeFilter)
})