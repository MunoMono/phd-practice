import { test, expect } from '@playwright/test'

const summary = { completeness_cards: [] }

const events = [
  {
    id: 101,
    event_id: 'dev-miss-001',
    type: 'retrieval',
    query_or_entity_or_field: 'women-led administration',
    evidence: 'Development seed: source interrogation returned no chunks for a targeted local query.',
    query_id: null,
    source_document_id: null,
    source_chunk_id: null,
    status: 'reviewing',
    reviewer_note: 'Persisted retrieval note.',
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
    reviewer_note: 'Persisted descriptive note.',
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
    source_chunk_id: null,
    status: 'triaged',
    reviewer_note: 'Persisted institutional note.',
    created_at: '2026-08-17T12:02:00Z'
  }
]

const eventsForType = (type) => type && type !== 'all' ? events.filter((event) => event.type === type) : events

const installMissingnessApi = async (page, methods) => {
  await page.route('**/api/missingness/summary', async (route) => {
    methods.push(route.request().method())
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(summary) })
  })
  await page.route('**/api/missingness/events**', async (route) => {
    methods.push(route.request().method())
    const type = new URL(route.request().url()).searchParams.get('type')
    const filteredEvents = eventsForType(type)
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ count: filteredEvents.length, events: filteredEvents }) })
  })
}

const selectEvent = async (page, eventId) => {
  const row = page.getByRole('row', { name: new RegExp(eventId) })
  await row.dispatchEvent('click')
  await expect(page.locator('#selected-missingness-reviewer-note')).toBeVisible()
}

test('reviewer-note drafts are local, event-scoped, and independent of status', async ({ page }) => {
  const methods = []
  await installMissingnessApi(page, methods)
  await page.goto('/absences')

  const note = page.locator('#selected-missingness-reviewer-note')
  await expect(note).toHaveCount(0)

  await selectEvent(page, 'dev-miss-001')
  await expect(note).toHaveValue(events[0].reviewer_note)
  await expect(page.getByText('Researcher review note - changes remain local until saved')).toBeVisible()
  const firstDraft = 'Researcher draft one\nwith punctuation: “scope”, semicolon; and apostrophe.'
  await note.fill(firstDraft)
  await page.locator('#selected-missingness-status').selectOption('triaged')
  await expect(note).toHaveValue(firstDraft)

  await selectEvent(page, 'dev-miss-002')
  await expect(note).toHaveValue(events[1].reviewer_note)
  const secondDraft = 'Researcher draft two.'
  await note.fill(secondDraft)

  await selectEvent(page, 'dev-miss-001')
  await expect(note).toHaveValue(firstDraft)
  await selectEvent(page, 'dev-miss-002')
  await expect(note).toHaveValue(secondDraft)
  expect(methods.every((method) => method === 'GET')).toBe(true)
  expect(events[0].reviewer_note).toBe('Persisted retrieval note.')
})

test('empty drafts survive filter exclusion and reselecting their event without mutation', async ({ page }) => {
  const methods = []
  await installMissingnessApi(page, methods)
  await page.goto('/absences')

  const note = page.locator('#selected-missingness-reviewer-note')
  await selectEvent(page, 'dev-miss-003')
  await note.fill('')
  await expect(note).toHaveValue('')

  await page.getByLabel('Typology').selectOption('retrieval')
  await expect(page.getByText('Select a missingness event from the table to review it.')).toBeVisible()
  await expect(note).toHaveCount(0)
  await expect(page.getByRole('row', { name: /dev-miss-001/ })).toBeVisible()

  await page.getByLabel('Typology').selectOption('all')
  await expect(page.getByRole('row', { name: /dev-miss-003/ })).toBeVisible()
  await selectEvent(page, 'dev-miss-003')
  await expect(note).toHaveValue('')
  await expect(page.locator('#selected-missingness-status')).toHaveValue('triaged')
  expect(methods.every((method) => method === 'GET')).toBe(true)
  expect(events[2].reviewer_note).toBe('Persisted institutional note.')
})