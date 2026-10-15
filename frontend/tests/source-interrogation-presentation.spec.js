import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'

const stages = ['Question', 'Retrieval', 'Evidence', 'Validated claims', 'Scholarly argument', 'Citations', 'Bounded Qualification']
const response = {
  query_id: 'presentation-fixture', status: 'completed', mode: 'exploratory',
  answer: null, original_draft: 'A **bounded formulation ** [EV‑123456789abc]. A second claim [EV-abcdef123456]. Repeated [EV-123456789abc]. Unknown [EV-000000000000].\n\nConnections — not implementation — are inferred. "Original—words" remain unchanged.',
  answer_state: 'unverified_research_draft', answer_origin: 'granite_documentary_research_draft',
  model: { name: 'granite4.1:30b-q4_K_M' },
  stage_execution: { scholarly_model_calls: 2 },
  provenance_validation: { valid: false, semantic_status: 'UNASSESSED' },
  retrieved_evidence: [
    { document_id: 'doc1', chunk_id: 'c1', title: 'Original report', text: 'Exact first—passage.', page_start: 4, asset_pid: 'pid1' },
  ],
  evidence_sources: [
    { evidence_id: 'EV-123456789abc', document_id: 'doc1', chunk_id: 'c1', title: 'Original report', text: 'Exact first—passage.', page: 4, asset_pid: 'pid1', source_uri: 'https://archive.example/report.pdf' },
    { evidence_id: 'EV-abcdef123456', document_id: 'doc1', chunk_id: 'c2', title: 'Original report', text: 'Exact second—passage.', page: 5, asset_pid: 'pid1' },
  ],
  documentary_evidence: [], inferences: [], missingness: [],
  retrieval_diagnostics: { result_count: 1, notes: ['A meaningful diagnostic warning.'] },
}

const submit = async (page, fixture = response) => {
  await page.route('**/api/runtime/model-info', (route) => route.fulfill({
    json: { status: 'ready', display_name: 'IBM Granite 4.1 30B' },
  }))
  await page.route('**/api/documents', (route) => route.fulfill({ json: { count: 0, documents: [] } }))
  await page.route('**/api/analysis/interrogate', (route) => route.fulfill({ json: fixture }))
  await page.goto('/source-interrogation')
  await page.getByRole('textbox', { name: 'Research query' }).fill('Presentation fixture only.')
  await page.getByRole('button', { name: 'Run interrogation' }).click()
  await expect(page.locator('.tracer__answer-body')).toContainText('bounded')
}

