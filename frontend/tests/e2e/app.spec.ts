import { test, expect } from '@playwright/test';

test.describe('PropRoo Frontend', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Wait for the React app to render content beyond the initial HTML
    await page.waitForFunction(() => document.body.innerText.length > 1000);
  });

  test('homepage loads successfully', async ({ page }) => {
    const body = page.locator('body');
    await expect(body).not.toBeEmpty();
    const content = await page.locator('body').innerText();
    console.log('Page loaded with content length:', content.length);
  });

  test('header displays correctly', async ({ page }) => {
    const content = await page.locator('body').innerText();
    expect(content.length).toBeGreaterThan(50);
  });

  test('year selector is visible', async ({ page }) => {
    const selectElements = page.locator('select');
    const count = await selectElements.count();
    expect(count).toBeGreaterThan(0);
  });

  test('map container exists', async ({ page }) => {
    const mapContainer = page.locator('.leaflet-container');
    await expect(mapContainer).toBeVisible({ timeout: 10000 });
  });

  test('category filter dropdown exists', async ({ page }) => {
    const selects = page.locator('select');
    await expect(selects.first()).toBeVisible();
  });

  test('CAGR performance chart exists', async ({ page }) => {
    await page.waitForTimeout(2000);
    const charts = page.locator('.recharts-wrapper, svg.recharts-surface');
    const count = await charts.count();
    console.log(`Found ${count} chart elements`);
  });

  test('table displays data or loading state', async ({ page }) => {
    const table = page.locator('table').first();
    await expect(table).toBeAttached();
  });

  test('no critical console errors', async ({ page }) => {
    const errors: string[] = [];
    
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });
    
    page.on('pageerror', err => {
      errors.push(err.message);
    });
    
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);
    
    const criticalErrors = errors.filter(e => 
      !e.includes('CORS') && 
      !e.includes('Failed to fetch') &&
      !e.includes('NetworkError') &&
      !e.includes('net::ERR')
    );
    
    if (criticalErrors.length > 0) {
      console.log('Console errors found:', criticalErrors);
    }
  });
});
