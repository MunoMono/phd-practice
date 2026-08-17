import { test, expect } from '@playwright/test'

const installAtlasMemoDownloadCapture = async (page) => {
  await page.addInitScript(() => {
    window.__atlasMemoDownload = {}
    URL.createObjectURL = (blob) => {
      window.__atlasMemoDownload.blob = blob
      return 'blob:atlas-memo'
    }
    URL.revokeObjectURL = (url) => { window.__atlasMemoDownload.revokedUrl = url }
    HTMLAnchorElement.prototype.click = function click() {
      window.__atlasMemoDownload.filename = this.download
      window.__atlasMemoDownload.link = this
    }
  })
}

test('empty atlas export records capability state and keeps resonance search inactive', async ({ page }) => {
  await installAtlasMemoDownloadCapture(page)
  await page.route('**/api/viz/umap**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        points: [],
        clusters: [],
        metadata: {
          projection_method: 'none',
          evidence_surface_scope: { embedded_chunks: 0, documents_with_embeddings: 0 }
        },
        message: 'No embedded chunks/documents available for UMAP projection.'
      })
    })
  })

  await page.goto('/semantic-atlas')
  await expect(page.getByText('Atlas not yet generated')).toBeVisible()
  await expect(page.getByText('Inactive experimental capability')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Experimental resonance search unavailable' })).toBeDisabled()

  await page.getByRole('button', { name: 'Export atlas coordinates / cluster summary' }).evaluate((button) => button.click())
  await expect.poll(() => page.evaluate(() => Boolean(window.__atlasMemoDownload.blob))).toBe(true)

  const download = await page.evaluate(async () => ({
    content: await window.__atlasMemoDownload.blob.text(),
    filename: window.__atlasMemoDownload.filename,
    type: window.__atlasMemoDownload.blob.type,
    revokedUrl: window.__atlasMemoDownload.revokedUrl,
    anchorRemoved: !window.__atlasMemoDownload.link.isConnected
  }))

  expect(download.content).toContain('# Visual Analytics Capability State')
  expect(download.content).toContain('No approved embedding/projection was available')
  expect(download.content).toContain('No coordinates were exported.')
  expect(download.content).toContain('No clusters were exported.')
  expect(download.content).toContain('not an analytical interpretation.')
  expect(download.content).not.toContain('# Visual Analytics Memo')
  expect(download.filename).toBe('visual-analytics-memo.md')
  expect(download.type).toBe('text/markdown;charset=utf-8')
  expect(download.revokedUrl).toBe('blob:atlas-memo')
  expect(download.anchorRemoved).toBe(true)
})