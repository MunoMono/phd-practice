import { test, expect } from '@playwright/test'

const summary = { completeness_cards: [] }

const events = [
  {
    id: 101,
    event_id: 'dev-miss-001',
    type: 'retrieval',
    query_or_entity_or_field: 'women-led administration',
    evidence: 'Development seed: source interrogation returned no chunks for a targeted local query.',
    query_id: 'query-retrieval-001',
    source_document_id: null,
    source_chunk_id: null,
    status: 'reviewing',
    reviewer_note: 'Development seed only. Treat as provisional until retrieval-trail persistence is in place.',
    created_at: '2026-08-17T12:00:00Z'
  },
  {
    id: 202,
    event_id: 'dev-miss-002',
    type: 'descriptive',
    query_or_entity_or_field: 'creator field',
    evidence: 'Development seed: creator metadata is absent on a locally ingested record.',
    query_id: null,
    source_document_id: '606',
    source_chunk_id: null,
    status: 'open',
    reviewer_note: 'Development seed only. Check authority sync before interpreting as archive silence.',
    created_at: '2026-08-17T12:01:00Z'
  },
  {
    id: 303,
    event_id: 'dev-miss-003',
    type: 'institutional',
    query_or_entity_or_field: 'institutional conflict',
    evidence: 'Development seed: description foregrounds projects more than internal contestation.',
    query_id: null,
    source_document_id: '599',
    source_chunk_id: 'chunk-599-1',
    status: 'triaged',
    reviewer_note: 'Development seed only. Surface as caveat, not finding.',
    created_at: '2026-08-17T12:02:00Z'
  }
]

const eventsForType = (type) => type && type !== 'all' ? events.filter((event) => event.type === type) : events

const installMissingnessApi = async (page, requests) => {
  await page.route('**/api/missingness/summary', async (route) => {
    requests.push(route.request().method())
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(summary) })
  })
  await page.route('**/api/missingness/events**', async (route) => {
    requests.push(route.request().method())
    const type = new URL(route.request().url()).searchParams.get('type')
    const filteredEvents = eventsForType(type)
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ count: filteredEvents.length, events: filteredEvents }) })
  })
}

const selectEvent = async (page, eventId) => {
  const row = page.getByRole('row', { name: new RegExp(eventId) })
  await row.dispatchEvent('click')
  await expect(page.locator('#selected-missingness-status')).toBeVisible()
  return row
}

test('selection uses persisted event_id and fully updates review detail without mutation', async ({ page }) => {
  const requests = []
  await installMissingnessApi(page, requests)
  await page.goto('/absences')
  const reviewPane = page.locator('.missingness-workbench__detail-actions').locator('xpath=..')

  await expect(page.locator('tbody tr.app-table-row--selected')).toHaveCount(0)
  await expect(page.getByText('Select a missingness event from the table to review it.')).toBeVisible()
  await expect(page.locator('#selected-missingness-status')).toHaveCount(0)
  await expect(page.locator('#selected-missingness-reviewer-note')).toHaveCount(0)

  const retrievalRow = await selectEvent(page, 'dev-miss-001')
  await expect(retrievalRow).toHaveClass(/app-table-row--selected/)
  await expect(page.getByText('Event ID: dev-miss-001')).toBeVisible()
  await expect(page.getByText('Typology: retrieval')).toBeVisible()
  await expect(page.getByText('Source run: query-retrieval-001')).toBeVisible()
  await expect(reviewPane.getByText(events[0].evidence)).toBeVisible()
  await expect(page.locator('#selected-missingness-status')).toHaveValue('reviewing')
  await expect(page.locator('#selected-missingness-reviewer-note')).toHaveValue(events[0].reviewer_note)

  const descriptiveRow = await selectEvent(page, 'dev-miss-002')
  await expect(descriptiveRow).toHaveClass(/app-table-row--selected/)
  await expect(retrievalRow).not.toHaveClass(/app-table-row--selected/)
  await expect(page.getByText('Event ID: dev-miss-002')).toBeVisible()
  await expect(page.getByText('Typology: descriptive')).toBeVisible()
  await expect(page.getByText('Source document: 606')).toBeVisible()
  await expect(reviewPane.getByText(events[1].evidence)).toBeVisible()
  await expect(page.locator('#selected-missingness-status')).toHaveValue('open')
  await expect(page.locator('#selected-missingness-reviewer-note')).toHaveValue(events[1].reviewer_note)
  await expect(reviewPane.getByText(events[0].evidence)).toHaveCount(0)

  const institutionalRow = await selectEvent(page, 'dev-miss-003')
  await expect(institutionalRow).toHaveClass(/app-table-row--selected/)
  await expect(page.getByText('Event ID: dev-miss-003')).toBeVisible()
  await expect(page.getByText('Typology: institutional')).toBeVisible()
  await expect(page.getByText('Source document: 599')).toBeVisible()
  await expect(page.getByText('Source chunk: chunk-599-1')).toBeVisible()
  await expect(reviewPane.getByText(events[2].evidence)).toBeVisible()
  await expect(page.locator('#selected-missingness-status')).toHaveValue('triaged')
  await expect(page.locator('#selected-missingness-reviewer-note')).toHaveValue(events[2].reviewer_note)
  expect(requests.every((method) => method === 'GET')).toBe(true)
})

test('filtering retains compatible selection and clears excluded or empty results without substitution', async ({ page }) => {
  const requests = []
  await installMissingnessApi(page, requests)
  await page.goto('/absences')

  await selectEvent(page, 'dev-miss-001')
  await page.getByLabel('Typology').selectOption('retrieval')
  await expect(page.getByText('Event ID: dev-miss-001')).toBeVisible()
  await expect(page.locator('tbody tr.app-table-row--selected')).toHaveCount(1)

  await page.getByLabel('Typology').selectOption('all')
  await expect(page.getByRole('row', { name: /dev-miss-003/ })).toBeVisible()
  await selectEvent(page, 'dev-miss-003')
  await page.getByLabel('Typology').selectOption('retrieval')
  await expect(page.getByRole('row', { name: /dev-miss-003/ })).toHaveCount(0)
  await expect(page.getByText('Select a missingness event from the table to review it.')).toBeVisible()
  await expect(page.locator('tbody tr.app-table-row--selected')).toHaveCount(0)
  await expect(page.locator('#selected-missingness-status')).toHaveCount(0)
  await expect(page.getByText('Event ID: dev-miss-003')).toHaveCount(0)

  await page.getByLabel('Typology').selectOption('documentary')
  await expect(page.getByText('No missingness events are recorded for this typology.')).toBeVisible()
  await expect(page.getByText('Select a missingness event from the table to review it.')).toBeVisible()
  await expect(page.locator('tbody tr')).toHaveCount(0)
  expect(requests.every((method) => method === 'GET')).toBe(true)
})

test('an unknown eventId produces a controlled state without fallback selection', async ({ page }) => {
  const requests = []
  await installMissingnessApi(page, requests)
  await page.goto('/absences?eventId=missing-event')

  await expect(page.getByText('Requested missingness event could not be loaded.')).toBeVisible()
  await expect(page.locator('tbody tr.app-table-row--selected')).toHaveCount(0)
  await expect(page.getByText('Select a missingness event from the table to review it.')).toBeVisible()
  await expect(page.locator('#selected-missingness-status')).toHaveCount(0)
  expect(requests.every((method) => method === 'GET')).toBe(true)
})