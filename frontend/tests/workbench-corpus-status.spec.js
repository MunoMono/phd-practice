import { test, expect } from '@playwright/test'

const analyticalSurface = {
  corpus_version: 'corpus_f40d78dbce52',
  composition: {
    current_assets: 109,
    controlled_ingestible_sources: 95,
    source_format_anomalies: 2,
    ml_excluded_assets: 12,
    current_chunks: 12884
  },
  density: [{ document_id: 'source-1', title: 'A fully readable evidence-density source title', chunk_count: 12 }],
  temporal: { bins: [{ year: 1975, document_count: 3 }], undated_documents: 0 },
  runs: { completed_runs: 1, bounded_failures: 0, assessed_runs: 1 }
}

const mockAnalyticalSurface = async (page, payload) => {
  await page.route('**/api/viz/dashboard-analytical-surface', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(payload) })
  })
}

test('workbench distinguishes frozen retrieval, archive inventory, and local processing populations', async ({ page }) => {
  await page.goto('/', { waitUntil: 'networkidle' })

  await expect(page.getByText('Frozen retrieval corpus')).toBeVisible()
  await expect(page.getByText('corpus_f40d78dbce52')).toBeVisible()
  await expect(page.getByText('Searchable FTS chunks')).toBeVisible()
  await expect(page.getByText('12,884')).toBeVisible()
  await expect(page.getByText('95 successfully ingested frozen-corpus sources')).toBeVisible()

  await expect(page.getByText(/Archive-resolved current document records \(of \d+ local records\)/)).toBeVisible()
  await expect(page.getByText(/Legacy document records without current archive resolution \(of \d+ local records\)/)).toBeVisible()

  await expect(page.getByText('Documents with stored embeddings')).toBeVisible()
  await expect(page.getByText('0 of 138 local records')).toBeVisible()
  await expect(page.getByText('Inactive for retrieval; PostgreSQL FTS remains active.')).toBeVisible()

  await expect(page.getByText('Authoritative archive assets')).toBeVisible()
  await expect(page.getByText('109')).toBeVisible()
  await expect(page.getByText('ML-eligible archive assets')).toBeVisible()
  await expect(page.getByText('97 of 109')).toBeVisible()
  await expect(page.getByText('ML-excluded archive assets')).toBeVisible()
  await expect(page.getByText('12 of 109')).toBeVisible()

  await expect(page.getByText('ML-authorised archive PDF media')).toBeVisible()
  await expect(page.getByText('114')).toBeVisible()
  await expect(page.getByText('PID-linked archive metadata')).toBeVisible()

  await expect(page.getByText('Archive-linked PDF assets')).toHaveCount(0)
  await expect(page.getByText('Controlled-ingested PDFs')).toHaveCount(0)
  await expect(page.getByText('4 successfully ingested frozen-corpus sources')).toHaveCount(0)

  await expect(page.getByRole('heading', { level: 3, name: 'Corpus composition' })).toBeVisible()
  await expect(page.getByRole('heading', { level: 3, name: 'Evidence density' })).toBeVisible()
  await expect(page.getByRole('heading', { level: 3, name: 'Corpus across time' })).toBeVisible()
  await expect(page.getByRole('heading', { level: 3, name: 'Research evidence state' })).toBeVisible()

  const firstDensityLabel = page.locator('.dashboard__density-label').first()
  await expect(firstDensityLabel).toHaveCSS('white-space', 'normal')
  await expect(firstDensityLabel).toHaveCSS('text-overflow', 'clip')

  await page.getByTestId('composition-segment-controlled').hover()
  await expect(page.locator('.dashboard-composition-tooltip')).toContainText('Controlled-ingestible sources')
  await expect(page.locator('.dashboard-composition-tooltip')).toContainText('Assets: 95')

  await page.getByTestId('evidence-density-row').first().hover()
  await expect(page.locator('.dashboard-density-tooltip')).toContainText(await firstDensityLabel.innerText())
  await expect(page.locator('.dashboard-density-tooltip')).toContainText('Current frozen-corpus chunks:')

  await page.getByTestId('timeline-bar-1975').hover()
  await expect(page.locator('.dashboard-timeline-tooltip')).toContainText('Current sources: 3')
})

test('workbench reports an unavailable analytical surface', async ({ page }) => {
  await page.route('**/api/viz/dashboard-analytical-surface', async (route) => {
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Unavailable' }) })
  })

  await page.goto('/', { waitUntil: 'networkidle' })
  await expect(page.getByText('Analytical surface unavailable. Current corpus-status metrics remain available, but analytical summaries could not be loaded.')).toBeVisible()
})

test('workbench reports empty analytical panel data explicitly', async ({ page }) => {
  await mockAnalyticalSurface(page, {
    ...analyticalSurface,
    composition: { ...analyticalSurface.composition, current_assets: 0 },
    density: [],
    temporal: { bins: [], undated_documents: 0 }
  })

  await page.goto('/', { waitUntil: 'networkidle' })
  await expect(page.getByText('No corpus-composition data are available for the current analytical surface.')).toBeVisible()
  await expect(page.getByText('No evidence-density data are available for the current analytical surface.')).toBeVisible()
  await expect(page.getByText('No temporal distribution data are available for the current analytical surface.')).toBeVisible()
})