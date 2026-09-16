import { test, expect } from '@playwright/test'

const summary = { completeness_cards: [] }

const initialEvents = () => [
  {
    id: 801,
    event_id: 'fixture-miss-a',
    type: 'retrieval',
    query_or_entity_or_field: 'fixture A',
    evidence: 'Fixture A evidence.',
    query_id: null,
    source_document_id: null,
    source_chunk_id: null,
    status: 'open',
    reviewer_note: 'Persisted A note.',
    created_at: '2026-08-17T12:00:00Z',
    updated_at: '2026-08-17T12:00:00Z'
  },
  {
    id: 802,
    event_id: 'fixture-miss-b',
    type: 'descriptive',
    query_or_entity_or_field: 'fixture B',
    evidence: 'Fixture B evidence.',
    query_id: null,
    source_document_id: '606',
    source_chunk_id: null,
    status: 'reviewing',
    reviewer_note: 'Persisted B note.',
    created_at: '2026-08-17T12:01:00Z',
    updated_at: '2026-08-17T12:01:00Z'
  }
]

const installApi = async (page, state, patchHandler) => {
  await page.route('**/api/missingness/summary', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(summary) })
  })
  await page.route('**/api/missingness/events?*', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ count: state.events.length, events: state.events }) })
  })
  await page.route('**/api/missingness/events', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ count: state.events.length, events: state.events }) })
  })
  await page.route('**/api/missingness/events/*', (route) => patchHandler(route, state))
}

const selectEvent = async (page, eventId) => {
  await page.getByRole('row', { name: new RegExp(eventId) }).dispatchEvent('click')
  await expect(page.locator('#selected-missingness-status')).toBeVisible()
}

test('a dirty review saves only captured review fields and rebases matching event drafts', async ({ page }) => {
  const state = { events: initialEvents(), patches: [] }
  await installApi(page, state, async (route, currentState) => {
    const eventId = route.request().url().split('/').pop()
    const payload = route.request().postDataJSON()
    currentState.patches.push({ eventId, payload })
    currentState.events = currentState.events.map((event) => event.event_id === eventId
      ? { ...event, ...payload, updated_at: '2026-08-17T12:05:00Z' }
      : event)
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(currentState.events.find((event) => event.event_id === eventId)) })
  })

  await page.goto('/absences')
  await expect(page.getByRole('button', { name: 'Save review state' })).toHaveCount(0)
  await selectEvent(page, 'fixture-miss-a')
  const saveButton = page.getByRole('button', { name: 'Save review state' })
  await expect(saveButton).toBeDisabled()

  await page.locator('#selected-missingness-status').selectOption('triaged')
  await expect(saveButton).toBeEnabled()
  await page.locator('#selected-missingness-reviewer-note').fill('Saved researcher review note.')
  await saveButton.dispatchEvent('click')
  await expect(page.getByText('Saved', { exact: true })).toBeVisible()
  await expect(saveButton).toBeDisabled()
  expect(state.patches).toEqual([{
    eventId: 'fixture-miss-a',
    payload: { status: 'triaged', reviewer_note: 'Saved researcher review note.' }
  }])
  await expect(page.locator('#selected-missingness-status')).toHaveValue('triaged')
  await expect(page.locator('#selected-missingness-reviewer-note')).toHaveValue('Saved researcher review note.')
  expect(state.events[1]).toMatchObject({ status: 'reviewing', reviewer_note: 'Persisted B note.' })

  await page.goto('/absences')
  await selectEvent(page, 'fixture-miss-a')
  await expect(page.locator('#selected-missingness-status')).toHaveValue('triaged')
  await expect(page.locator('#selected-missingness-reviewer-note')).toHaveValue('Saved researcher review note.')
  expect(state.events[0].updated_at).toBe('2026-08-17T12:05:00Z')
})

