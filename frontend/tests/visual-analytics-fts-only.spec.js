import { expect, test } from '@playwright/test'

test('FTS-only corpus reports an unavailable semantic atlas without hiding retrieval coverage', async ({ page }) => {
  await page.route('**/api/viz/umap**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      points: [],
      metadata: {
        projection_method: 'none',
        evidence_surface_scope: {
          documents_with_embeddings: 0,
          embedded_chunks: 0,
          active_corpus_version: 'corpus_turin_successor_d6c6858b23d0',
          active_fts_chunks: 15114,
          active_fts_documents: 123,
        },
      },
      message: 'No embedded chunks/documents available for UMAP projection.',
    }),
  }))

  await page.goto('/visual-analytics')

  await expect(page.getByText('Semantic atlas unavailable', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'FTS retrieval: 15,114 FTS chunks | 123 documents' })).toBeVisible()
  await expect(page.getByText('Semantic atlas unavailable: this corpus has no embedding vectors. Full-text retrieval remains active across 15,114 FTS chunks | 123 documents.')).toBeVisible()
})

test('projected local density is a display-only atlas encoding', async ({ page }) => {
  let projectionRequests = 0
  await page.route('**/api/viz/umap**', (route) => {
    projectionRequests += 1
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ points: [
        { id: 'chunk-1', chunk_id: 'chunk-1', x: 0, y: 0, documentary_form: { file_type: 'pdf', document_text_length: 1200, document_chunk_count: 4 } },
        { id: 'chunk-2', chunk_id: 'chunk-2', x: 0.1, y: 0.1, documentary_form: { file_type: 'pdf', document_text_length: 1200, document_chunk_count: 4 } },
        { id: 'chunk-3', chunk_id: 'chunk-3', x: 4, y: 4, documentary_form: { file_type: 'tiff', document_text_length: 32000, document_chunk_count: 70 } },
      ], metadata: { projection_id: 'projection-fixed', embedding_set_id: 'embedding-fixed', evidence_surface_scope: { embedded_chunks: 3 } } }),
    })
  })

  await page.goto('/visual-analytics')
  await expect(page.getByRole('button', { name: 'projection-fixed | embedding-fixed' })).toBeVisible()
  const initialProjectionRequests = projectionRequests
  await page.getByLabel('Colour by').selectOption('local_density')

  await expect(page.getByText('Colour encodes Projected local visual density. It is derived from distances between displayed stored coordinates; it does not indicate historical concentration, significance, or archive completeness.')).toBeVisible()
  await expect(page.getByText('Lower local visual density')).toBeVisible()
  await expect(page.getByText('Higher local visual density')).toBeVisible()
  await page.getByLabel('Colour by').selectOption('documentary_file_type')
  await expect(page.getByText('Colour encodes Documentary file type. These are returned documentary representation fields. Not exposed or not evaluated states are not evidence of access, rights, completeness, or archival absence.')).toBeVisible()
  await expect(page.getByText('pdf', { exact: true })).toBeVisible()
  await expect(page.getByText('tiff', { exact: true })).toBeVisible()
  await page.getByLabel('Colour by').selectOption('documentary_text_length')
  await expect(page.getByText('1-5,000 characters')).toBeVisible()
  await expect(page.getByText('25,001+ characters')).toBeVisible()
  await page.getByLabel('Colour by').selectOption('documentary_chunk_count')
  await expect(page.getByText('1-10 chunks')).toBeVisible()
  await expect(page.getByText('51+ chunks')).toBeVisible()
  expect(projectionRequests).toBe(initialProjectionRequests)
})

