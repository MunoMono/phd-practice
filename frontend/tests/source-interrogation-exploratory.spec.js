import { expect, test } from '@playwright/test'

test('an exploratory interrogation renders Qwen answer, sources, and provenance without a formal run', async ({ page }) => {
  let requestBody
  await page.route('**/api/runtime/model-info', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ status: 'ready', display_name: 'Qwen3 8B · Q4_K_M' })
  }))
  await page.route('**/api/analysis/interrogate', async (route) => {
    requestBody = route.request().postDataJSON()
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        query_id: 'exploratory-fixture', mode: 'exploratory', status: 'completed', persisted: false,
        answer: 'The supplied documentary passage identifies a project.',
        model: { name: 'qwen3:8b-q4_K_M', display_name: 'Qwen3 8B · Q4_K_M', runtime: 'ollama' },
        corpus_version: 'corpus_f40d78dbce52',
        provenance_validation: { valid: true, source_count: 1 },
        retrieval: {}, retrieval_diagnostics: { result_count: 1, notes: [] },
        retrieved_evidence: [{
          chunk_id: 'chunk-1', document_id: 'doc-1', title: 'Project report', text: 'A documentary passage.',
          pid: '546216480663', archive_record_pid: '637362423718', page_start: 4, rank: 1, score: 0.9,
          archive_resolution_status: 'resolved_current', provenance: { archive_record_pid: '637362423718', asset_pid: '123' }
          , asset_pid: '123', combined_score: 1.2, text_score: 0.9, metadata_score: 0.3, source_nomination_score: 1.2, passage_score: 1.4, source_nomination_channels: ['METADATA_MATCH', 'TEXT_MATCH'], passage_evidence_channel: 'DIRECT_TEXT_MATCH', retrieval_channels: ['TEXT_MATCH', 'METADATA_MATCH'], metadata_matches: [{ field: 'keywords', value: 'Example Person' }], evidence_classification: { subject_named: true, relationship_to_question: 'DIRECT_SUPPORT' }
        }]
        , documentary_evidence: [{ claim: 'A documentary passage.', pid: '546216480663', page: 4 }],
        inferences: [{ claim: 'This may be related across sources.' }],
        missingness: [{ category: 'not_established', explanation: 'The source does not establish supervision.' }]
      })
    })
  })
  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('Describe this harmless development source.')
  await page.getByRole('button', { name: 'Run interrogation' }).click()
  await expect(page.getByText('The supplied documentary passage identifies a project.')).toBeVisible()
  await expect(page.locator('p').filter({ hasText: 'Project report' }).first()).toBeVisible()
  await expect(page.getByText('Provenance enabled')).toBeVisible()
  await expect(page.getByText('Direct support').nth(1)).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Documentary evidence' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Qwen interpretation' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Evidential limits' })).toBeVisible()
  await expect(page.getByText('The source does not establish supervision.')).toBeVisible()
  await page.getByText('Why this source?').click()
  await expect(page.getByText('Nomination channel')).toBeVisible()
  await expect(page.getByText('METADATA_MATCH + TEXT_MATCH')).toBeVisible()
  await expect(page.getByText('Nomination score')).toBeVisible()
  await expect(page.getByText('1.200')).toBeVisible()
  await expect(page.getByText('Metadata: keywords')).toBeVisible()
  await expect(page.getByText('Example Person')).toBeVisible()
  await expect(page.getByText('637362423718 → 546216480663 → 123 → page 4 → chunk-1')).toBeVisible()
  await page.getByText('Why this passage?').click()
  await expect(page.getByText('Evidence channel')).toBeVisible()
  await expect(page.getByText('DIRECT_TEXT_MATCH')).toBeVisible()
  await expect(page.getByText('Passage score')).toBeVisible()
  await expect(page.getByText('1.400')).toBeVisible()
  expect(requestBody).toEqual({ query: 'Describe this harmless development source.', mode: 'exploratory', top_k: 5 })
})