test('failed or mismatched saves retain drafts and never apply another event response', async ({ page }) => {
  const state = { events: initialEvents(), patches: [] }
  let returnMismatchedEvent = false
  let failureStatus = 500
  await installApi(page, state, async (route, currentState) => {
    currentState.patches.push(route.request().postDataJSON())
    if (returnMismatchedEvent) {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(currentState.events[1]) })
      return
    }
    await route.fulfill({ status: failureStatus, contentType: 'application/json', body: JSON.stringify({ detail: 'Fixture storage failure.' }) })
  })

  await page.goto('/absences')
  await selectEvent(page, 'fixture-miss-a')
  await page.locator('#selected-missingness-status').selectOption('resolved')
  await page.locator('#selected-missingness-reviewer-note').fill('Preserve after failure.')
  await page.getByRole('button', { name: 'Save review state' }).dispatchEvent('click')
  await expect(page.getByText('Review state could not be saved')).toBeVisible()
  await expect(page.getByText('Your local changes have not been lost.')).toBeVisible()
  await expect(page.locator('#selected-missingness-status')).toHaveValue('resolved')
  await expect(page.locator('#selected-missingness-reviewer-note')).toHaveValue('Preserve after failure.')
  expect(state.events[0]).toMatchObject({ status: 'open', reviewer_note: 'Persisted A note.' })
  await expect(page.getByText('Saved', { exact: true })).toHaveCount(0)

  failureStatus = 404
  await page.getByRole('button', { name: 'Save review state' }).dispatchEvent('click')
  await expect(page.locator('#selected-missingness-status')).toHaveValue('resolved')
  await expect(page.locator('#selected-missingness-reviewer-note')).toHaveValue('Preserve after failure.')
  expect(state.events[0]).toMatchObject({ status: 'open', reviewer_note: 'Persisted A note.' })

  returnMismatchedEvent = true
  await page.getByRole('button', { name: 'Save review state' }).dispatchEvent('click')
  await expect(page.locator('#selected-missingness-status')).toHaveValue('resolved')
  await expect(page.locator('#selected-missingness-reviewer-note')).toHaveValue('Preserve after failure.')
  expect(state.events[0]).toMatchObject({ status: 'open', reviewer_note: 'Persisted A note.' })
  expect(state.events[1]).toMatchObject({ status: 'reviewing', reviewer_note: 'Persisted B note.' })
  await expect(page.getByText('Saved', { exact: true })).toHaveCount(0)
  expect(state.patches).toHaveLength(3)
})

test('event-keyed status drafts survive switching and an in-flight save does not alter a new selection', async ({ page }) => {
  const state = { events: initialEvents(), patches: [] }
  let resolveSave
  const pendingSave = new Promise((resolve) => { resolveSave = resolve })
  await installApi(page, state, async (route, currentState) => {
    const eventId = route.request().url().split('/').pop()
    const payload = route.request().postDataJSON()
    currentState.patches.push({ eventId, payload })
    await pendingSave
    currentState.events = currentState.events.map((event) => event.event_id === eventId
      ? { ...event, ...payload, updated_at: '2026-08-17T12:10:00Z' }
      : event)
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(currentState.events.find((event) => event.event_id === eventId)) })
  })

  await page.goto('/absences')
  await selectEvent(page, 'fixture-miss-a')
  await page.locator('#selected-missingness-status').selectOption('triaged')
  await selectEvent(page, 'fixture-miss-b')
  await selectEvent(page, 'fixture-miss-a')
  await expect(page.locator('#selected-missingness-status')).toHaveValue('triaged')

  await page.locator('#selected-missingness-reviewer-note').fill('Save A while switching.')
  await page.getByRole('button', { name: 'Save review state' }).dispatchEvent('click')
  await expect(page.getByRole('button', { name: 'Save review state' })).toBeDisabled()
  await selectEvent(page, 'fixture-miss-b')
  await expect(page.getByText('Event ID: fixture-miss-b')).toBeVisible()
  await expect(page.locator('#selected-missingness-status')).toHaveValue('reviewing')
  resolveSave()
  await expect(page.getByText('Saved', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Event ID: fixture-miss-b')).toBeVisible()
  await expect(page.locator('#selected-missingness-status')).toHaveValue('reviewing')
  expect(state.events[0]).toMatchObject({ status: 'triaged', reviewer_note: 'Save A while switching.' })
})