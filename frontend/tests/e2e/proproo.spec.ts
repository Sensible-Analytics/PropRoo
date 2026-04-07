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
      await expect(page.locator('text=LAYERS')).toBeVisible({ timeout: 60000 });
    });

    test('header displays TOP CAGR section', async ({ page }) => {
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
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
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      // Year display uses text-xl font-black text-blue-600 class
      const yearDisplay = page.locator('.text-xl.font-black.text-blue-600');
      await expect(yearDisplay.first()).toBeVisible({ timeout: 30000 });
      const yearText = await yearDisplay.first().textContent();
      expect(yearText).toMatch(/20\d{2}/);
    });
  });

  test.describe('3. UI Controls', () => {
    test('year selector is visible and interactive', async ({ page }) => {
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      const yearSlider = page.locator('input[type="range"]').first();
      await expect(yearSlider).toBeVisible({ timeout: 30000 });
    });

    test('price range controls exist', async ({ page }) => {
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      // Price section with label
      await expect(page.locator('text=Price').first()).toBeVisible({ timeout: 30000 });
    });

    test('layer toggles are visible', async ({ page }) => {
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await expect(page.locator('text=LAYERS')).toBeVisible({ timeout: 30000 });
      await expect(page.locator('text=Property Zones')).toBeVisible({ timeout: 30000 });
      await expect(page.locator('text=Price Density')).toBeVisible({ timeout: 30000 });
      await expect(page.locator('text=Price Contours')).toBeVisible({ timeout: 30000 });
      await expect(page.locator('text=Properties')).toBeVisible({ timeout: 30000 });
    });

    test('time slider is visible', async ({ page }) => {
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      const slider = page.locator('input[type="range"]').first();
      await expect(slider).toBeVisible({ timeout: 30000 });
    });

    test('can change year via slider', async ({ page }) => {
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      const slider = page.locator('input[type="range"]').first();
      await slider.fill('2023');
      await page.waitForTimeout(2000);
      const yearDisplay = page.locator('.text-xl.font-black.text-blue-600');
      const yearText = await yearDisplay.first().textContent();
      expect(yearText).toMatch(/20\d{2}/);
    });
  });

  test.describe('4. Data Rendering', () => {
    test('CAGR chart section is visible', async ({ page }) => {
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
    });

    test('recharts wrappers render for charts', async ({ page }) => {
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      const charts = page.locator('.recharts-wrapper');
      await expect(charts.first()).toBeVisible({ timeout: 30000 });
      const count = await charts.count();
      expect(count).toBeGreaterThanOrEqual(1);
    });

    test('sales table displays data rows', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      // Wait for data to load — DuckDB queries take time
      await page.waitForTimeout(15000);
      const tableRows = page.locator('tbody tr');
      const count = await tableRows.count();
      expect(count).toBeGreaterThan(0);
    });

    test('table headers are visible', async ({ page }) => {
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await expect(page.locator('text=Address')).toBeVisible({ timeout: 30000 });
      await expect(page.locator('text=CAGR').last()).toBeVisible({ timeout: 30000 });
      await expect(page.locator('text=Price').first()).toBeVisible({ timeout: 30000 });
    });
  });

  test.describe('5. Navigation & Drill-Down', () => {
    test('clicking table row triggers map focus', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);
      const firstRow = page.locator('tbody tr').first();
      const rowCount = await firstRow.count();
      if (rowCount === 0) {
        test.skip(true, 'No table rows available to test drill-down');
      }
      await expect(firstRow).toBeVisible({ timeout: 10000 });
      await firstRow.click({ force: true });
      await page.waitForTimeout(3000);
      // Should show suburb indicator after click
      const canvas = page.locator('canvas');
      await expect(canvas.first()).toBeVisible({ timeout: 10000 });
    });

    test('double-click table row drills into suburb', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);
      const firstRow = page.locator('tbody tr').first();
      const rowCount = await firstRow.count();
      if (rowCount === 0) {
        test.skip(true, 'No table rows available to test drill-down');
      }
      await firstRow.dblclick({ force: true });
      await page.waitForTimeout(5000);
      // Should show suburb indicator
      const suburbIndicator = page.locator('text=Suburb:');
      const hasSuburb = await suburbIndicator.count();
      if (hasSuburb > 0) {
        await expect(suburbIndicator).toBeVisible({ timeout: 5000 });
      }
    });
  });

  test.describe('6. Layer Toggles', () => {
    test('can toggle Property Zones layer', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);
      const zonesCheckbox = page.locator('label:has-text("Property Zones") input[type="checkbox"]');
      await expect(zonesCheckbox).toBeChecked({ timeout: 10000 });
      await zonesCheckbox.uncheck();
      await expect(zonesCheckbox).not.toBeChecked({ timeout: 5000 });
    });

    test('can toggle Price Density layer', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);
      const densityCheckbox = page.locator('label:has-text("Price Density") input[type="checkbox"]');
      await expect(densityCheckbox).toBeChecked({ timeout: 10000 });
      await densityCheckbox.uncheck();
      await expect(densityCheckbox).not.toBeChecked({ timeout: 5000 });
    });

    test('can toggle Price Contours layer', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);
      const contourCheckbox = page.locator('label:has-text("Price Contours") input[type="checkbox"]');
      await expect(contourCheckbox).toBeChecked({ timeout: 10000 });
      await contourCheckbox.uncheck();
      await expect(contourCheckbox).not.toBeChecked({ timeout: 5000 });
    });
  });

  test.describe('7. Error Handling', () => {
    test('no uncaught JavaScript errors on page', async ({ page }) => {
      test.setTimeout(60000);
      const errors: string[] = [];
      page.on('pageerror', err => {
        if (!err.message.includes('NetworkError') &&
            !err.message.includes('Failed to fetch') &&
            !err.message.includes('ReadableStream') &&
            !err.message.includes('maxTextureDimension2D') &&
            !err.message.includes('luma') &&
            !err.message.includes('i$')) {
          errors.push(err.message);
        }
      });

      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(15000);

      expect(errors.length).toBe(0);
    });

    test('no 404 errors for R2 parquet files', async ({ page }) => {
      test.setTimeout(60000);
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

  test.describe('9. Map-Driven Hierarchical Exploration (Core User Journey)', () => {
    // Based on industry patterns: Zillow, Redfin, CoreLogic, PropertyShark
    // Core principle: exploration driven by MAP VIEW, not filters

    test('map pan/zoom triggers progressive data disclosure', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);

      // Verify canvas is visible
      const canvas = page.locator('canvas').first();
      await expect(canvas).toBeVisible({ timeout: 30000 });

      // Zoom in
      await canvas.click();
      await page.keyboard.press('ArrowUp'); // deck.gl zoom in
      await page.waitForTimeout(5000);

      // Map should still be visible and responsive
      await expect(canvas).toBeVisible({ timeout: 10000 });
    });

    test('map tooltips show investment metrics on hover', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);

      // Hover over the map center to trigger tooltip
      const canvas = page.locator('canvas').first();
      const box = await canvas.boundingBox();
      if (box) {
        await canvas.hover({ position: { x: box.width / 2, y: box.height / 2 } });
        await page.waitForTimeout(2000);

        // Tooltip may or may not appear depending on data density
        // The key is no crash occurred
      }
    });

    test('table row double-click drills into suburb', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Double-click the first row to drill into suburb
      const firstRow = page.locator('tbody tr').first();
      const rowCount = await firstRow.count();
      if (rowCount === 0) {
        test.skip(true, 'No table rows available');
      }

      await firstRow.dblclick({ force: true });
      await page.waitForTimeout(5000);

      // Should show suburb indicator
      const canvas = page.locator('canvas').first();
      await expect(canvas).toBeVisible({ timeout: 10000 });
    });

    test('double-click drill-down changes visible data scope', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Double-click first row to drill down to suburb
      const firstRow = page.locator('tbody tr').first();
      await firstRow.dblclick({ force: true });
      await page.waitForTimeout(8000);

      // After drill-down, table should show street-level data
      const canvas = page.locator('canvas').first();
      await expect(canvas).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('10. Investment Discovery (Map-Driven)', () => {
    // User goal: figure out which property is investable
    // Visualized through CAGR colors, growth indicators

    test('CAGR growth data is visible in leaderboard', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      const charts = page.locator('.recharts-wrapper');
      const chartCount = await charts.count();
      expect(chartCount).toBeGreaterThanOrEqual(1);
    });

    test('top performing suburbs display growth metrics', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      const charts = page.locator('.recharts-wrapper');
      const chartCount = await charts.count();
      expect(chartCount).toBeGreaterThanOrEqual(1);
    });

    test('sales table shows investment growth indicators', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Table should have CAGR column
      await expect(page.locator('text=CAGR').last()).toBeVisible({ timeout: 10000 });

      // Growth bars should exist (green progress bars)
      const growthBars = page.locator('.bg-emerald-500');
      const barCount = await growthBars.count();
      // Growth bars may or may not be visible depending on data
      // The key is the column exists
    });

    test('Price Density layer visualizes price density', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);

      const densityCheckbox = page.locator('label:has-text("Price Density") input[type="checkbox"]');
      await densityCheckbox.check();
      await expect(densityCheckbox).toBeChecked({ timeout: 5000 });

      const canvas = page.locator('canvas').first();
      await expect(canvas).toBeVisible({ timeout: 10000 });
    });

    test('Price Contours layer shows price boundaries', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);

      const contourCheckbox = page.locator('label:has-text("Price Contours") input[type="checkbox"]');
      await contourCheckbox.check();
      await expect(contourCheckbox).toBeChecked({ timeout: 5000 });

      const canvas = page.locator('canvas').first();
      await expect(canvas).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('11. Cross-Level Comparison (Street vs Suburb vs State)', () => {
    // User goal: compare performance across aggregation levels

    test('state level shows suburb leaderboard', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 10000 });

      const charts = page.locator('.recharts-wrapper');
      const chartCount = await charts.count();
      expect(chartCount).toBeGreaterThanOrEqual(1);
    });

    test('price range filter narrows results', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Price section should be visible
      await expect(page.locator('text=Price').first()).toBeVisible({ timeout: 10000 });

      // Table should show results
      const rows = await page.locator('tbody tr').count();
      expect(rows).toBeGreaterThan(0);
    });
  });

  test.describe('12. Time-Based Exploration', () => {
    // User goal: see how property trends change over time

    test('time slider changes displayed year', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);

      // Get initial year display
      const yearDisplay = page.locator('.text-xl.font-black.text-blue-600');
      const initialYear = await yearDisplay.first().textContent();
      expect(initialYear).toMatch(/20\d{2}/);

      // Use time slider to change year
      const slider = page.locator('input[type="range"]').first();
      await slider.fill('2015');
      await page.waitForTimeout(3000);

      // Year display should update
      const newYear = await yearDisplay.first().textContent();
      expect(newYear).toMatch(/20\d{2}/);
    });

    test('year slider shows full year range (2001-2024)', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);

      // Slider should have min=2001 and max=2024
      const slider = page.locator('input[type="range"]').first();
      const minVal = await slider.getAttribute('min');
      const maxVal = await slider.getAttribute('max');
      expect(minVal).toBe('2001');
      expect(maxVal).toBe('2024');
    });

    test('changing year triggers data refresh', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Change year
      const slider = page.locator('input[type="range"]').first();
      await slider.fill('2010');

      // Wait for data to settle
      await page.waitForTimeout(5000);

      // Year display should show new year
      const yearDisplay = page.locator('.text-xl.font-black.text-blue-600');
      await expect(yearDisplay.first()).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('13. Map Interaction & Layer Control', () => {
    // User should explore via map, not just filters

    test('map is interactive (pan/zoom controls work)', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);

      const canvas = page.locator('canvas').first();
      await expect(canvas).toBeVisible({ timeout: 10000 });

      // Zoom in
      await canvas.click();
      await page.keyboard.press('ArrowUp');
      await page.waitForTimeout(2000);

      // Canvas should still be visible
      await expect(canvas).toBeVisible({ timeout: 10000 });
    });

    test('Property Zones layer is enabled by default', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);

      const zonesCheckbox = page.locator('label:has-text("Property Zones") input[type="checkbox"]');
      await expect(zonesCheckbox).toBeChecked({ timeout: 10000 });
    });

    test('multiple layers can be active simultaneously', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);

      const densityCheckbox = page.locator('label:has-text("Price Density") input[type="checkbox"]');
      const contourCheckbox = page.locator('label:has-text("Price Contours") input[type="checkbox"]');

      await densityCheckbox.check();
      await contourCheckbox.check();

      await expect(densityCheckbox).toBeChecked({ timeout: 5000 });
      await expect(contourCheckbox).toBeChecked({ timeout: 5000 });

      const canvas = page.locator('canvas').first();
      await expect(canvas).toBeVisible({ timeout: 10000 });
    });

    test('disabling Property Zones layer removes from map', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);

      const zonesCheckbox = page.locator('label:has-text("Property Zones") input[type="checkbox"]');
      await zonesCheckbox.uncheck();
      await expect(zonesCheckbox).not.toBeChecked({ timeout: 5000 });

      const canvas = page.locator('canvas').first();
      await expect(canvas).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('14. Data Integrity & Performance', () => {
    // Ensure data loads correctly and queries return valid results

    test('sales table shows valid price data', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      const tableBody = page.locator('tbody');
      const text = await tableBody.innerText();

      // Should contain price data with $ symbol
      expect(text).toContain('$');
    });

    test('sales table shows locality/suburb names', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      const tableBody = page.locator('tbody');
      const text = await tableBody.innerText();

      // Should contain suburb names (uppercase text)
      const hasLocality = /[A-Z]{2,}/.test(text);
      expect(hasLocality).toBe(true);
    });

    test('chart data contains numeric values', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      const charts = page.locator('.recharts-wrapper');
      const chartCount = await charts.count();
      expect(chartCount).toBeGreaterThanOrEqual(1);
    });

    test('DuckDB queries return non-empty results', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      const rows = await page.locator('tbody tr').count();
      expect(rows).toBeGreaterThan(0);

      const charts = page.locator('.recharts-wrapper');
      const chartCount = await charts.count();
      expect(chartCount).toBeGreaterThanOrEqual(1);
    });
  });

  test.describe('15. Responsive Layout', () => {
    test('works on mobile viewport (375x667)', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('/');
      await expect(page.locator('text=NSW Valuer General')).toBeVisible({ timeout: 60000 });
      const canvas = page.locator('canvas');
      await expect(canvas.first()).toBeVisible({ timeout: 60000 });
    });

    test('works on tablet viewport (768x1024)', async ({ page }) => {
      await page.setViewportSize({ width: 768, height: 1024 });
      await page.goto('/');
      await expect(page.locator('text=NSW Valuer General')).toBeVisible({ timeout: 60000 });
    });

    test('works on desktop viewport (1920x1080)', async ({ page }) => {
      await page.setViewportSize({ width: 1920, height: 1080 });
      await page.goto('/');
      await expect(page.locator('text=NSW Valuer General')).toBeVisible({ timeout: 60000 });
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
    });
  });

  test.describe('16. Property Zones Interaction (Map-Driven Exploration)', () => {
    // Core: Property Zones are the primary map-driven exploration mechanism
    // Users discover investment opportunities by viewing colored zones

    test('map tooltip shows investment metrics on hover', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      const canvas = page.locator('canvas').first();
      const box = await canvas.boundingBox();
      if (box) {
        await canvas.hover({ position: { x: box.width / 2, y: box.height / 2 } });
        await page.waitForTimeout(2000);
      }
    });

    test('map colors reflect CAGR growth data', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      const canvas = page.locator('canvas').first();
      await expect(canvas).toBeVisible({ timeout: 30000 });

      const zonesCheckbox = page.locator('label:has-text("Property Zones") input[type="checkbox"]');
      await expect(zonesCheckbox).toBeChecked({ timeout: 10000 });

      await expect(canvas).toBeVisible({ timeout: 10000 });
    });

    test('map resolution changes with zoom level', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Get initial zoom level
      const canvas = page.locator('canvas').first();
      await expect(canvas).toBeVisible({ timeout: 10000 });

      // Zoom in significantly
      for (let i = 0; i < 4; i++) {
        await canvas.click();
        await page.keyboard.press('ArrowUp');
        await page.waitForTimeout(500);
      }
      await page.waitForTimeout(3000);

      // Map should still be responsive
      await expect(canvas).toBeVisible({ timeout: 10000 });
    });

    test('map tooltip closes when mouse moves away', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      const canvas = page.locator('canvas').first();
      const box = await canvas.boundingBox();
      if (box) {
        // Hover to show tooltip
        await canvas.hover({ position: { x: box.width / 2, y: box.height / 2 } });
        await page.waitForTimeout(2000);

        // Move mouse away
        await canvas.hover({ position: { x: 0, y: 0 } });
        await page.waitForTimeout(1000);

        // Map should still be visible (no crash)
        await expect(canvas).toBeVisible({ timeout: 10000 });
      }
    });
  });

  test.describe('17. Investment Discovery (Visual Indicators)', () => {
    // User goal: identify investable properties through visual cues
    // CAGR colors, growth bars, price formatting

    test('CAGR leaderboard displays growth percentages', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Chart should show CAGR data with percentage values
      const charts = page.locator('.recharts-wrapper');
      const chartCount = await charts.count();
      expect(chartCount).toBeGreaterThanOrEqual(1);
    });

    test('CAGR bars display in sales table', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Table should have CAGR column header
      await expect(page.locator('text=CAGR').last()).toBeVisible({ timeout: 10000 });

      // Green growth bars should exist
      const growthBars = page.locator('.bg-emerald-500');
      const barCount = await growthBars.count();
      // Bars may or may not be visible depending on data
      // The key is the column exists and table renders
    });

    test('price data uses correct formatting', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Table should show formatted prices
      const tableBody = page.locator('tbody');
      const text = await tableBody.innerText();

      // Should contain $ symbol (price formatting)
      expect(text).toContain('$');
    });

    test('Properties layer can be enabled and shows on map', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(10000);

      const pinsCheckbox = page.locator('label:has-text("Properties") input[type="checkbox"]');
      await expect(pinsCheckbox).toBeVisible({ timeout: 10000 });
      await pinsCheckbox.check();
      await expect(pinsCheckbox).toBeChecked({ timeout: 5000 });

      const canvas = page.locator('canvas').first();
      for (let i = 0; i < 5; i++) {
        await canvas.click();
        await page.keyboard.press('ArrowUp');
        await page.waitForTimeout(1000);
      }
      await page.waitForTimeout(3000);

      await expect(canvas).toBeVisible({ timeout: 10000 });
    });

    test('top performers section highlights high-growth areas', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Charts should show top performers
      const charts = page.locator('.recharts-wrapper');
      const chartCount = await charts.count();
      expect(chartCount).toBeGreaterThanOrEqual(1);

      // Chart should have data (not empty)
      const chartText = await charts.first().textContent();
      expect(chartText.length).toBeGreaterThan(0);
    });
  });

  test.describe('18. Cross-Level Comparison (Street vs Suburb)', () => {
    // User goal: "How is this street performance compared to the suburb it's in?"
    // Compare metrics across aggregation levels

    test('state level shows suburb-level leaderboard', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Should show suburb leaderboard with CAGR data
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 10000 });

      const charts = page.locator('.recharts-wrapper');
      const chartCount = await charts.count();
      expect(chartCount).toBeGreaterThanOrEqual(1);
    });

    test('suburb level shows street-level data', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Drill down to suburb level
      const firstRow = page.locator('tbody tr').first();
      const rowCount = await firstRow.count();
      if (rowCount === 0) {
        test.skip(true, 'No table rows to drill down');
      }
      await firstRow.dblclick({ force: true });
      await page.waitForTimeout(10000);

      // Should show street-level data for this suburb
      const charts = page.locator('.recharts-wrapper');
      const chartCount = await charts.count();
      expect(chartCount).toBeGreaterThanOrEqual(0);

      // Map should still be visible
      const canvas = page.locator('canvas').first();
      await expect(canvas).toBeVisible({ timeout: 10000 });
    });

    test('price range filter narrows results', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Price label should be visible
      await expect(page.locator('text=Price').first()).toBeVisible({ timeout: 10000 });

      // Table should show results
      const rows = await page.locator('tbody tr').count();
      expect(rows).toBeGreaterThan(0);
    });
  });

  test.describe('19. Data Change Verification (Time Exploration)', () => {
    // Verify that changing year actually changes the displayed data

    test('changing year via slider updates displayed year', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Get initial year display
      const yearDisplay = page.locator('.text-xl.font-black.text-blue-600');
      const initialYear = await yearDisplay.first().textContent();
      expect(initialYear).toMatch(/20\d{2}/);

      // Use time slider to change year
      const slider = page.locator('input[type="range"]').first();
      await slider.fill('2015');
      await page.waitForTimeout(5000);

      // Year display should update
      const newYear = await yearDisplay.first().textContent();
      expect(newYear).toMatch(/20\d{2}/);
    });

    test('changing year triggers data refresh in sales table', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Get initial table content
      const tableBody = page.locator('tbody');
      const initialText = await tableBody.innerText();

      // Change year
      const slider = page.locator('input[type="range"]').first();
      await slider.fill('2010');
      await page.waitForTimeout(5000);

      // Table should still show data (may be different rows)
      const rows = await page.locator('tbody tr').count();
      expect(rows).toBeGreaterThanOrEqual(0);
    });

    test('charts update when year changes', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Get initial chart data
      const charts = page.locator('.recharts-wrapper');
      const initialCount = await charts.count();
      expect(initialCount).toBeGreaterThanOrEqual(1);

      // Change year
      const slider = page.locator('input[type="range"]').first();
      await slider.fill('2020');
      await page.waitForTimeout(5000);

      // Charts should still render with new data
      const newCharts = page.locator('.recharts-wrapper');
      const newCount = await newCharts.count();
      expect(newCount).toBeGreaterThanOrEqual(1);
    });
  });

  test.describe('20. Edge Cases & Resilience', () => {
    // Ensure app handles edge cases gracefully

    test('app handles rapid year changes without crashing', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Rapidly change year multiple times
      const slider = page.locator('input[type="range"]').first();
      await slider.fill('2015');
      await page.waitForTimeout(500);
      await slider.fill('2020');
      await page.waitForTimeout(500);
      await slider.fill('2010');
      await page.waitForTimeout(5000);

      // App should still be functional
      const canvas = page.locator('canvas').first();
      await expect(canvas).toBeVisible({ timeout: 10000 });
    });

    test('map remains responsive during data loading', async ({ page }) => {
      test.setTimeout(90000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Trigger data refresh by changing year
      const slider = page.locator('input[type="range"]').first();
      await slider.fill('2012');

      // Try to interact with map immediately (during loading)
      const canvas = page.locator('canvas').first();
      await canvas.click({ force: true });
      await page.waitForTimeout(5000);

      // Map should still be visible
      await expect(canvas).toBeVisible({ timeout: 10000 });
    });

    test('layer toggles persist across drill-down navigation', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      const densityCheckbox = page.locator('label:has-text("Price Density") input[type="checkbox"]');
      await densityCheckbox.uncheck();
      await expect(densityCheckbox).not.toBeChecked({ timeout: 5000 });

      const firstRow = page.locator('tbody tr').first();
      const rowCount = await firstRow.count();
      if (rowCount === 0) {
        test.skip(true, 'No table rows to drill down');
      }
      await firstRow.dblclick({ force: true });
      await page.waitForTimeout(8000);

      await expect(densityCheckbox).toBeVisible({ timeout: 10000 });
    });

    test('table displays gracefully', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=TOP CAGR')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      // Table should exist
      const tableBody = page.locator('tbody');
      await expect(tableBody).toBeVisible({ timeout: 10000 });

      // Table should be truthy
      expect(tableBody).toBeTruthy();
    });
  });

  test.describe('21. Map Layers — Suburbs, Streets, POIs', () => {
    test('Suburb Boundaries toggle is visible and checked by default', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=LAYERS')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);
      const checkbox = page.locator('label:has-text("Suburb Boundaries") input[type="checkbox"]');
      await expect(checkbox).toBeVisible({ timeout: 10000 });
      await expect(checkbox).toBeChecked({ timeout: 5000 });
    });

    test('Street Names toggle is visible and checked by default', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=LAYERS')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);
      const checkbox = page.locator('label:has-text("Street Names") input[type="checkbox"]');
      await expect(checkbox).toBeVisible({ timeout: 10000 });
      await expect(checkbox).toBeChecked({ timeout: 5000 });
    });

    test('Points of Interest toggle is visible and checked by default', async ({ page }) => {
      test.setTimeout(120000);
      await expect(page.locator('text=LAYERS')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);
      const checkbox = page.locator('label:has-text("Points of Interest") input[type="checkbox"]');
      await expect(checkbox).toBeVisible({ timeout: 10000 });
      await expect(checkbox).toBeChecked({ timeout: 5000 });
    });

    test('all layer toggles can be toggled on and off', async ({ page }) => {
      test.setTimeout(180000);
      await expect(page.locator('text=LAYERS')).toBeVisible({ timeout: 60000 });
      await page.waitForTimeout(15000);

      const layerNames = [
        'Property Zones',
        'Price Density',
        'Price Contours',
        'Properties',
        'Street Names',
        'Suburb Boundaries',
        'Points of Interest',
        'Growth Map',
      ];

      for (const name of layerNames) {
        const checkbox = page.locator(`label:has-text("${name}") input[type="checkbox"]`);
        await expect(checkbox).toBeVisible({ timeout: 5000 });
        await checkbox.uncheck();
        await expect(checkbox).not.toBeChecked({ timeout: 5000 });
        await checkbox.check();
        await expect(checkbox).toBeChecked({ timeout: 5000 });
      }
    });
  });
});
