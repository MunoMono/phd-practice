import { test, expect } from '@playwright/test'

const ddrPublicRecordRouteAvailable = globalThis.process?.env.DDR_PUBLIC_RECORD_ROUTE_AVAILABLE === 'true'
const calendarDocumentId = 'doc_964614721622_ba420b8ee1f2'
const calendarRecordPid = '880612075513'
const calendarMediaPid = '964614721622'
const calendarAssetPid = '711095685552'
const calendarRecordUri = `https://ddrarchive.org/id/record/${calendarRecordPid}`

const openCalendarProvenance = async (page) => {
  await page.goto('/sources', { waitUntil: 'networkidle' })
  await page.getByRole('tab', { name: 'Provenance' }).click()
}

const expectField = (page, label, value) => expect(
  page.locator('.corpus-panel__field-row').filter({ hasText: label }).filter({ hasText: value })
).toBeVisible()

test('Sources preserves canonical identity while the DDR public record route is unavailable', async ({ page }) => {
  test.skip(ddrPublicRecordRouteAvailable, 'This assertion covers the current disabled capability state.')

  await openCalendarProvenance(page)

  await page.getByRole('tab', { name: 'Overview' }).click()
  await expectField(page, 'Document ID', calendarDocumentId)
  await expectField(page, 'Archive record PID', calendarRecordPid)
  await expectField(page, 'Attached-media PID', calendarMediaPid)
  await expectField(page, 'Asset PID', calendarAssetPid)
  await expectField(page, 'DDR public record URI', calendarRecordUri)
  await page.getByRole('tab', { name: 'Provenance' }).click()
  await expect(page.getByRole('button', { name: 'DDR public record currently unavailable' })).toBeDisabled()
  await expect(page.getByText('The authoritative DDR record URI is retained, but the public DDR record interface does not currently resolve this record.')).toBeVisible()
})

test('Sources opens the unchanged canonical URI only when the capability is enabled', async ({ page }) => {
  test.skip(!ddrPublicRecordRouteAvailable, 'Run this assertion against an explicitly enabled capability build.')

  await page.addInitScript(() => {
    window.__ddrPublicRecordOpenCalls = []
    window.open = (...argumentsList) => {
      window.__ddrPublicRecordOpenCalls.push(argumentsList)
      return null
    }
  })

  await openCalendarProvenance(page)
  await page.getByRole('button', { name: 'Open DDR source' }).click()

  await expect.poll(() => page.evaluate(() => window.__ddrPublicRecordOpenCalls)).toEqual([
    [calendarRecordUri, '_blank', 'noopener,noreferrer']
  ])
  await page.getByRole('tab', { name: 'Overview' }).click()
  await expectField(page, 'Document ID', calendarDocumentId)
})