test('canonical citations preserve evidence, punctuation, warning visibility and metadata access', async ({ page }) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await submit(page)
  const answer = page.locator('.tracer__answer-body')
  await expect(answer.locator('sup a')).toHaveText(['1', '2', '1', '?'])
  await expect(answer).not.toContainText('EV-')
  await expect(answer).toContainText('Connections–not implementation–are inferred.')
  await expect(answer).toContainText('"Original—words"')
  const whitespace = await answer.locator('sup').evaluateAll((nodes) => nodes.some((node) => (
    /\s$/.test(node.previousSibling?.textContent || '')
  )))
  expect(whitespace).toBe(false)
  await expect(page.locator('.evidence-source-card')).toHaveCount(2)
  await expect(page.getByText('Exact first—passage.', { exact: true })).toHaveCount(1)
  await expect(page.getByText('Exact second—passage.', { exact: true })).toHaveCount(1)
  await expect(page.locator('#citation-warnings')).toContainText('EV-000000000000')
  await answer.getByRole('link', { name: 'Jump to source 2', exact: true }).click()
  await expect(page.locator('#source-card-2')).toBeFocused()
  await expect(page.locator('#source-card-2')).toContainText('Page 5')
  await page.locator('#source-card-1').getByRole('button', { name: 'View provenance' }).click()
  await expect(page.locator('#source-card-1')).toContainText('Chunk ID: c1')
  await expect(page.locator('#source-card-1').getByRole('link', { name: 'Open original source' })).toHaveAttribute('href', 'https://archive.example/report.pdf')
  await expect(page.getByText('A meaningful diagnostic warning.', { exact: true }).first()).not.toBeVisible()
  await page.getByRole('button', { name: 'Retrieval diagnostics', exact: true }).click()
  await expect(page.getByText('A meaningful diagnostic warning.', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Research execution', exact: true }).click()
  await expect(page.getByText('scholarly model calls', { exact: true })).toBeVisible()
  expect(errors).toEqual([])
})

test('seven-stage trail is legible, keyboard-operable, themed and exportable at mobile width', async ({ page }) => {
  await submit(page)
  const graph = page.locator('.evidence-graph')
  expect(await graph.locator('[data-stage]').evaluateAll((nodes) => nodes.map((node) => node.dataset.stage))).toEqual(stages)
  await expect(graph.locator('.evidence-graph__stage-status')).toHaveCount(7)
  await expect(graph.locator('[data-stage="Validated claims"]')).toContainText('Unassessed')
  const boxes = await graph.locator('.evidence-graph__stage .evidence-graph__label').evaluateAll((nodes) => nodes.map((node) => {
    const box = node.getBoundingClientRect()
    return { left: box.left, right: box.right, top: box.top, bottom: box.bottom }
  }))
  expect(boxes.every((box, index) => !index || box.left > boxes[index - 1].right)).toBe(true)
  const source = graph.locator('.evidence-graph__source').first()
  await source.focus()
  await page.keyboard.press('Enter')
  await expect(graph.getByRole('heading', { name: 'Selected passage' })).toBeVisible()
  await expect(graph.getByRole('link', { name: 'Read selected source passage' })).toHaveAttribute('href', '#source-card-1')
  const fill = await graph.locator('.evidence-graph__label').first().evaluate((node) => getComputedStyle(node).fill)
  await page.getByRole('button', { name: /Switch to .* theme/ }).click()
  await expect.poll(() => graph.locator('.evidence-graph__label').first().evaluate((node) => getComputedStyle(node).fill)).not.toBe(fill)
  const svgDownload = page.waitForEvent('download')
  await graph.getByRole('button', { name: 'Download SVG' }).click()
  const svg = await svgDownload
  expect(await svg.failure()).toBeNull()
  const svgText = await readFile(await svg.path(), 'utf8')
  expect(svgText).toContain('Bounded Qualification')
  expect(svgText).toContain('stroke-dasharray="4 4"')
  expect(svgText).toMatch(/<rect[^>]+fill="rgb\(/)
  const pngDownload = page.waitForEvent('download')
  await graph.getByRole('button', { name: 'Download PNG' }).click()
  const png = await pngDownload
  expect(await png.failure()).toBeNull()
  const pngBytes = await readFile(await png.path())
  expect([...pngBytes.subarray(0, 8)]).toEqual([137, 80, 78, 71, 13, 10, 26, 10])
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  expect(await graph.locator('.evidence-graph__viewport').evaluate((node) => node.scrollWidth > node.clientWidth)).toBe(true)
  expect(await graph.getByRole('img', { name: 'Evidence retrieval trail' }).evaluate((node) => node.getBoundingClientRect().width / node.viewBox.baseVal.width)).toBeGreaterThanOrEqual(1)
})

test('Markdown memo exports citation links and every original source passage without changing quotations', async ({ page }) => {
  await submit(page)
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download retrieval memo' }).click()
  const result = await download
  expect(await result.failure()).toBeNull()
  const markdown = await readFile(await result.path(), 'utf8')
  expect(markdown).toContain('<sup>[1](#source-card-1)</sup>')
  expect(markdown).toContain('Connections–not implementation–are inferred.')
  expect(markdown).toContain('"Original—words"')
  expect(markdown).toContain('Exact first—passage.')
  expect(markdown).toContain('Exact second—passage.')
  expect(markdown).toContain('Unresolved citation: EV-000000000000')
})

test('scoped-missingness answers share documentary citation rendering without implying acceptance', async ({ page }) => {
  await submit(page, {
    ...response, answer: 'A bounded scope statement [EV-123456789abc].', original_draft: null,
    answer_state: 'evidential_limit', answer_origin: 'targeted_document_evidence_limit',
    missingness: [{ scope: 'retrieval_run', category: 'not_established', explanation: 'This does not establish historical absence.' }],
  })

  await expect(page.locator('.tracer__answer-body sup a')).toHaveText(['1'])
  await expect(page.locator('.tracer__answer-state')).toContainText('Evidential limit')
  await expect(page.locator('[data-stage="Scholarly argument"]')).toContainText('Unavailable')
  await expect(page.locator('[data-stage="Bounded Qualification"]')).toContainText('Limits recorded')
})

test('a saved Granite draft rehydrates original prose and citation mappings without another model request', async ({ page }) => {
  let submissions = 0
  await page.route('**/api/runtime/model-info', (route) => route.fulfill({ json: { status: 'ready', display_name: 'IBM Granite 4.1 30B' } }))
  await page.route('**/api/documents', (route) => route.fulfill({ json: { count: 0, documents: [] } }))
  await page.route('**/api/analysis/interrogate', (route) => { submissions += 1; return route.abort() })
  await page.route('**/api/experiments/experiment-presentation', (route) => route.fulfill({ json: {
    run_id: 'experiment-presentation', status: 'completed', interpretative_status: 'unassessed',
    prompt: { question: 'A saved question.' }, answer_state: 'unverified_research_draft',
    model: response.model, retrieved_evidence: response.retrieved_evidence, structured_response: response,
  } }))
  await page.goto('/source-interrogation?runId=experiment-presentation')
  await expect(page.locator('.tracer__answer-body')).toContainText('A second claim')
  await expect(page.locator('.tracer__answer-body sup a')).toHaveText(['1', '2', '1', '?'])
  await expect(page.getByText('Exact second—passage.', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.locator('.tracer__answer-body sup a')).toHaveText(['1', '2', '1', '?'])
  expect(submissions).toBe(0)
})
