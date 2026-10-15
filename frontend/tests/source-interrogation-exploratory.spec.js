import { expect, test } from '@playwright/test'

test('an exploratory interrogation preserves answer, source passages and collapsed provenance without a formal run', async ({ page }) => {
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
        retrieval: {}, retrieval_diagnostics: {
          result_count: 1,
          notes: [],
          retrieval_coverage: {
            coverage_status: 'partially_satisfied',
            required_surfaces_found: ['documentary'],
            required_surfaces_missing: ['oral_history'],
            distinct_source_count: 1,
            temporal_buckets_found: ['1970s'],
            target_entity_evidence_found: true,
            target_project_evidence_found: null
          }
        },
        retrieved_evidence: [{
          chunk_id: 'chunk-1', document_id: 'doc-1', title: 'Project report', text: 'A documentary passage.',
          pid: '546216480663', archive_record_pid: '637362423718', page_start: 4, rank: 1, score: 0.9,
          archive_resolution_status: 'resolved_current', provenance: { archive_record_pid: '637362423718', asset_pid: '123' }
          , asset_pid: '123', combined_score: 1.2, text_score: 0.9, metadata_score: 0.3, source_nomination_score: 1.2, passage_score: 1.4, source_nomination_channels: ['METADATA_MATCH', 'TEXT_MATCH'], passage_evidence_channel: 'DIRECT_TEXT_MATCH', retrieval_channels: ['TEXT_MATCH', 'METADATA_MATCH'], metadata_matches: [{ field: 'keywords', value: 'Example Person' }], evidence_classification: { subject_named: true, relationship_to_question: 'DIRECT_SUPPORT' }
        }]
        , evidence_ledger: [
          { evidence_id: 'ev:fixture', evidence_type: 'DIRECT_DOCUMENTARY', source_title: 'Project report', chunk_id_or_record_id: 'chunk-1', contemporary_or_retrospective: 'contemporary' },
          { evidence_id: 'metadata:fixture', evidence_type: 'ARCHIVAL_METADATA', source_title: 'Project report', relation_type_if_any: 'PERSON_ASSOCIATED_WITH_SOURCE', relation_derivation_if_any: 'keyword_metadata', contemporary_or_retrospective: 'unknown' }
        ]
        , documentary_evidence: [{ claim: 'A documentary passage.', pid: '546216480663', page: 4 }],
        testimony_evidence: [{ claim: 'A later interview recollection.', pid: '546216480663', page: 4 }],
        researcher_facing: {
          authority_evidence: [],
          documentary_evidence: [{ claim: 'A documentary passage.', pid: '546216480663', page: 4 }],
          testimony_evidence: [{ claim: 'A later interview recollection.', pid: '546216480663', page: 4 }],
          evidential_limits: [{ category: 'not_established', explanation: 'The source does not establish supervision.' }]
        },
        inferences: [{ claim: 'This may be related across sources.' }],
        missingness: [{ category: 'not_established', explanation: 'The source does not establish supervision.' }]
      })
    })
  })
  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('Describe this harmless development source.')
  await page.getByRole('button', { name: 'Run interrogation' }).click()
  await expect(page.getByText('The supplied documentary passage identifies a project.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Source 1 – Project report', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'View provenance', exact: true }).click()
  await expect(page.getByText('Direct support', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Provenance details', exact: true }).click()
  await expect(page.getByText('DIRECT_DOCUMENTARY').first()).toBeVisible()
  await expect(page.getByText('Typed evidence ledger', { exact: true })).toBeVisible()
  await expect(page.getByText('PERSON_ASSOCIATED_WITH_SOURCE', { exact: true })).toBeVisible()
  await expect(page.getByText('keyword_metadata', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Claim support and evidential limits', exact: true }).click()
  await expect(page.getByText('A later interview recollection.', { exact: true })).toBeVisible()
  await expect(page.getByText('This may be related across sources.', { exact: true })).toBeVisible()
  await expect(page.getByText('The source does not establish supervision.', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Retrieval diagnostics', exact: true }).click()
  await expect(page.getByText('Retrieval coverage: partially satisfied.')).toBeVisible()
  await expect(page.getByText('Required evidence missing: oral_history.')).toBeVisible()
  await expect(page.getByText('Evidence periods: 1970s.')).toBeVisible()
  await expect(page.getByText('Target entity evidence: found.')).toBeVisible()
  await page.getByText('Why this source?').click()
  const nomination = page.locator('details').filter({ has: page.getByText('Why this source?', { exact: true }) })
  await expect(nomination.getByText('Nomination channel', { exact: true })).toBeVisible()
  await expect(nomination.getByText('METADATA_MATCH + TEXT_MATCH')).toBeVisible()
  await expect(nomination.getByText('Nomination score', { exact: true })).toBeVisible()
  await expect(nomination.getByText('1.200')).toBeVisible()
  await expect(nomination.getByText('Metadata: keywords')).toBeVisible()
  await expect(nomination.getByText('Example Person')).toBeVisible()
  await expect(nomination.getByText('637362423718 → 546216480663 → 123 → page 4 → chunk-1')).toBeVisible()
  await page.getByText('Why this passage?').click()
  const passage = page.locator('details').filter({ has: page.getByText('Why this passage?', { exact: true }) })
  await expect(passage.getByText('Evidence channel', { exact: true })).toBeVisible()
  await expect(passage.getByText('DIRECT_TEXT_MATCH')).toBeVisible()
  await expect(passage.getByText('Passage score', { exact: true })).toBeVisible()
  await expect(passage.getByText('1.400')).toBeVisible()
  expect(requestBody).toEqual({ query: 'Describe this harmless development source.', mode: 'exploratory', top_k: 8 })
})

test('an exact document title is submitted for backend title resolution', async ({ page }) => {
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

  await expect.poll(() => requestBody).toEqual({ query, mode: 'exploratory', top_k: 8 })
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
  await page.getByRole('combobox', { name: 'Document A' }).selectOption('document-a')
  await page.getByRole('combobox', { name: 'Document B' }).selectOption('document-b')
  await page.getByRole('button', { name: 'Compare documents' }).click()

  await expect(page.getByRole('heading', { name: 'Source 1 – Electrohome lectures', exact: true })).toBeVisible()
  await expect(page.getByText('Lecture evidence.', { exact: true })).toHaveCount(1)
  await page.getByRole('button', { name: 'Retrieval diagnostics', exact: true }).click()
  await expect(page.locator('.tracer__supporting-details').getByText('document-a', { exact: true }).first()).toBeVisible()
  await expect(page.locator('.tracer__supporting-details').getByText('document-b', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('No relevant passage was retrieved from this selected document under the current query and corpus configuration.')).toBeVisible()
  expect(requestBody).toEqual({ query: 'Compare the selected documents.', mode: 'comparison', top_k: 8, target_document_ids: ['document-a', 'document-b'] })
})