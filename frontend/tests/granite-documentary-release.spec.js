import { expect, test } from '@playwright/test'

test('the full unverified draft and each grouped citation remain inspectable', async ({ page }) => {
  await page.route('**/api/runtime/model-info', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ status: 'ready', display_name: 'IBM Granite 4.1 30B' })
  }))
  const ids = ['EV-123456789abc', 'EV-abcdef123456']
  await page.route('**/api/analysis/interrogate', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      status: 'completed', answer: null, verified_answer: null,
      original_draft: `The complete draft opening [${ids.join(', ')}].\n\nThe final unverified paragraph is preserved. Repeated source [${ids[0]}].\n\nRoles in design\u2014aid, analyst\u2014remain provisional. The source says \u201csource\u2014wording\u201d and "verbatim\u2014text".\n\nProposition P1 describes the recorded aim. The author qualifies P2 [P2, P3]. The source says "P1 remains P1".\n\n> Block quotation\u2014unchanged.`,
      answer_state: 'unverified_research_draft', draft_label: 'UNVERIFIED RESEARCH DRAFT',
      answer_origin: 'granite_documentary_research_draft',
      human_acceptance_status: 'UNASSESSED', verification_status: 'not_performed',
      model: { name: 'granite4.1:30b-q4_K_M' },
      retrieved_evidence: [], documentary_evidence: [], inferences: [],
      provenance_validation: { valid: false, claim_count: 1, claim_provenance: [{
        claim_number: 1, assertion: 'Draft claim requires assessment.',
        evidence_ids: ids, semantic_status: 'UNASSESSED'
      }] },
      evidence_sources: ids.map((id, index) => ({
        evidence_id: id, title: `Original source ${index + 1}`, page: index + 3,
        document_id: `doc-${index}`, asset_id: `asset-${index}`, chunk_id: `chunk-${index}`,
        archive_record_pid: 'record-1', attached_media_pid: 'media-1', asset_pid: `pid-${index}`,
        source_uri: `https://archive.example/source-${index}.pdf`,
        text: `Exact conditional passage ${index + 1}.\u2014Original punctuation.`,
        evidence_status: 'unknown', evidence_role: 'retrieved_match'
      }))
    })

  }))
  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('How is design described?')
  await page.getByRole('button', { name: 'Run interrogation' }).click()
  await expect(page.getByText('UNVERIFIED RESEARCH DRAFT', { exact: true })).toBeVisible()
  await expect(page.getByText('The final unverified paragraph is preserved.', { exact: false })).toBeVisible()
  const answer = page.locator('.tracer__answer-body')
  await expect(answer.locator('sup a')).toHaveText(['1', '2', '1'])
  await expect(answer).not.toContainText('EV-')
  await expect(answer).toContainText('Roles in design\u2013aid, analyst\u2013remain provisional.')
  await expect(answer).toContainText('\u201csource\u2014wording\u201d')
  await expect(answer).toContainText('"verbatim\u2014text"')
  await expect(answer.locator('blockquote')).toContainText('Block quotation\u2014unchanged.')
  await expect(answer).toContainText('Proposition P1 describes the recorded aim.')
  await expect(answer).toContainText('The author qualifies P2 [P2, P3]')
  await expect(answer).toContainText('"P1 remains P1"')
  for (const [index, id] of ids.entries()) {
    const marker = answer.getByRole('link', { name: `Jump to source ${index + 1}`, exact: true }).first()
    await expect(marker).toHaveAttribute('href', `#source-card-${index + 1}`)
    await marker.click()
    const card = page.locator(`#source-card-${index + 1}`)
    await expect(card).toBeFocused()
    await expect(card.locator(`[id="evidence-${id}"]`)).toHaveCount(1)
    await expect(card.getByRole('link', { name: 'Open original source' })).toHaveAttribute('href', `https://archive.example/source-${index}.pdf`)
  }
  await expect(answer.locator('sup a').last()).toHaveAttribute('href', '#source-card-1')
  await expect(page.locator('#documentary-note-1 a')).toHaveAttribute('href', '#source-card-1')
  await expect(page.getByText('Exact conditional passage 1.\u2014Original punctuation.')).toBeVisible()
  await expect(page.getByText('Exact conditional passage 2.\u2014Original punctuation.')).toBeVisible()
  await expect(page.getByText('Draft claim requires assessment.', { exact: true })).not.toBeVisible()
  await page.getByRole('button', { name: 'Claim support and evidential limits', exact: true }).click()
  await expect(page.getByText('Draft claim requires assessment.', { exact: true })).toBeVisible()
  await expect(page.getByText('UNASSESSED', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Validated synthesis with resolvable source citations.')).toHaveCount(0)
})

test('a hybrid draft preserves deterministic authority, scholarly prose and numbered documentary notes', async ({ page }) => {
  await page.route('**/api/runtime/model-info', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ status: 'ready', display_name: 'IBM Granite 4.1 30B' })
  }))
  await page.route('**/api/analysis/interrogate', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      status: 'completed', answer: null, verified_answer: null,
      original_draft: 'John Wood: employment role: Designer; start date: 1969; end date: 1977.\n\nThe two reports describe distinct operational requirements [EV-123456789abc].',
      answer_state: 'unverified_research_draft', draft_label: 'UNVERIFIED RESEARCH DRAFT',
      answer_origin: 'granite_hybrid_research_draft',
      human_acceptance_status: 'UNASSESSED', verification_status: 'not_performed',
      model: { name: 'granite4.1:30b-q4_K_M' },
      authority_evidence: [{
        authority_id: 'employment-wood', authority_type: 'agent_employment',
        fields: { name: 'John Wood', start_date: '1969', end_date: '1977' }
      }],
      retrieved_evidence: [], documentary_evidence: [], inferences: [],
      citation_bindings: [{ evidence_ids: ['EV-123456789abc'] }],
      provenance_validation: { valid: false, semantic_status: 'UNASSESSED', claim_provenance: [] },
      evidence_sources: [{
        evidence_id: 'EV-123456789abc', title: 'Original project report', page: 8,
        document_id: 'doc-175', asset_pid: 'asset-175', chunk_id: 'original-chunk',
        source_uri: 'https://archive.example/report.pdf', text: 'Original documentary passage.',
        evidence_role: 'retrieved_match'
      }]
    })
  }))
  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('What do the authority record and two reports establish?')
  await page.getByRole('button', { name: 'Run interrogation' }).click()
  await expect(page.getByText('UNVERIFIED RESEARCH DRAFT', { exact: true })).toBeVisible()
  const answer = page.locator('.tracer__answer-body')
  await expect(answer).toContainText('John Wood: employment role: Designer; start date: 1969; end date: 1977.')
  await expect(answer).toContainText('The two reports describe distinct operational requirements')
  await expect(answer.locator('sup a')).toHaveText(['1'])
  await expect(page.getByRole('link', { name: 'Open original source' })).toHaveAttribute('href', 'https://archive.example/report.pdf')
  await expect(page.getByText('Validated synthesis with resolvable source citations.')).toHaveCount(0)
})
