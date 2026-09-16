const { test, expect } = require('@playwright/test');

const BASE_URL = 'https://innovationdesign.io';

test.describe('Production Smoke Validation', () => {
  test('Root Page (/)', async ({ page }) => {
    const response = await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    expect(response.status()).toBe(200);
    expect(page.url()).toBe(BASE_URL + '/');
    expect(page.url().startsWith('https://')).toBe(true);
    await expect(page.locator('h1')).toContainText('Critical testamentary traces of contested design knowledge using multimodal machine learning and visual analytics');
    await expect(page.locator('body')).toContainText('Powered by IBM Granite');
    await expect(page.locator('h2')).toContainText('Research workflow');
  });

  test('Corpus Explorer (/corpus)', async ({ page }) => {
    await page.goto(`${BASE_URL}/corpus`, { waitUntil: 'networkidle' });
    await expect(page.locator('h1')).toContainText('Corpus explorer');
                                                                  us                                                  on',                                              });
                                                   }) => {
    await page.goto(`${BASE_URL}/tracer`    await page.goto(`${BASE_URL}/tracer`    await page.goto(`${BASE_URL}/traai    await page.goto(`${BASE_URL}/tracerec    await page.goto(`${BASE_URL}/tracer`earch    await page.goto(`${BASE_URL}/tracer`    await page.ame: 'Trace evidence' })).toBeVisible();
  });

  test('Visual Analytics (/visual-analytics)', async ({ page }) => {
    await page.goto(`${BASE_URL}/visual-analytics`, { w    await page.goto(`${BASE_URL}/visual-analytics`, { w    await page.goinText('Visual analytics');
    await expect(page.locator('body')).toContainText('Partial evidence surface');
    await expect(page.locator('h3')).toContainText('UMAP projection');
  });

  test('Session Recorder (/sessions)', async ({ page }) => {
    await page.goto(`${BASE_URL}/sessions    await page.goto(`${BASE_URL}/sessions    await page.goto(`${BASE_URL}/sessions    await page.goto(`${BASE_URL}/sessions    await page.goto(`${BASE_URL}/sessions t sessi    await page.goto(`${BASE_URL}/sessions    await pnText('Confidence');
  });

  test('Experimental Log (/experiments)', async ({ page }) => {
    await page.goto(`${BASE_URL}/experiments`, { waitUntil: 'networkidle' });
    await expect(page.locator('h1')).toContainText('Experimental log');
    await expect(page.locator('h3')).toContainText('Training loss curves    await expect(page.locator('h3')).toContainText('Training loing ru    await expect(page.locator('h3')).toContainText('Training loss curves    await expect(page.locator('h3')).toContainText('Training loing ru    await eil:    await expect(page.locator('h3')).toContainText('Training loss curves    awaising dashboard');
    await expect(page.getByRole('button', { name: 'Refresh sta    await expect(page.getByRole('button', { name: 'Refredy')).toContainText('Granite archive chat');
  });
});