test('neighbourhood display k is a bounded slider exclusive to Semantic Neighbourhoods', async ({ page }) => {
  await page.route('**/api/viz/umap**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ points: [], metadata: { evidence_surface_scope: {} }, message: 'No projection available.' }),
  }))

  await page.goto('/visual-analytics')
  await expect(page.getByRole('slider', { name: 'Neighbourhood size (k)' })).not.toBeVisible()

  await page.goto('/visual-analytics?view=neighbourhoods')
  const slider = page.getByRole('slider', { name: 'Neighbourhood size (k)' })
  await expect(slider).toBeVisible()
  await expect(slider).toHaveAttribute('aria-valuenow', '10')
  await expect(page.getByLabel('Neighbourhood size value')).toHaveValue('10')
  await expect(page.getByText('It does not change the stored UMAP projection or its n_neighbors parameter.')).toBeVisible()
})

test('changing neighbourhood k refreshes original-space results without reloading the fixed projection', async ({ page }) => {
  const neighbourhoodRequests = []
  let projectionRequests = 0
  await page.addInitScript(() => {
    sessionStorage.setItem('ddr.visual-analytics.workspace', JSON.stringify({
      orbitVersion: 5,
      view: 'neighbourhoods',
      anchorId: 'chunk-1',
      selectedIds: ['chunk-1'],
    }))
  })
  await page.route('**/api/viz/umap**', (route) => {
    projectionRequests += 1
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        points: [{ id: 'chunk-1', chunk_id: 'chunk-1', document_id: 'document-1', pid: 'pid-1', title: 'Focal trace', x: 0, y: 0 }],
        metadata: { projection_id: 'projection-fixed', embedding_set_id: 'embedding-fixed', evidence_surface_scope: { embedded_chunks: 1, documents_with_embeddings: 1 } },
      }),
    })
  })
  await page.route('**/api/viz/semantic-neighbourhood', async (route) => {
    const request = route.request().postDataJSON()
    neighbourhoodRequests.push(request)
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ focal_chunk_id: 'chunk-1', focal: { id: 'chunk-1' }, neighbours: [{ id: 'chunk-2', title: 'Neighbour', rank: 1, similarity: 0.9 }], metadata: { projection_id: 'projection-fixed', requested_k: request.size, returned_k: 1 } }),
    })
  })

  await page.goto('/visual-analytics?view=neighbourhoods')
  await page.getByRole('button', { name: 'Explore neighbourhood' }).click()
  await expect.poll(() => neighbourhoodRequests.length).toBe(1)
  const settledProjectionRequests = projectionRequests
  const slider = page.getByRole('slider', { name: 'Neighbourhood size (k)' })
  await slider.focus()
  await slider.press('ArrowRight')
  await expect.poll(() => neighbourhoodRequests.length).toBe(2)

  expect(neighbourhoodRequests.map((request) => request.size)).toEqual([10, 15])
  expect(projectionRequests).toBe(settledProjectionRequests)
  await expect(page.getByRole('button', { name: 'projection-fixed | embedding-fixed' })).toBeVisible()
})

test('comparative view exposes named cohort controls and does not imply fidelity availability', async ({ page }) => {
  await page.route('**/api/viz/umap**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ points: [], metadata: { evidence_surface_scope: {} } }),
  }))

  await page.goto('/visual-analytics?view=comparative')

  await expect(page.getByLabel('Cohort A name')).toHaveValue('Cohort A')
  await expect(page.getByRole('button', { name: 'Save cohort A from selection' })).toBeDisabled()
  await expect(page.getByLabel('Projection fidelity')).toBeDisabled()
})

