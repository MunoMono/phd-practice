import { test, expect } from '@playwright/test'

const routes = [
  {
    path: '/',
    heading: 'RCA Department of Design Research archive critical inquiry instrument',
    assertions: async (page) => {
      await expect(page.getByRole('heading', { level: 2, name: 'Research apparatus status' })).toBeVisible()
    }
  },
  {
    path: '/sources',
    heading: 'Sources',
    assertions: async (page) => {
      await expect(page.getByText('Methodological distinction')).toBeVisible()
    }
  },
  {
    path: '/source-interrogation',
    heading: 'Source interrogation',
    assertions: async (page) => {
      await expect(page.getByRole('heading', { level: 3, name: 'Research query' })).toBeVisible()
      await expect(page.getByRole('button', { name: 'Run interrogation' })).toBeVisible()
    }
  },
  {
    path: '/absences',
    heading: 'Absences',
    assertions: async (page) => {
      await expect(page.getByRole('heading', { level: 3, name: 'Typology filter and export' })).toBeVisible()
    }
  },
  {
    path: '/cross-readings',
    heading: 'Cross-readings',
    assertions: async (page) => {
      await expect(page.getByRole('heading', { level: 3, name: 'Passage input or list' })).toBeVisible()
    }
  },
  {
    path: '/semantic-atlas',
    heading: 'Semantic Atlas',
    usesPageGrid: false,
    assertions: async (page) => {
      await expect(page.getByRole('heading', { level: 1, name: 'Semantic Atlas' })).toBeVisible()
      await expect(page.getByLabel('Interactive UMAP embedding map').or(page.getByText('Chunk embeddings are not provisioned in the current database. This is a local system coverage state, not evidence of archival absence.'))).toBeVisible()
    }
  },
  {
    path: '/claims-evidence',
    heading: 'Claims and evidence',
    assertions: async (page) => {
      await expect(page.getByRole('heading', { level: 3, name: 'Claim table' })).toBeVisible()
    }
  },
  {
    path: '/provenance',
    heading: 'Provenance',
    assertions: async (page) => {
      await expect(page.getByRole('heading', { level: 3, name: 'Apparatus status' })).toBeVisible()
    }
  },
  {
    path: '/research-runs',
    heading: 'Research runs',
    assertions: async (page) => {
      await expect(page.getByRole('heading', { level: 3, name: 'Saved runs' })).toBeVisible()
    }
  },
  {
    path: '/documentation',
    heading: 'Documentation',
    assertions: async (page) => {
      await expect(page.getByText('Documentation reader')).toBeVisible()
    }
  }
]

for (const route of routes) {
  test(`smoke ${route.path}`, async ({ page }) => {
    await page.goto(route.path, { waitUntil: 'networkidle' })
    await expect(page.getByRole('heading', { level: 1, name: route.heading })).toBeVisible()
    await expect(page.locator('#main-content')).toBeVisible()
    if (route.usesPageGrid !== false) await expect(page.locator('.page-grid')).toBeVisible()
    await route.assertions(page)
  })
}