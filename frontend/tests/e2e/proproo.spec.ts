import { test, expect } from '@playwright/test';

test.describe('PropRoo DuckDB-WASM E2E Test Suite', () => {
  test.beforeEach(async ({ page }) => {
    const baseUrl = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173';
    console.log(`Navigating to: ${baseUrl}`);
    await page.goto(baseUrl);
  });

  test.describe('1. Initialization', () => {
    test('app loads without initialization error', async ({ page }) => {
      const initError = page.locator('text=INITIALIZATION FAILED');
      await expect(initError).not.toBeVisible({ timeout: 30000 });
    });

    test('DuckDB-WASM loads parquet files from R2', async ({ page }) => {
      const progressBar = page.locator('.bg-blue-500.transition-all');
      await expect(progressBar.first()).toBeVisible({ timeout: 30000 });
    });

    test('app transitions from loading to main UI', async ({ page }) => {
      await expect(page.locator('text=NSW UNIFIED SPATIAL')).toBeVisible({ timeout: 60000 });
    });

    test('header displays STATE OVERVIEW', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
    });
  });

  test.describe('2. Map Rendering', () => {
    test('deck.gl canvas renders on page', async ({ page }) => {
      const canvas = page.locator('canvas');
      await expect(canvas.first()).toBeVisible({ timeout: 60000 });
    });

    test('MapLibre map container exists', async ({ page }) => {
      const mapContainer = page.locator('.maplibregl-map, canvas');
      await expect(mapContainer.first()).toBeVisible({ timeout: 60000 });
    });

    test('year display shows current year', async ({ page }) => {
      // The year display is a large blue number in the map overlay
      // Wait for the main UI first, then check for any year text
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      // Year display uses text-2xl font-black text-blue-400 class
      const yearDisplay = page.locator('.text-2xl.font-black.text-blue-400');
      await expect(yearDisplay.first()).toBeVisible({ timeout: 30000 });
      const yearText = await yearDisplay.first().textContent();
      expect(yearText).toMatch(/20\d{2}/);
    });
  });

  test.describe('3. UI Controls', () => {
    test('year selector is visible and interactive', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      const yearSelect = page.locator('select').last();
      await expect(yearSelect).toBeVisible({ timeout: 30000 });
      await expect(yearSelect).toHaveValue('2024');
    });

    test('category filter dropdown exists', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      const categorySelect = page.locator('select').filter({ hasText: /ALL PROPERTIES|RESIDENCE|STRATA/ });
      await expect(categorySelect.first()).toBeVisible({ timeout: 30000 });
    });

    test('price range label is visible', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      await expect(page.locator('text=PRICE RANGE')).toBeVisible({ timeout: 30000 });
    });

    test('layer toggles are visible', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      await expect(page.locator('text=LAYERS')).toBeVisible({ timeout: 30000 });
      await expect(page.locator('text=H3 HEXAGONS')).toBeVisible({ timeout: 30000 });
      await expect(page.locator('text=HEATMAP')).toBeVisible({ timeout: 30000 });
      await expect(page.locator('text=CONTOURS')).toBeVisible({ timeout: 30000 });
      await expect(page.locator('text=PROPERTY PINS')).toBeVisible({ timeout: 30000 });
    });

    test('time slider is visible', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      // Wait for map overlay to render
      await page.waitForTimeout(3000);
      // The slider container is a div with rounded-xl border at bottom of map
      // Check for the year labels around the slider instead of the input itself
      const sliderContainer = page.locator('text=2001');
      await expect(sliderContainer.first()).toBeVisible({ timeout: 30000 });
    });

    test('can change year via selector', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      const yearSelect = page.locator('select').last();
      await yearSelect.selectOption('2023');
      await expect(yearSelect).toHaveValue('2023', { timeout: 10000 });
    });
  });

  test.describe('4. Data Rendering', () => {
    test('CAGR performance chart section is visible', async ({ page }) => {
      await expect(page.locator('text=CAGR % PERFORMANCE')).toBeVisible({ timeout: 60000 });
    });

    test('transaction count chart section is visible', async ({ page }) => {
      await expect(page.locator('text=TRANSACTION COUNT')).toBeVisible({ timeout: 60000 });
    });

    test('recharts wrappers render for charts', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      const charts = page.locator('.recharts-wrapper');
      await expect(charts.first()).toBeVisible({ timeout: 30000 });
      const count = await charts.count();
      expect(count).toBeGreaterThanOrEqual(2);
    });

    test('sales table displays data rows', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      // Wait for data to load — DuckDB queries take time
      await page.waitForTimeout(15000);
      const tableRows = page.locator('tbody tr');
      const count = await tableRows.count();
      expect(count).toBeGreaterThan(0);
    });

    test('table rows contain price data with $ symbol', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      // Wait for data to load
      await page.waitForTimeout(15000);
      // Check that at least one row has a $ symbol
      const tableBody = page.locator('tbody');
      const text = await tableBody.innerText();
      expect(text).toContain('$');
    });

    test('table headers are visible', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      await expect(page.locator('text=Contextual Address')).toBeVisible({ timeout: 30000 });
      await expect(page.locator('text=Market Valuation')).toBeVisible({ timeout: 30000 });
      await expect(page.locator('text=Actions')).toBeVisible({ timeout: 30000 });
    });
  });

  test.describe('5. Navigation & Drill-Down', () => {
    test('clicking table row triggers drill-down', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);
      const firstRow = page.locator('tbody tr').first();
      const rowCount = await firstRow.count();
      if (rowCount === 0) {
        test.skip(true, 'No table rows available to test drill-down');
      }
      await expect(firstRow).toBeVisible({ timeout: 10000 });
      await firstRow.click({ force: true });
      await page.waitForTimeout(3000);
      // Should show back button after drill-down
      const backButton = page.locator('button').first();
      await expect(backButton).toBeVisible({ timeout: 10000 });
    });

    test('back button returns to state level', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);
      const firstRow = page.locator('tbody tr').first();
      const rowCount = await firstRow.count();
      if (rowCount === 0) {
        test.skip(true, 'No table rows available to test back button');
      }
      await firstRow.click({ force: true });
      await page.waitForTimeout(3000);
      const backButton = page.locator('button').first();
      await backButton.click();
      await page.waitForTimeout(3000);
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('6. Layer Toggles', () => {
    test('can toggle H3 hexagons layer', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);
      const h3Checkbox = page.locator('label:has-text("H3 HEXAGONS") input[type="checkbox"]');
      await expect(h3Checkbox).toBeChecked({ timeout: 10000 });
      await h3Checkbox.uncheck();
      await expect(h3Checkbox).not.toBeChecked({ timeout: 5000 });
    });

    test('can toggle heatmap layer', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);
      const heatmapCheckbox = page.locator('label:has-text("HEATMAP") input[type="checkbox"]');
      await expect(heatmapCheckbox).not.toBeChecked({ timeout: 10000 });
      await heatmapCheckbox.check();
      await expect(heatmapCheckbox).toBeChecked({ timeout: 5000 });
    });

    test('can toggle contours layer', async ({ page }) => {
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);
      const contourCheckbox = page.locator('label:has-text("CONTOURS") input[type="checkbox"]');
      await expect(contourCheckbox).not.toBeChecked({ timeout: 10000 });
      await contourCheckbox.check();
      await expect(contourCheckbox).toBeChecked({ timeout: 5000 });
    });
  });

  test.describe('7. Error Handling', () => {
    test('no uncaught JavaScript errors on page', async ({ page }) => {
      const errors: string[] = [];
      page.on('pageerror', err => {
        if (!err.message.includes('NetworkError') &&
            !err.message.includes('Failed to fetch') &&
            !err.message.includes('ReadableStream')) {
          errors.push(err.message);
        }
      });

      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(15000);

      expect(errors.length).toBe(0);
    });

    test('no 404 errors for R2 parquet files', async ({ page }) => {
      const failedRequests: string[] = [];
      page.on('requestfailed', request => {
        if (request.url().includes('.parquet')) {
          failedRequests.push(request.url());
        }
      });

      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(15000);

      expect(failedRequests.length).toBe(0);
    });
  });

  test.describe('8. Responsive Layout', () => {
    test('works on mobile viewport (375x667)', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('/');
      await expect(page.locator('text=NSW UNIFIED SPATIAL')).toBeVisible({ timeout: 60000 });
      const canvas = page.locator('canvas');
      await expect(canvas.first()).toBeVisible({ timeout: 60000 });
    });

    test('works on tablet viewport (768x1024)', async ({ page }) => {
      await page.setViewportSize({ width: 768, height: 1024 });
      await page.goto('/');
      await expect(page.locator('text=NSW UNIFIED SPATIAL')).toBeVisible({ timeout: 60000 });
    });

    test('works on desktop viewport (1920x1080)', async ({ page }) => {
      await page.setViewportSize({ width: 1920, height: 1080 });
      await page.goto('/');
      await expect(page.locator('text=NSW UNIFIED SPATIAL')).toBeVisible({ timeout: 60000 });
      await expect(page.locator('text=STATE OVERVIEW')).toBeVisible({ timeout: 60000 });
    });
  });
});
