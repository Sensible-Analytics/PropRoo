import { test, expect } from '@playwright/test';

test.describe('PropRoo Critical E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    const baseUrl = process.env.PLAYWRIGHT_BASE_URL || 'https://proproo.pages.dev';
    console.log(`Navigating to: ${baseUrl}`);
    await page.goto(baseUrl);
  });

  test('1. App loads without JS errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => {
      if (!err.message.includes('luma') && 
          !err.message.includes('maxTextureDimension2D') &&
          !err.message.includes('i$')) {
        errors.push(err.message);
      }
    });
    await page.waitForTimeout(15000);
    expect(errors.filter(e => !e.includes('luma') && !e.includes('maxTextureDimension2D'))).toHaveLength(0);
  });

  test('2. DuckDB initializes and loads TOP CAGR data', async ({ page }) => {
    await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
  });

  test('3. Property suburb names are displayed', async ({ page }) => {
    await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
    const body = await page.locator('body').innerText();
    expect(body).toContain('Greenlands');
  });

  test('4. Canvas renders', async ({ page }) => {
    await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
    const canvas = page.locator('canvas');
    await expect(canvas.first()).toBeVisible({ timeout: 10000 });
  });

  test('5. No R2 parquet file 404s', async ({ page }) => {
    const failedParquet: string[] = [];
    page.on('requestfailed', request => {
      if (request.url().includes('.parquet')) {
        failedParquet.push(request.url());
      }
    });
    await page.waitForTimeout(20000);
    expect(failedParquet).toHaveLength(0);
  });
});