test('comparative selection saves a durable researcher-defined cohort', async ({ page }) => {
  const cohortRequests = []
  await page.addInitScript(() => {
    sessionStorage.setItem('ddr.visual-analytics.workspace', JSON.stringify({ orbitVersion: 7, selectedIds: ['chunk-1'] }))
  })
  await page.route('**/api/viz/umap**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ points: [{ id: 'chunk-1', chunk_id: 'chunk-1', document_id: 'document-1', title: 'Selected source', x: 0, y: 0 }], metadata: { projection_id: 'projection-fixed', embedding_set_id: 'embedding-fixed', evidence_surface_scope: { embedded_chunks: 1 } } }),
  }))
  await page.route('**/api/viz/cohorts', async (route) => {
    cohortRequests.push(route.request().postDataJSON())
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ cohort_id: 'visual-cohort-1', name: 'Researchers A', point_ids: ['chunk-1'], projection_id: 'projection-fixed', embedding_set_id: 'embedding-fixed', version: 1, created_at: '2026-10-02T00:00:00' }) })
  })

  await page.goto('/visual-analytics?view=comparative')
  await page.getByLabel('Cohort A name').fill('Researchers A')
  await page.getByRole('button', { name: 'Save cohort A from selection' }).click()

  await expect.poll(() => cohortRequests.length).toBe(1)
  expect(cohortRequests[0]).toMatchObject({ name: 'Researchers A', point_ids: ['chunk-1'], projection_id: 'projection-fixed', embedding_set_id: 'embedding-fixed', definition: { source: 'researcher_selection', operator: 'include', selected_point_ids: ['chunk-1'] } })
  await expect(page.getByText('Researchers A (1)')).toBeVisible()
  await page.getByRole('button', { name: 'Save view' }).click()
  await expect(page.getByText('Export cohort comparison (CSV)')).toBeEnabled()
})

test('comparative date and source rules persist declared AND/OR cohort semantics', async ({ page }) => {
  const cohortRequests = []
  await page.route('**/api/viz/umap**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ points: [
      { id: 'chunk-early', chunk_id: 'chunk-early', title: 'Early source', x: 0, y: 0, year: 1965, source_type: 'pdf' },
      { id: 'chunk-late', chunk_id: 'chunk-late', title: 'Later source', x: 1, y: 1, year: 1972, source_type: 'tiff' },
    ], metadata: { projection_id: 'projection-fixed', embedding_set_id: 'embedding-fixed', evidence_surface_scope: { embedded_chunks: 2 } } }),
  }))
  await page.route('**/api/viz/cohorts', async (route) => {
    cohortRequests.push(route.request().postDataJSON())
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ cohort_id: 'visual-cohort-date', name: '1970s sources', point_ids: ['chunk-late'], projection_id: 'projection-fixed', embedding_set_id: 'embedding-fixed', version: 1, created_at: '2026-10-02T00:00:00' }) })
  })

  await page.goto('/visual-analytics?view=comparative')
  await page.getByLabel('Cohort A name').fill('1970s sources')
  await page.getByLabel('Cohort rule operator').selectOption('or')
  await page.getByLabel('Cohort rule: source type').selectOption('pdf')
  await page.getByLabel('Cohort rule: from year').fill('1970')
  await page.getByLabel('Cohort rule: to year').fill('1979')
  await page.getByRole('button', { name: 'Save cohort A from selection' }).click()

  await expect.poll(() => cohortRequests.length).toBe(1)
  expect(cohortRequests[0]).toMatchObject({ point_ids: ['chunk-early', 'chunk-late'], definition: { source: 'researcher_rule', operator: 'or', source_type: 'pdf', year_from: '1970', year_to: '1979' } })
})

test('temporal view defaults to fixed projection and guards aligned change', async ({ page }) => {
  let projectionRequests = 0
  await page.route('**/api/viz/umap**', (route) => {
    projectionRequests += 1
    return route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ points: [], metadata: { evidence_surface_scope: {} } }),
    })
  })
  await page.route('**/api/viz/temporal-periods', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ periods: [{ period_id: 'period-1', label: 'Documented interval', start_year: 1968, end_year: 1974, authority_source: 'Archive chronology', certainty: 'approximate', notes: 'Date range is reconstructed.' }] }),
  }))

  await page.goto('/visual-analytics?view=temporal')

  await expect(page.getByLabel('Temporal mode')).toHaveValue('fixed')
  const initialProjectionRequests = projectionRequests
  await page.getByLabel('Authority period A').selectOption('period-1')
  await expect(page.getByLabel('Window A from')).toHaveValue('1968')
  await expect(page.getByLabel('Window A to')).toHaveValue('1974')
  await expect(page.getByText('Window A authority: Archive chronology (approximate) - Date range is reconstructed.')).toBeVisible()
  expect(projectionRequests).toBe(initialProjectionRequests)
  await expect(page.getByText('Fixed projection filters change visibility and encoding only. They do not recompute or move stored UMAP coordinates.')).toBeVisible()
  await expect(page.getByRole('button', { name: /Aligned change requires explicit consecutive relation mappings/ })).toBeVisible()
})

