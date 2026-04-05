import { useEffect, useRef } from 'react';
import { latLngToCell, cellToLatLng } from 'h3-js';
import { query, isInitialized } from '../services/duckdb';
import { get as cacheGet, set as cacheSet } from '../services/cache';
import type { SaleRecord, SuburbSummary, StreetSummary, H3Cell } from '../store';

async function cachedQuery<T>(sql: string): Promise<T[]> {
  const cached = await cacheGet<T[]>(sql);
  if (cached) return cached;

  const result = await query<T>(sql);
  await cacheSet(sql, result);
  return result;
}

function getH3Resolution(zoom: number): number {
  if (zoom >= 12 && zoom <= 14) return 9;
  if (zoom >= 9 && zoom <= 11) return 7;
  return 5;
}

/**
 * Fetches suburb leaderboard once on initialization.
 * Dependencies: isInitialized only.
 */
export function useSuburbData(isInitialized: boolean) {
  const cancelledRef = useRef(false);

  useEffect(() => {
    if (!isInitialized) return;
    cancelledRef.current = false;

    async function fetchSuburbs() {
      try {
        const sql = `SELECT suburb, avg_cagr, unique_properties, total_sales, latitude, longitude
                     FROM suburb_summary
                     ORDER BY avg_cagr DESC LIMIT 10`;
        const suburbs = await cachedQuery<SuburbSummary>(sql);
        if (!cancelledRef.current) {
          // Import store setters
          const { useDataStore } = await import('../store');
          useDataStore.getState().setSuburbLeaderboard(suburbs);
        }
      } catch (e) {
        console.warn('Suburb leaderboard fetch failed:', e);
        if (!cancelledRef.current) {
          const { useDataStore } = await import('../store');
          useDataStore.getState().setSuburbLeaderboard([]);
        }
      }
    }

    fetchSuburbs();
    return () => { cancelledRef.current = true; };
  }, [isInitialized]);
}

/**
 * Fetches street leaderboard once on initialization.
 * Dependencies: isInitialized only.
 */
export function useStreetData(isInitialized: boolean) {
  const cancelledRef = useRef(false);

  useEffect(() => {
    if (!isInitialized) return;
    cancelledRef.current = false;

    async function fetchStreets() {
      try {
        const sql = `SELECT street_name, suburb, avg_cagr, unique_properties, total_sales, latitude, longitude
                     FROM street_summary
                     ORDER BY avg_cagr DESC LIMIT 10`;
        const streets = await cachedQuery<StreetSummary>(sql);
        if (!cancelledRef.current) {
          const { useDataStore } = await import('../store');
          useDataStore.getState().setStreetLeaderboard(streets);
        }
      } catch (e) {
        console.warn('Street leaderboard fetch failed:', e);
        if (!cancelledRef.current) {
          const { useDataStore } = await import('../store');
          useDataStore.getState().setStreetLeaderboard([]);
        }
      }
    }

    fetchStreets();
    return () => { cancelledRef.current = true; };
  }, [isInitialized]);
}

/**
 * Fetches H3 cells when map zoom or selected year changes.
 * Dependencies: isInitialized, mapZoom, selectedYear.
 */
export function useH3Data(isInitialized: boolean, mapZoom: number, selectedYear: number) {
  const cancelledRef = useRef(false);

  useEffect(() => {
    if (!isInitialized) return;
    cancelledRef.current = false;

    async function fetchH3() {
      try {
        const resolution = getH3Resolution(mapZoom);
        const sql = `
          SELECT 
            latitude, longitude, purchase_price
          FROM sales 
          WHERE strftime(contract_date, '%Y') = '${selectedYear}'
            AND latitude IS NOT NULL AND longitude IS NOT NULL
          LIMIT 100000
        `;
        const rows = await cachedQuery<{ latitude: number; longitude: number; purchase_price: number }>(sql);
        
        // Compute H3 cells client-side
        const cellMap = new Map<string, { prices: number[]; latSum: number; lngSum: number; count: number }>();
        for (const row of rows) {
          const h3Index = latLngToCell(row.latitude, row.longitude, resolution);
          const existing = cellMap.get(h3Index);
          if (existing) {
            existing.prices.push(row.purchase_price);
            existing.latSum += row.latitude;
            existing.lngSum += row.longitude;
            existing.count++;
          } else {
            cellMap.set(h3Index, { prices: [row.purchase_price], latSum: row.latitude, lngSum: row.longitude, count: 1 });
          }
        }
        
        const cells: H3Cell[] = [];
        for (const [h3Index, data] of cellMap) {
          const [lat, lng] = cellToLatLng(h3Index);
          const medianPrice = data.prices.sort((a, b) => a - b)[Math.floor(data.prices.length / 2)] || 0;
          cells.push({ h3_index: h3Index, lat, lng, median_price: medianPrice, sale_count: data.count, avg_cagr: 0 });
        }
        
        if (!cancelledRef.current) {
          const { useDataStore } = await import('../store');
          useDataStore.getState().setH3Cells(cells);
        }
      } catch (e) {
        console.warn('H3 cells fetch failed:', e);
        if (!cancelledRef.current) {
          const { useDataStore } = await import('../store');
          useDataStore.getState().setH3Cells([]);
        }
      }
    }

    fetchH3();
    return () => { cancelledRef.current = true; };
  }, [isInitialized, mapZoom, selectedYear]);
}

