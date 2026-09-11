import { expect, test } from '@playwright/test'

const passage = {
  passage_id: 'pass-fixture',
  passage_text: 'Situated testimony passage.',
  passage_label: 'Interview extract',
  speaker_or_source: 'Named speaker',
  source_type: 'interview',
  source_reference: 'Interview transcript, page 3',
  source_date: '2013-05-01',
  access_status: 'restricted',
  ingestion_method: 'imported',
  memory_position_note: 'Retrospective account.',
  status: 'unresolved',
  mappings: [{
    mapping_id: 'map-fixture',
    passage_id: 'pass-fixture',
    query_id: 'query-fixture',
    chunk_id: null,
    document_id: null,
    relation_type: 'no_documentary_trace',
    confidence_or_status: 'candidate_no_result',
    reviewer_note: 'The current digitised corpus does not establish this account.',
    source_metadata_json: {}
  }]
}

test('a persisted no-trace mapping saves its canonical relation and nominates a scoped Absences event', async ({ page }) => {
  let mappingUpdate
  let nomination
  await page.route('**/api/cross-read/passages', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ count: 1, passages: [passage] })
  }))
  await page.route('**/api/cross-read/passages/pass-fixture', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify(passage)
  }))
  await page.route('**/api/cross-read/mappings/map-fixture', async (route) => {
    mappingUpdate = route.request().postDataJSON()
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ...passage.mappings[0], ...mappingUpdate }) })
  })
  await page.route('**/api/cross-read/mappings/map-fixture/nominate-missingness', async (route) => {
    nomination = route.request().postDataJSON()
    await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ event_id: 'miss-fixture' }) })
  })

  await page.goto('/cross-readings')
  const relationType = page.getByRole('combobox', { name: 'Relation type' })
  await expect(relationType).toHaveValue('no_documentary_trace')
  await page.getByRole('button', { name: 'Save mapping annotation' }).click()
  await expect.poll(() => mappingUpdate).toMatchObject({ relation_type: 'no_documentary_trace' })

  await page.getByRole('button', { name: 'Nominate retrieval condition for Absences' }).click()
  await expect.poll(() => nomination).toEqual({
    confirmed: true,
    reviewer_note: 'The current digitised corpus does not establish this account.'
  })
  await expect(page).toHaveURL(/\/absences\?eventId=miss-fixture/)
})