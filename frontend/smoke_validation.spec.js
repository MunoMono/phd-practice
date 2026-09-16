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
    await expect(page.locator('body')).toContainText('Current corpu    await expect(page.locator('body')).toContainTexon', { name: 'Reset filters' })).toBeVisible();
  });  });  });  });  });  });  });  });  });  });  }age }  });  });  });  });  });  });  });  });  })er`, { waitUntil: 'networkidle' });
    await expect(page.locator('h1')).toConta    await expect(page.locator('h1')).txpe    await expect(page.locator('h1')).toConarc    await expect(page.locator('h1')).toConta    await exame: 'Trace evidence' })).toBeVisible();
  });

  test('Visual Analytics (/visual-analytics)', async ({ page }) => {
    await page.goto(`${BASE_URL}/visual-analytics`, { w    await page.goto(`${BASE_URL}/visual-analytics`, { w    await page.goto(`${('    await page.goto(`${BASE_URL}/visual-analytics`, { w    await page.gt('Partial evidence surface');
    await expect(page.locator('h3'))    await expect(page.locator('h3'))    await expect(page.locator('h3')ssions)', async ({ page }) => {
    await page.goto(`${BASE_URL}/sessions    await page.goto(`${BASE_URL}/sessions    await page.goto(`${BASE_URL}/sessions    await page.goto(`${BASE_URL}/sessions    await page.goto(`${BASE_URL}/sessionsnt sessions');
    await expect(page.locator('th')).toContainText('Confidence');
  });

  test('Experimental Log (/experiments)', async ({ p  test('Experimental Log (/experiments)', async ({ p  test('Experimental Log (/experiments)', async ({ p  test('Experimental Log (/experiments)', async ({ p  test('Experimental Log (/experiments)', async ({ p  test('Experimenss curves  test('Experimental Log (/experiments)', async ({ p  test('Experg run provenance');
  });

  test('ML Processing Dashboard (/ml-dashboard)', async ({ page }) => {
    await page.goto(`${BASE_URL}/ml-dashboard`, { waitUntil: 'networkidle' });
    await expect(page.locator('h1')).toContainText('ML processi    await expect(page.locator('h1')).toContainText('ML processi    await expect(page.locator('h1')).toContainText('ML processi    await e)).toContainText('Granite archive chat');
  });
});