test('an exact document title in a query targets that document automatically', async ({ page }) => {
  let requestBody
  const document = { document_id: 'five-year-programme', title: 'A five year programme for design in general education, 2nd draft', ml_policy_status: 'eligible_unrestricted' }
  await page.route('**/api/runtime/model-info', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ status: 'ready', display_name: 'Qwen fixture' }) }))
  await page.route('**/api/documents', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ count: 1, documents: [document] }) }))
  await page.route('**/api/analysis/interrogate', async (route) => {
    requestBody = route.request().postDataJSON()
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({
      query_id: 'query-fixture', status: 'completed', answer: 'A bounded answer.', model: {},
      provenance_validation: { valid: true }, retrieved_evidence: [], documentary_evidence: [], authority_evidence: [], inferences: [], contradictions: [], missingness: []
    }) })
  })

  await page.goto('/source-interrogation')
  const query = 'What does "A five year programme for design in general education, 2nd draft" explicitly establish about design education?'
  await page.getByRole('textbox', { name: 'Research query' }).fill(query)
  await page.getByRole('button', { name: 'Run interrogation' }).click()

  await expect.poll(() => requestBody).toEqual({ query, mode: 'exploratory', top_k: 5, target_document_ids: ['five-year-programme'] })
})

test('a document comparison retains document-specific evidence and insufficiency', async ({ page }) => {
  let requestBody
  const documents = [
    { document_id: 'document-a', title: 'Electrohome lectures', ml_policy_status: 'eligible_unrestricted' },
    { document_id: 'document-b', title: 'Rector report', ml_policy_status: 'eligible_page_restricted' }
  ]
  await page.route('**/api/runtime/model-info', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ status: 'ready', display_name: 'Qwen fixture' })
  }))
  await page.route('**/api/documents', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ count: documents.length, documents })
  }))
  await page.route('**/api/analysis/interrogate', async (route) => {
    requestBody = route.request().postDataJSON()
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'comparison-fixture', mode: 'comparison', status: 'completed', persisted: true,
        answer: 'The retained evidence supports a bounded reading of document A only.',
        model: { name: 'qwen-fixture', display_name: 'Qwen fixture', runtime: 'fixture' },
        corpus_version: 'corpus_f40d78dbce52', provenance_validation: { valid: true, source_count: 1, claim_count: 0 },
        retrieval: { strategy: 'explicit_document_selection_v1' }, retrieval_diagnostics: { selected_document_count: 2, retrieved_documentary_source_count: 1 },
        retrieved_evidence: [{ chunk_id: 'chunk-a', document_id: 'document-a', title: 'Electrohome lectures', text: 'Lecture evidence.', pid: 'PID-A', page_start: 4, rank: 1, score: 0.9, archive_resolution_status: 'resolved_current', provenance: { asset_pid: 'PID-A' } }],
        comparison: {
          document_a: { document_id: 'document-a', title: 'Electrohome lectures', pid: 'PID-A', evidence: [{ chunk_id: 'chunk-a', page_start: 4, text: 'Lecture evidence.' }], claims: [] },
          document_b: { document_id: 'document-b', title: 'Rector report', pid: null, evidence: [], claims: [], evidence_limit: 'No relevant passage was retrieved from this selected document under the current query and corpus configuration.' },
          convergences: [], differences_or_tensions: [], evidence_limits: []
        }
      })
    })
  })

  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('Compare the selected documents.')
  await page.getByRole('combobox', { name: 'Mode / model selector' }).selectOption('comparison')
  await page.getByRole('combobox', { name: 'Target document A' }).selectOption('document-a')
  await page.getByRole('combobox', { name: 'Target document B (comparison)' }).selectOption('document-b')
  await page.getByRole('button', { name: 'Compare documents' }).click()

  await expect(page.getByRole('heading', { name: 'Document comparison evidence' })).toBeVisible()
  await expect(page.getByText('Document A:')).toBeVisible()
  await expect(page.getByText('Document B:')).toBeVisible()
  await expect(page.getByText('No relevant passage was retrieved from this selected document under the current query and corpus configuration.')).toBeVisible()
  expect(requestBody).toEqual({ query: 'Compare the selected documents.', mode: 'comparison', top_k: 5, target_document_ids: ['document-a', 'document-b'] })
})