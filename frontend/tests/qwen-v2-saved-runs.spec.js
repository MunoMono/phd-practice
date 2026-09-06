import { test, expect } from '@playwright/test'

const source = (index) => ({
  rank: index,
  document_id: `document-${index}`,
  pid: `PID-${index}`,
  chunk_id: `chunk-${index}`,
  page_start: index,
  archive_resolution_status: 'resolved_current',
  excerpt: `Documentary passage ${index}.`,
  snapshot: { title: `Document ${index}` }
})

const savedRun = ({ runId, question, answer, inference, limit, failure = null }) => ({
  run_id: runId,
  created_at: '2026-09-03T12:00:00Z',
  research_case: 'known_relationship',
  corpus_version: 'corpus_f40d78dbce52',
  retrieval_method: 'exploratory_archive_retrieval_v3',
  status: failure ? 'failed' : 'completed',
  interpretative_status: failure ? 'unsupported' : 'unassessed',
  model: { name: 'qwen3:8b-q4_K_M' },
  retrieved_evidence: [1, 2, 3, 4, 5].map(source),
  retrieval_diagnostics: { result_count: 5, candidate_count: 11, diagnostic_state: 'RETRIEVED' },
  provenance_validation: failure ? { valid: false } : { valid: true },
  raw_model_response: failure ? '{"sources": []}' : '{"final_synthesis": {}}',
  error_code: failure ? 'evidence_pipeline_failure' : null,
  error_message: failure ? 'EvidencePipelineStageError: source_analysis response did not match its structured schema.' : null,
  structured_response: failure
    ? { answer: null, evidence: [], inferences: [], contradictions: [], missingness: [], follow_up_queries: [], pipeline_failure: { stage: 'source_analysis', raw_output_preserved: true } }
    : {
        answer,
        evidence: [{ claim: `Documentary support for ${question}.`, origin: 'model' }],
        inferences: inference ? [{ inference, confidence: null, origin: 'model' }] : [],
        contradictions: [],
        missingness: [{ scope: 'selected evidence', category: 'not_established', explanation: limit, origin: 'system_pipeline' }],
        follow_up_queries: []
      }
})

const runs = {
  'experiment-qwen-q01': savedRun({ runId: 'experiment-qwen-q01', question: 'Q01', answer: 'Q01 genuine answer about Job 171.', inference: 'Q01 cross-source inference.', limit: "The selected evidence does not directly establish the named subject's activity." }),
  'experiment-qwen-q08': savedRun({ runId: 'experiment-qwen-q08', question: 'Q08', answer: 'Q08 genuine answer about systematic design.', inference: 'Q08 cross-source inference.', limit: "The selected evidence does not establish a complete reconstruction of the subject's role." }),
  'experiment-qwen-q12': savedRun({ runId: 'experiment-qwen-q12', question: 'Q12', answer: 'Q12 genuine answer about Henrietta Ryott.', inference: 'Q12 cross-source inference.', limit: "The selected evidence does not directly establish the named subject's activity." }),
  'experiment-qwen-q05': savedRun({ runId: 'experiment-qwen-q05', question: 'Q05', failure: true })
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/experiments/experiment-qwen-*', async (route) => {
    const run = runs[route.request().url().split('/').pop()]
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(run) })
  })
})

test('Qwen V2 saved runs render distinct canonical answers with diagnostics and provenance', async ({ page }) => {
  for (const [runId, expected] of Object.entries({
    'experiment-qwen-q01': 'Q01 genuine answer about Job 171.',
    'experiment-qwen-q08': 'Q08 genuine answer about systematic design.',
    'experiment-qwen-q12': 'Q12 genuine answer about Henrietta Ryott.'
  })) {
    await page.goto(`/source-interrogation?runId=${runId}`)
    await expect(page.locator('.tracer__answer-body')).toHaveText(expected)
    await expect(page.getByRole('region', { name: 'Qwen interpretation' })).toContainText(`${runId.slice(-3).toUpperCase()} cross-source inference.`)
    await expect(page.getByText('Retrieved passages: 5.')).toBeVisible()
    await expect(page.getByRole('region', { name: 'Model claim provenance' })).toContainText('PASS Generated substantive claims must cite valid supplied documentary sources.')
    await expect(page.getByText('Pipeline-derived:', { exact: true })).toBeVisible()
    await expect(page.getByText('Model-generated:', { exact: true })).toHaveCount(0)
    await expect(page.getByText(/undefined/)).toHaveCount(0)
  }
})

test('Qwen V2 CI1 Stage A failure remains explicit without a synthetic answer', async ({ page }) => {
  await page.goto('/source-interrogation?runId=experiment-qwen-q05')
  await expect(page.locator('.tracer__answer-body')).toHaveText('No answer returned.')
  await expect(page.getByRole('region', { name: 'Qwen interpretation' })).toContainText('Qwen interpretation unavailable')
  await expect(page.getByRole('region', { name: 'Qwen interpretation' })).toContainText('Formal run stopped at Stage A schema validation.')
  await expect(page.getByRole('region', { name: 'Qwen interpretation' })).toContainText('Raw Stage A model output is preserved with the immutable run.')
  await expect(page.getByText('Raw Stage A model output (immutable audit record)')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Documentary evidence' })).toContainText('No documentary claim is asserted beyond the retrieved source stack.')
})