test('temporal view loads only validated aligned-run static provenance', async ({ page }) => {
  await page.route('**/api/viz/umap**', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ points: [], metadata: { evidence_surface_scope: {} } }) }))
  await page.route('**/api/viz/temporal-periods', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ periods: [] }) }))
  await page.route('**/api/viz/aligned-runs/aligned-reviewed/static-comparison', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      aligned_run: { aligned_run_id: 'aligned-reviewed', status: 'validated' },
      slices: [{ slice_id: 'period-a', slice_order: 0, period_provenance: { label: 'Documented period A' }, point_count: 4 }, { slice_id: 'period-b', slice_order: 1, period_provenance: { label: 'Documented period B' }, point_count: 5 }],
      relations: [{ relation_id: 'relation-1' }],
      interpretation_limit: 'This static comparison exposes reviewed relation provenance between slices. It does not create aligned coordinates, historical trajectories, or causal claims.',
    }),
  }))

  await page.goto('/visual-analytics?view=temporal')
  await page.getByRole('button', { name: 'Validated aligned-run provenance' }).click()
  await page.getByLabel('Validated aligned run ID').fill('aligned-reviewed')
  await page.getByRole('button', { name: 'Load static comparison' }).click()

  await expect(page.getByText('Validated run: aligned-reviewed')).toBeVisible()
  await expect(page.getByText('0: Documented period A (4 declared points)')).toBeVisible()
  await expect(page.getByText('Static comparison exposes only validated relation provenance. It does not generate coordinates, trails, animation, or historical continuity.')).toBeVisible()
})

test('critical inquiry presets fill an editable researcher proposition without implying a probe marker', async ({ page }) => {
  await page.route('**/api/viz/umap**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ points: [], metadata: { evidence_surface_scope: {} } }),
  }))

  await page.goto('/visual-analytics?view=critical')
  await page.getByLabel('Researcher lens preset').selectOption('maintenance')

  await expect(page.getByLabel('Concept or proposition')).toHaveValue('technical maintenance, infrastructure, coordination, and support work')
  await expect(page.getByRole('button', { name: /Original-space retrieval only/ })).toBeVisible()
})

test('critical inquiry saves an explicit negative probe record after original-space retrieval', async ({ page }) => {
  const records = []
  await page.route('**/api/viz/umap**', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ points: [], metadata: { projection_id: 'projection-fixed', embedding_set_id: 'embedding-fixed', evidence_surface_scope: {} } }) }))
  await page.route('**/api/viz/critical-probe', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ passages: [{ id: 'chunk-1', title: 'Probe result' }] }) }))
  await page.route('**/api/viz/critical-probe-records', async (route) => {
    records.push(route.request().postDataJSON())
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ probe_id: 'visual-probe-1' }) })
  })

  await page.goto('/visual-analytics?view=critical')
  await page.getByLabel('Concept or proposition').fill('absence of attribution')
  await page.getByRole('button', { name: 'Investigate concept' }).click()
  await expect(page.getByRole('button', { name: 'Save probe record' })).toBeEnabled()
  await page.getByLabel('Probe record label').fill('Counterexample scan')
  await page.getByLabel('Researcher probe polarity').selectOption('negative')
  await page.getByRole('button', { name: 'Save probe record' }).click()

  await expect.poll(() => records.length).toBe(1)
  expect(records[0]).toMatchObject({ label: 'Counterexample scan', probe_text: 'absence of attribution', polarity: 'negative', projection_id: 'projection-fixed', embedding_set_id: 'embedding-fixed', retrieval_method: 'original-space embedding retrieval' })
  await expect(page.getByText('Saved probe: visual-probe-1', { exact: true })).toBeVisible()
    await page.route('**/api/viz/critical-probe-records/*', (route) => {
      const probeId = route.request().url().split('/').pop()
      const passages = probeId === 'visual-probe-1' ? [{ id: 'chunk-1' }, { id: 'chunk-2' }] : [{ id: 'chunk-2' }, { id: 'chunk-3' }]
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ probe_id: probeId, results: { passages } }) })
    })
    await page.getByLabel('Saved probe ID to compare').fill('visual-probe-2')
    await page.getByRole('button', { name: 'Compare saved probes' }).click()
    await expect(page.getByText('Saved-probe comparison: current 2 results | comparison 2 results | overlap 1. Result overlap identifies shared retrieval candidates, not evidential confirmation.')).toBeVisible()
})

