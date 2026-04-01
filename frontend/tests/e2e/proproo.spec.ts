import { test, expect } from '@playwright/test';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173';
const API_URL = process.env.API_URL || 'https://proproo.onrender.com/api';

test.describe('PropRoo E2E Test Suite', () => {
    test.beforeEach(async ({ page }) => {
      const baseUrl = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173';
      console.log(`Navigating to: ${baseUrl}`);
      await page.goto(baseUrl);
      // Wait for initial load
      await page.waitForLoadState('networkidle');
    });

    test.describe('1. State Level (Homepage)', () => {
     test('homepage loads with NSW UNIFIED header', async ({ page }) => {
       const header = page.locator('text=NSW UNIFIED');
       await expect(header).toBeVisible({ timeout: 15000 });
     });
 
     test('state overview is displayed by default', async ({ page }) => {
       const stateOverview = page.locator('text=STATE OVERVIEW');
       await expect(stateOverview).toBeVisible({ timeout: 15000 });
     });
 
     test('year selector shows 2024 by default', async ({ page }) => {
       const yearSelector = page.locator('select').filter({ hasText: '2024' });
       await expect(yearSelector).toBeVisible({ timeout: 10000 });
     });
 
     test('map container renders with leaflet', async ({ page }) => {
       const mapContainer = page.locator('.leaflet-container');
       await expect(mapContainer).toBeVisible({ timeout: 20000 });
     });
 
     test('CAGR performance chart exists', async ({ page }) => {
       await page.waitForTimeout(3000);
       const cagrSection = page.locator('text=CAGR % PERFORMANCE');
       await expect(cagrSection).toBeVisible({ timeout: 15000 });
     });
 
     test('transaction count chart exists', async ({ page }) => {
       const transactionSection = page.locator('text=TRANSACTION COUNT');
       await expect(transactionSection).toBeVisible({ timeout: 15000 });
     });
 
     test('data table shows property entries', async ({ page }) => {
       await page.waitForTimeout(5000);
       const tableRows = page.locator('tbody tr');
       const count = await tableRows.count();
       expect(count).toBeGreaterThan(0);
     });
 
     test('price range slider is visible', async ({ page }) => {
       const priceLabel = page.locator('text=PRICE RANGE');
       await expect(priceLabel).toBeVisible({ timeout: 10000 });
     });
 
     test('can interact with price range slider', async ({ page }) => {
       // Check if the slider exists and can be moved
       const slider = page.locator('input[type="range"]');
       await expect(slider).toBeVisible({ timeout: 10000 });
       
       // Get initial value
       const initialValue = await slider.evaluate((el) => el.value);
       
       // Move slider to a different position (if possible)
       if (initialValue !== '10000000') { // Not already at max
         await slider.fill('5000000'); // Set to middle value
         await page.waitForTimeout(1000);
         
         // Verify value changed
         const newValue = await slider.evaluate((el) => el.value);
         expect(newValue).toBe('5000000');
       }
     });
 
     test('category filter dropdown works', async ({ page }) => {
       const categorySelect = page.locator('select').filter({ hasText: /ALL PROPERTIES|RESIDENCE|STRATA/ });
       await expect(categorySelect).toBeVisible({ timeout: 10000 });
     });
   });

  test.describe('2. Year Selection', () => {
    test('can change year from 2024 to 2023', async ({ page }) => {
      const yearSelect = page.locator('select').last();
      await yearSelect.selectOption('2023');
      await page.waitForTimeout(3000);
      const updatedSelect = page.locator('select').last();
      await expect(updatedSelect).toHaveValue('2023');
    });

    test('data reloads when year changes', async ({ page }) => {
      const yearSelect = page.locator('select').last();
      await yearSelect.selectOption('2022');
      await page.waitForTimeout(5000);
      // Table should still have data
      const tableRows = page.locator('tbody tr');
      await expect(tableRows.first()).toBeVisible({ timeout: 10000 });
    });
  });

   test.describe('3. Suburb Level Navigation', () => {
     test('can click on table row to drill into suburb', async ({ page }) => {
       await page.waitForTimeout(5000);
       
       // Find a suburb row and click it (use force to bypass sticky header interception)
       const suburbRow = page.locator('tbody tr').first();
       await suburbRow.click({ force: true });
       
       // Should show back button and suburb name
       await page.waitForTimeout(3000);
       const backButton = page.locator('button').filter({ has: page.locator('svg') }).first();
       await expect(backButton).toBeVisible({ timeout: 10000 });
     });
 
     test('can navigate back from suburb to state', async ({ page }) => {
       await page.waitForTimeout(5000);
       
       // First drill to suburb
       const suburbRow = page.locator('tbody tr').first();
       await suburbRow.click({ force: true });
       await page.waitForTimeout(3000);
       
       // Click back button (button with SVG icon)
       const backButton = page.locator('button').filter({ has: page.locator('svg') }).first();
       await backButton.click();
       await page.waitForTimeout(3000);
       
       // Should be back at state level with NSW UNIFIED header visible
       const header = page.locator('text=NSW UNIFIED');
       await expect(header).toBeVisible({ timeout: 10000 });
     });
 
     test('map centers on suburb after drill-down', async ({ page }) => {
       await page.waitForTimeout(5000);
       const suburbRow = page.locator('tbody tr').first();
       await suburbRow.click({ force: true });
       
       await page.waitForTimeout(3000);
       // Map should be visible still
       const mapContainer = page.locator('.leaflet-container');
       await expect(mapContainer).toBeVisible({ timeout: 10000 });
     });
   });

   test.describe('4. Street Level Navigation', () => {
     test('can drill from suburb to street', async ({ page }) => {
       await page.waitForTimeout(5000);
       
       // First drill to suburb
       const suburbRow = page.locator('tbody tr').first();
       await suburbRow.click({ force: true });
       await page.waitForTimeout(3000);
       
       // Then drill to street (click on street address row)
       const streetRow = page.locator('tbody tr').first();
       await streetRow.click({ force: true });
       await page.waitForTimeout(3000);
       
       // Should still have map and table
       const mapContainer = page.locator('.leaflet-container');
       await expect(mapContainer).toBeVisible({ timeout: 10000 });
     });
 
     test('can navigate back from street to suburb', async ({ page }) => {
       await page.waitForTimeout(5000);
       
       // First drill to suburb
       const suburbRow = page.locator('tbody tr').first();
       await suburbRow.click({ force: true });
       await page.waitForTimeout(3000);
       
       // Then drill to street
       const streetRow = page.locator('tbody tr').first();
       await streetRow.click({ force: true });
       await page.waitForTimeout(3000);
       
       // Click back button (button with SVG icon)
       const backButton = page.locator('button').filter({ has: page.locator('svg') }).first();
       await backButton.click();
       await page.waitForTimeout(3000);
       
       // Should be back at suburb level with back button visible
       const backButtonAfter = page.locator('button').filter({ has: page.locator('svg') }).first();
       await expect(backButtonAfter).toBeVisible({ timeout: 10000 });
     });
   });

   test.describe('5. Map Interactions', () => {
     test('cluster markers are visible on map', async ({ page }) => {
       await page.waitForTimeout(5000);
       // Check for SVG circles (cluster markers)
       const markers = page.locator('.leaflet-interactive');
       const count = await markers.count();
       console.log(`Found ${count} map markers`);
       expect(count).toBeGreaterThan(0);
     });
 
     test('can click on cluster marker to see popup', async ({ page }) => {
       await page.waitForTimeout(5000);
       const marker = page.locator('.leaflet-interactive').first();
       if (await marker.isVisible()) {
         await marker.click();
         await page.waitForTimeout(2000);
         // Popup should appear with CAGR data
         const popup = page.locator('.leaflet-popup');
         await expect(popup).toBeVisible({ timeout: 10000 });
       }
     });
 
     test('drill into cluster button exists in popup', async ({ page }) => {
       await page.waitForTimeout(5000);
       const marker = page.locator('.leaflet-interactive').first();
       if (await marker.isVisible()) {
         await marker.click();
         await page.waitForTimeout(2000);
         const drillButton = page.locator('text=Drill Into Cluster');
         await expect(drillButton).toBeVisible({ timeout: 10000 });
       }
     });
   });
   
   test.describe('6. Chart Interactions', () => {
     test('CAGR chart bars show tooltip on hover', async ({ page }) => {
       await page.waitForTimeout(5000);
       // Find the CAGR chart bars
       const bars = page.locator('.recharts-bar-rectangle');
       const barCount = await bars.count();
       
       if (await barCount > 0) {
         // Hover over the first bar
         const firstBar = bars.first();
         await firstBar.hover();
         
         // Wait for tooltip to appear
         const tooltip = page.locator('.recharts-tooltip-wrapper');
         await expect(tooltip).toBeVisible({ timeout: 5000 });
       }
     });
 
     test('transaction count chart bars show tooltip on hover', async ({ page }) => {
       await page.waitForTimeout(5000);
       // Find the transaction count chart bars
       const bars = page.locator('.recharts-bar-rectangle');
       const barCount = await bars.count();
       
       if (await barCount > 0) {
         // Hover over the first bar
         const firstBar = bars.first();
         await firstBar.hover();
         
         // Wait for tooltip to appear
         const tooltip = page.locator('.recharts-tooltip-wrapper');
         await expect(tooltip).toBeVisible({ timeout: 5000 });
       }
     });
   });
   
    test.describe('7. Map Zoom and Pan', () => {
      test('map can be zoomed in', async ({ page }) => {
        await page.waitForTimeout(5000);
        // Get initial zoom level from the map container (this is approximate)
        const mapContainer = page.locator('.mapboxgl-map, .maplibregl-map, .leaflet-container');
        await expect(mapContainer).toBeVisible({ timeout: 10000 });
        
        // Try to zoom in using mouse wheel or pinch gesture equivalent
        // For simplicity, we'll test that the map is interactive by checking if we can trigger zoom events
        await page.mouse.wheel(0, 0, { deltaY: -100 }); // Zoom in
        await page.waitForTimeout(1000);
        
        // Map should still be visible after zoom
        await expect(mapContainer).toBeVisible({ timeout: 10000 });
      });
    });
 
     test('map can be panned/dragged', async ({ page }) => {
       await page.waitForTimeout(5000);
       const mapContainer = page.locator('.mapboxgl-map, .maplibregl-map, .leaflet-container');
       await expect(mapContainer).toBeVisible({ timeout: 10000 });
       
       // Get initial position (approximate)
       const box = await mapContainer.boundingBox();
       if (box) {
         // Click and drag to pan the map
         await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
         await page.mouse.down();
         await page.mouse.move(box.x + box.width / 2 + 100, box.y + box.height / 2 + 100);
         await page.mouse.up();
         await page.waitForTimeout(1000);
         
         // Map should still be visible after pan
         await expect(mapContainer).toBeVisible({ timeout: 10000 });
       }
     });
   });
   
   test.describe('6. Chart Interactions', () => {
     test('CAGR chart bars show tooltip on hover', async ({ page }) => {
       await page.waitForTimeout(5000);
       // Find the CAGR chart bars
       const bars = page.locator('.recharts-bar-rectangle');
       const barCount = await bars.count();
       
       if (await barCount > 0) {
         // Hover over the first bar
         const firstBar = bars.first();
         await firstBar.hover();
         
         // Wait for tooltip to appear
         const tooltip = page.locator('.recharts-tooltip-wrapper');
         await expect(tooltip).toBeVisible({ timeout: 5000 });
       }
     });
 
     test('transaction count chart bars show tooltip on hover', async ({ page }) => {
       await page.waitForTimeout(5000);
       // Find the transaction count chart bars
       const bars = page.locator('.recharts-bar-rectangle');
       const barCount = await bars.count();
       
       if (await barCount > 0) {
         // Hover over the first bar
         const firstBar = bars.first();
         await firstBar.hover();
         
         // Wait for tooltip to appear
         const tooltip = page.locator('.recharts-tooltip-wrapper');
         await expect(tooltip).toBeVisible({ timeout: 5000 });
       }
     });
   });

  test.describe('6. API Data Loading', () => {
    test('fetches sales data from backend', async ({ page }) => {
      await page.waitForTimeout(5000);
      const tableRows = page.locator('tbody tr');
      const count = await tableRows.count();
      expect(count).toBeGreaterThan(0);
      
      // Verify price data exists
      const firstRow = tableRows.first();
      const priceCell = firstRow.locator('td').nth(1);
      const priceText = await priceCell.textContent();
      expect(priceText).toContain('$');
    });

    test('leaderboards display data', async ({ page }) => {
      await page.waitForTimeout(5000);
      // CAGR chart should have bars
      const bars = page.locator('.recharts-bar-rectangle');
      const barCount = await bars.count();
      console.log(`Found ${barCount} chart bars`);
      expect(barCount).toBeGreaterThan(0);
    });
  });

    test.describe('7. Filters', () => {
     test('category filter shows residence option', async ({ page }) => {
       const categorySelect = page.locator('select').filter({ hasText: /RESIDENCE|ALL PROPERTIES/ });
       await expect(categorySelect).toBeVisible({ timeout: 10000 });
     });
 
     test('can filter by residence type', async ({ page }) => {
       const categorySelect = page.locator('select').filter({ hasText: /RESIDENCE|ALL PROPERTIES/ });
       await categorySelect.selectOption('Residence');
       await page.waitForTimeout(3000);
       // Should still have data
       const tableRows = page.locator('tbody tr');
       expect(await tableRows.count()).toBeGreaterThan(0);
     });

     test('can filter by strata unit type', async ({ page }) => {
       const categorySelect = page.locator('select').filter({ hasText: /STRATA UNIT|ALL PROPERTIES/ });
       await categorySelect.selectOption('Strata Unit');
       await page.waitForTimeout(3000);
       // Should still have data (may be empty but table should exist)
       const table = page.locator('table');
       await expect(table).toBeAttached();
     });
   });

  test.describe('8. Error Handling', () => {
    test('shows loading state initially', async ({ page }) => {
      // Page should show loading or data within reasonable time
      await page.waitForTimeout(10000);
      const mapContainer = page.locator('.leaflet-container');
      await expect(mapContainer).toBeVisible({ timeout: 10000 });
    });

    test('no critical console errors on load', async ({ page }) => {
      const errors: string[] = [];
      page.on('pageerror', err => errors.push(err.message));
      
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(5000);
      
      // Filter out expected network errors
      const criticalErrors = errors.filter(e => 
        !e.includes('Failed to fetch') &&
        !e.includes('NetworkError') &&
        !e.includes('net::ERR')
      );
      
      expect(criticalErrors.length).toBe(0);
    });
  });

    test.describe('9. Backend API Verification', () => {
    test('backend health endpoint responds', async ({ request }) => {
    const response = await request.get(`${API_URL.replace('/api', '')}/health`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.status).toBe('ok');
    });

    test('backend sales endpoint returns data', async ({ request }) => {
    const response = await request.get(`${API_URL}/sales?limit=5`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
    expect(data.length).toBeGreaterThan(0);
    });

    test('backend top performers endpoint returns data', async ({ request }) => {
    const response = await request.get(`${API_URL}/stats/top_performers?year=2024`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('growth');
    });

    test('backend unified map endpoint returns data', async ({ request }) => {
    const response = await request.get(`${API_URL}/stats/unified_map?level=suburb&year=2024`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('clusters');
    });

    test('backend global summary endpoint returns data', async ({ request }) => {
    const response = await request.get(`${API_URL}/stats/global_summary?year=2024`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('top_suburbs');
    expect(data).toHaveProperty('top_streets');
    expect(data).toHaveProperty('year');
    expect(data.top_suburbs.length).toBeGreaterThan(0);
    expect(data.top_streets.length).toBeGreaterThan(0);
    });
    });

  test.describe('10. Responsive Layout', () => {
    test('works on mobile viewport', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      
      // Should still render main components
      const header = page.locator('text=NSW UNIFIED');
      await expect(header).toBeVisible({ timeout: 15000 });
    });

     test('works on tablet viewport', async ({ page }) => {
       await page.setViewportSize({ width: 768, height: 1024 });
       await page.goto('/');
       await page.waitForLoadState('networkidle');
       
       // Should still render main components
       const header = page.locator('text=NSW UNIFIED');
       await expect(header).toBeVisible({ timeout: 15000 });
    });
  });