/**
 * Fetches heatmap data when selected year changes.
 * Dependencies: isInitialized, selectedYear.
 */
export function useHeatmapData(isInitialized: boolean, selectedYear: number) {
  const cancelledRef = useRef(false);

  useEffect(() => {
    if (!isInitialized) return;
    cancelledRef.current = false;

    async function fetchHeatmap() {
      try {
        const sql = `SELECT * FROM sales WHERE strftime(contract_date, '%Y') = '${selectedYear}' LIMIT 50000`;
        const data = await cachedQuery<SaleRecord>(sql);
        if (!cancelledRef.current) {
          const { useDataStore } = await import('../store');
          useDataStore.getState().setHeatmapData(data);
        }
      } catch (e) {
        console.warn('Heatmap data fetch failed:', e);
        if (!cancelledRef.current) {
          const { useDataStore } = await import('../store');
          useDataStore.getState().setHeatmapData([]);
        }
      }
    }

    fetchHeatmap();
    return () => { cancelledRef.current = true; };
  }, [isInitialized, selectedYear]);
}

/**
 * Fetches sales table data when filters or navigation changes.
 * Dependencies: isInitialized, viewLevel, selection, selectedYear, propertyType, priceRange.
 */
export function useSalesData(
  isInitialized: boolean,
  viewLevel: string,
  selection: { suburb: string | null; street: string | null; propertyId: string | null },
  selectedYear: number,
  propertyType: string,
  priceRange: { min: number; max: number }
) {
  const cancelledRef = useRef(false);

  useEffect(() => {
    if (!isInitialized) return;
    cancelledRef.current = false;

    async function fetchSales() {
      const { useDataStore } = await import('../store');
      useDataStore.getState().setLoading(true);

      try {
        let sql = `SELECT * FROM sales WHERE strftime(contract_date, '%Y') = '${selectedYear}'`;
        if (propertyType) {
          sql += ` AND primary_purpose = '${propertyType}'`;
        }
        if (priceRange.min > 0) {
          sql += ` AND purchase_price >= ${priceRange.min}`;
        }
        if (priceRange.max < 10000000) {
          sql += ` AND purchase_price <= ${priceRange.max}`;
        }

        if (viewLevel === 'suburb' && selection.suburb) {
          sql += ` AND property_locality = '${selection.suburb}'`;
        } else if (viewLevel === 'street' && selection.suburb && selection.street) {
          sql += ` AND property_locality = '${selection.suburb}' AND property_street_name = '${selection.street}'`;
        } else if (viewLevel === 'property' && selection.propertyId) {
          sql = `SELECT * FROM sales WHERE property_id = '${selection.propertyId}' ORDER BY contract_date`;
        }

        sql += ' LIMIT 100';
        const data = await cachedQuery<SaleRecord>(sql);
        if (!cancelledRef.current) {
          useDataStore.getState().setSales(data);
        }
      } catch (e) {
        console.warn('Sales fetch failed:', e);
        if (!cancelledRef.current) {
          useDataStore.getState().setSales([]);
        }
      } finally {
        if (!cancelledRef.current) {
          useDataStore.getState().setLoading(false);
        }
      }
    }

    fetchSales();
    return () => { cancelledRef.current = true; };
  }, [isInitialized, viewLevel, selection, selectedYear, propertyType, priceRange]);
}