test('selected source supports an explicit researcher annotation without inferred classification', async ({ page }) => {
  const annotationRequests = []
  const revisionRequests = []
  let historyRequests = 0
  await page.addInitScript(() => {
    sessionStorage.setItem('ddr.visual-analytics.workspace', JSON.stringify({ orbitVersion: 7, selectedIds: ['chunk-1'] }))
  })
  await page.route('**/api/viz/umap**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ points: [{ id: 'chunk-1', chunk_id: 'chunk-1', document_id: 'document-1', title: 'Selected source', x: 0, y: 0 }], metadata: { evidence_surface_scope: { embedded_chunks: 1 } } }),
  }))
  await page.route('**/api/viz/annotations', async (route) => {
    annotationRequests.push({ body: route.request().postDataJSON(), authorization: route.request().headers().authorization })
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ annotation_id: 'visual-annotation-1' }) })
  })
  await page.route('**/api/viz/annotations/**', async (route) => {
    if (route.request().method() === 'PUT') {
      revisionRequests.push(route.request().postDataJSON())
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ annotation_id: 'visual-annotation-1', revision: 2 }) })
      return
    }
    historyRequests += 1
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ annotation_id: 'visual-annotation-1', revisions: [
      { revision: 1, snapshot: { value: { note: 'Does this attribution need corroboration?' } } },
      { revision: 2, snapshot: { value: { note: 'Revised with a source check.' } } },
    ] }) })
  })

  await page.goto('/visual-analytics')
  await page.getByLabel('Annotation type').selectOption('interpretive_question')
  await page.getByLabel('Review status').selectOption('contested')
  await page.getByLabel('Source-linked note').fill('Does this attribution need corroboration?')
  await page.getByRole('button', { name: 'Save annotation' }).click()

  await expect.poll(() => annotationRequests.length).toBe(1)
  expect(annotationRequests[0]).toMatchObject({ authorization: 'Bearer dev-bypass-token', body: { document_id: 'document-1', chunk_id: 'chunk-1', annotation_type: 'interpretive_question', status: 'contested', value: { note: 'Does this attribution need corroboration?' } } })
  await expect(page.getByRole('button', { name: 'Saved annotation: visual-annotation-1' })).toBeVisible()
  await page.getByLabel('Source-linked note').fill('Revised with a source check.')
  await page.getByRole('button', { name: 'Save revision' }).click()
  await expect.poll(() => revisionRequests.length).toBe(1)
  expect(revisionRequests[0]).toMatchObject({ value: { note: 'Revised with a source check.' } })
  await page.getByRole('button', { name: 'View revision history' }).click()
  await expect.poll(() => historyRequests).toBeGreaterThan(0)
  await expect(page.getByText('Revision 1: Does this attribution need corroboration?')).toBeVisible()
  await expect(page.getByText('Revision 2: Revised with a source check.')).toBeVisible()
})