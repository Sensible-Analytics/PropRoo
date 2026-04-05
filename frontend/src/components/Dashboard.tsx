import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Home, Loader, ArrowLeft, ChevronRight, Calendar, Layers } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import DualRangeSlider from './DualRangeSlider';
import { latLngToCell, cellToLatLng } from 'h3-js';

// deck.gl + MapLibre imports
import DeckGL from '@deck.gl/react';
import { Map } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { H3HexagonLayer } from '@deck.gl/geo-layers';
import { HeatmapLayer, ContourLayer } from '@deck.gl/aggregation-layers';
import { ScatterplotLayer, TextLayer, GeoJsonLayer } from '@deck.gl/layers';
import { FlyToInterpolator } from '@deck.gl/core';

// GeoJSON data
import nswSuburbsRaw from '../data/nsw_suburbs.geojson?raw';
const nswSuburbsGeoJSON = JSON.parse(nswSuburbsRaw);

// Australian state boundaries GeoJSON (simplified polygons)
const australiaStatesGeoJSON = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { name: 'New South Wales', abbr: 'NSW' },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [140.9993, -37.5000], [140.9993, -28.1500], [141.0000, -28.1500],
          [149.9993, -28.1500], [153.6393, -28.1500], [153.6393, -37.5000],
          [150.0000, -37.5000], [140.9993, -37.5000]
        ]]
      }
    },
    {
      type: 'Feature',
      properties: { name: 'Victoria', abbr: 'VIC' },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [140.9993, -39.1500], [140.9993, -37.5000], [150.0000, -37.5000],
          [150.0000, -39.1500], [140.9993, -39.1500]
        ]]
      }
    },
    {
      type: 'Feature',
      properties: { name: 'Queensland', abbr: 'QLD' },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [137.9993, -28.1500], [137.9993, -10.7000], [153.6393, -10.7000],
          [153.6393, -28.1500], [149.9993, -28.1500], [141.0000, -28.1500],
          [137.9993, -28.1500]
        ]]
      }
    },
    {
      type: 'Feature',
      properties: { name: 'South Australia', abbr: 'SA' },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [129.0000, -38.0000], [129.0000, -26.0000], [140.9993, -26.0000],
          [140.9993, -38.0000], [129.0000, -38.0000]
        ]]
      }
    },
    {
      type: 'Feature',
      properties: { name: 'Western Australia', abbr: 'WA' },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [112.9000, -35.0000], [112.9000, -13.7000], [129.0000, -13.7000],
          [129.0000, -35.0000], [112.9000, -35.0000]
        ]]
      }
    },
    {
      type: 'Feature',
      properties: { name: 'Tasmania', abbr: 'TAS' },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [143.8000, -43.6000], [143.8000, -40.7000], [148.5000, -40.7000],
          [148.5000, -43.6000], [143.8000, -43.6000]
        ]]
      }
    },
    {
      type: 'Feature',
      properties: { name: 'Northern Territory', abbr: 'NT' },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [129.0000, -26.0000], [129.0000, -10.7000], [137.9993, -10.7000],
          [137.9993, -26.0000], [129.0000, -26.0000]
        ]]
      }
    },
    {
      type: 'Feature',
      properties: { name: 'Australian Capital Territory', abbr: 'ACT' },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [148.7000, -35.9000], [148.7000, -35.1000], [149.4000, -35.1000],
          [149.4000, -35.9000], [148.7000, -35.9000]
        ]]
      }
    }
  ]
};

// DuckDB + Cache services
import { initDuckDB, query, isInitialized } from '../services/duckdb';
import { get as cacheGet, set as cacheSet } from '../services/cache';

// Types
interface SaleRecord {
  id: number;
  property_id: string;
  property_locality: string;
  property_street_name: string;
  property_house_number?: string;
  property_name?: string;
  purchase_price: number;
  contract_date: Date | string;
  primary_purpose: string;
  latitude: number;
  longitude: number;
  area?: string;
  zoning?: string;
  cagr?: number;
}

interface SuburbSummary {
  suburb: string;
  avg_cagr: number;
  unique_properties: number;
  total_sales: number;
  latitude: number;
  longitude: number;
}

interface StreetSummary {
  street_name: string;
  suburb: string;
  avg_cagr: number;
  unique_properties: number;
  total_sales: number;
  latitude: number;
  longitude: number;
}

interface H3Cell {
  h3_index: string;
  lat: number;
  lng: number;
  median_price: number;
  sale_count: number;
  avg_cagr: number;
}

// Constants
const CARTO_BASEMAP = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';
const INITIAL_VIEW_STATE = {
  longitude: 151.2093,
  latitude: -33.8688,
  zoom: 10,
  pitch: 45,
  bearing: 0,
};

const CLUSTER_COLORS = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#64748b'
];

const availableYears = Array.from({ length: 24 }, (_, i) => 2024 - i);

// CAGR color scale: red (negative) → gray (neutral) → green (positive)
function cagrToColor(cagr: number): [number, number, number, number] {
  const val = Math.max(-0.1, Math.min(0.2, cagr));
  if (val < 0) {
    const t = Math.min(1, Math.abs(val) / 0.1);
    return [220, Math.round(50 + t * 30), 50, 200];
  }
  if (val < 0.05) {
    const t = val / 0.05;
    return [Math.round(140 + t * 60), Math.round(140 + t * 20), Math.round(140 - t * 80), 200];
  }
  const t = Math.min(1, (val - 0.05) / 0.15);
  return [Math.round(50 - t * 30), Math.round(180 + t * 40), Math.round(60 + t * 20), 220];
}

// Price to elevation scale
function priceToElevation(price: number, maxPrice: number): number {
  return (price / maxPrice) * 5000;
}

// Get H3 resolution based on zoom level
function getH3Resolution(zoom: number): number {
  if (zoom >= 12 && zoom <= 14) return 9;
  if (zoom >= 9 && zoom <= 11) return 7;
  return 5;
}

// Format price for display
function formatPrice(price: number): string {
  if (price >= 1000000) return `$${(price / 1000000).toFixed(1)}M`;
  if (price >= 1000) return `$${(price / 1000).toFixed(0)}K`;
  return `$${price}`;
}

function formatDate(date: Date | string): string {
  if (date instanceof Date) return date.toISOString().split('T')[0];
  return String(date);
}

// Cached query helper
async function cachedQuery<T>(sql: string): Promise<T[]> {
  // Try cache first
  const cached = await cacheGet<T[]>(sql);
  if (cached) return cached;

  // Run query
  const result = await query<T>(sql);

  // Cache result
  await cacheSet(sql, result);

  return result;
}

// Error Boundary class for catching WebGL errors in deck.gl
class ErrorBoundary extends React.Component<{ children: React.ReactNode; fallback: React.ReactNode }, { hasError: boolean }> {
  constructor(props: { children: React.ReactNode; fallback: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch(error: Error) {
    console.warn('ErrorBoundary caught:', error.message);
  }
  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

export default function Dashboard() {
  // Navigation State
  const [viewLevel, setViewLevel] = useState('state');
  const [selection, setSelection] = useState({ suburb: null as string | null, street: null as string | null, propertyId: null as string | null });

  // Data State
  const [sales, setSales] = useState<SaleRecord[]>([]);
  const [suburbLeaderboard, setSuburbLeaderboard] = useState<SuburbSummary[]>([]);
  const [streetLeaderboard, setStreetLeaderboard] = useState<StreetSummary[]>([]);
  const [h3Cells, setH3Cells] = useState<H3Cell[]>([]);
  const [heatmapData, setHeatmapData] = useState<SaleRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [initError, setInitError] = useState<string | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<Record<string, number>>({});
  const [isInitialized, setIsInitialized] = useState(false);
  const [webglError, setWebglError] = useState<string | null>(null);

  // Filters
  const [selectedYear, setSelectedYear] = useState(2024);
  const [propertyType, setPropertyType] = useState('');
  const [priceRange, setPriceRange] = useState({ min: 0, max: 10000000 });

  // Map State
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);
  const [mapZoom, setMapZoom] = useState(10);

  // Layer Toggles
  const [showH3, setShowH3] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [showContours, setShowContours] = useState(false);
  const [showPins, setShowPins] = useState(false);

  // Selected property for popup
  const [selectedProperty, setSelectedProperty] = useState<SaleRecord | null>(null);

  // Initialize DuckDB on mount
  useEffect(() => {
    let cancelled = false;

    // Suppress WebGL ResizeObserver errors in headless/test environments
    const originalErrorHandler = window.onerror;
    window.onerror = (message, source, lineno, colno, error) => {
      if (typeof message === 'string' && (message.includes('maxTextureDimension2D') || message.includes('luma'))) {
        return true; // Suppress
      }
      if (originalErrorHandler) {
        return originalErrorHandler.call(window, message, source, lineno, colno, error);
      }
      return false;
    };

    async function init() {
      try {
        await initDuckDB((file, pct) => {
          if (!cancelled) {
            setDownloadProgress(prev => ({ ...prev, [file]: pct }));
          }
        });
        if (!cancelled) {
          setIsInitialized(true);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('DuckDB init failed:', err);
          setInitError(err instanceof Error ? err.message : 'Failed to initialize DuckDB');
        }
      }
    }

    init();
    return () => {
      cancelled = true;
      window.onerror = originalErrorHandler;
    };
  }, []);

  // Fetch data when filters change
  useEffect(() => {
    if (!isInitialized) return;

    let cancelled = false;
    setLoading(true);

    async function fetchData() {
      try {
        // 1. Fetch suburb leaderboard
        try {
          const sql = `SELECT suburb, avg_cagr, unique_properties, total_sales, latitude, longitude
                       FROM suburb_summary
                       ORDER BY avg_cagr DESC LIMIT 10`;
          const suburbs = await cachedQuery<SuburbSummary>(sql);
          if (!cancelled) setSuburbLeaderboard(suburbs);
        } catch (e) {
          console.warn('Suburb leaderboard fetch failed:', e);
          if (!cancelled) setSuburbLeaderboard([]);
        }

        // 2. Fetch street leaderboard
        try {
          const sql = `SELECT street_name, suburb, avg_cagr, unique_properties, total_sales, latitude, longitude
                       FROM street_summary
                       ORDER BY avg_cagr DESC LIMIT 10`;
          const streets = await cachedQuery<StreetSummary>(sql);
          if (!cancelled) setStreetLeaderboard(streets);
        } catch (e) {
          console.warn('Street leaderboard fetch failed:', e);
          if (!cancelled) setStreetLeaderboard([]);
        }

        // 3. Fetch coordinates for H3 cells, compute H3 client-side
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
          if (!cancelled) setH3Cells(cells);
        } catch (e) {
          console.warn('H3 cells fetch failed:', e);
          if (!cancelled) setH3Cells([]);
        }

        // 4. Fetch heatmap data
        try {
          const sql = `SELECT * FROM sales WHERE strftime(contract_date, '%Y') = '${selectedYear}' LIMIT 50000`;
          const data = await cachedQuery<SaleRecord>(sql);
          if (!cancelled) setHeatmapData(data);
        } catch (e) {
          console.warn('Heatmap data fetch failed:', e);
          if (!cancelled) setHeatmapData([]);
        }

        // 5. Fetch sales for table
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
          if (!cancelled) setSales(data);
        } catch (e) {
          console.warn('Sales fetch failed:', e);
          if (!cancelled) setSales([]);
        }
      } catch (error) {
        console.error('Fetch failed:', error);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchData();
    return () => { cancelled = true; };
  }, [isInitialized, viewLevel, selection, selectedYear, propertyType, priceRange, mapZoom]);

  // Navigation handlers
  const handleBack = useCallback(() => {
    if (viewLevel === 'property') {
      setViewLevel('street');
      setSelection(prev => ({ ...prev, propertyId: null }));
    } else if (viewLevel === 'street') {
      setViewLevel('suburb');
      setSelection(prev => ({ ...prev, street: null }));
    } else if (viewLevel === 'suburb') {
      setViewLevel('state');
      setSelection({ suburb: null, street: null, propertyId: null });
    }
  }, [viewLevel]);

  const navigateToState = useCallback(() => {
    setViewLevel('state');
    setSelection({ suburb: null, street: null, propertyId: null });
  }, []);

  const navigateToSuburb = useCallback(() => {
    setViewLevel('suburb');
    setSelection(prev => ({ ...prev, street: null, propertyId: null }));
  }, []);

  const drillDown = useCallback((type: string, value: string) => {
    if (type === 'suburb') {
      setSelection({ suburb: value, street: null, propertyId: null });
      setViewLevel('suburb');
      // Fly to suburb
      const suburb = suburbLeaderboard.find(s => s.suburb === value);
      if (suburb) {
        setViewState(prev => ({
          ...prev,
          longitude: suburb.longitude,
          latitude: suburb.latitude,
          zoom: 12,
          pitch: 45,
          transitionDuration: 1500,
          transitionInterpolator: new FlyToInterpolator(),
        }));
      }
    } else if (type === 'street') {
      setSelection(prev => ({ ...prev, street: value, propertyId: null }));
      setViewLevel('street');
      const street = streetLeaderboard.find(s => s.street_name === value);
      if (street) {
        setViewState(prev => ({
          ...prev,
          longitude: street.longitude,
          latitude: street.latitude,
          zoom: 14,
          pitch: 45,
          transitionDuration: 1500,
          transitionInterpolator: new FlyToInterpolator(),
        }));
      }
    } else if (type === 'property') {
      setSelection(prev => ({ ...prev, propertyId: value }));
      setViewLevel('property');
    }
  }, [suburbLeaderboard, streetLeaderboard]);

  const handleMapClick = useCallback((info: any) => {
    if (info.object) {
      const { object } = info;
      if (object.properties) {
        // H3 cell clicked - drill down
        setViewState(prev => ({
          ...prev,
          longitude: object.geometry.coordinates[0][0][0],
          latitude: object.geometry.coordinates[0][0][1],
          zoom: Math.min(prev.zoom + 2, 15),
          pitch: 45,
          transitionDuration: 1500,
          transitionInterpolator: new FlyToInterpolator(),
        }));
      }
    }
  }, []);

  // Computed data for charts
  const cagrData = useMemo(() => {
    const data = viewLevel === 'state' ? suburbLeaderboard : streetLeaderboard;
    return data.slice(0, 5).map(item => ({
      name: (item.suburb || item.street_name || '').split(' ')[0],
      value: parseFloat(((item.avg_cagr || 0) * 100).toFixed(1)),
      fullName: item.suburb || item.street_name,
    }));
  }, [suburbLeaderboard, streetLeaderboard, viewLevel]);

  const activityData = useMemo(() => {
    const data = viewLevel === 'state' ? suburbLeaderboard : streetLeaderboard;
    return data.slice(0, 5).map(item => ({
      name: (item.suburb || item.street_name || '').split(' ')[0],
      value: item.total_sales || item.unique_properties || 0,
      fullName: item.suburb || item.street_name,
    }));
  }, [suburbLeaderboard, streetLeaderboard, viewLevel]);

  // deck.gl layers
  const layers = useMemo(() => {
    const result: any[] = [];

    // State boundaries layer (visible at zoom 4-8)
    if (mapZoom >= 4 && mapZoom <= 8) {
      result.push(
        new GeoJsonLayer({
          id: 'state-boundaries',
          data: australiaStatesGeoJSON as any,
          stroked: true,
          filled: true,
          getFillColor: [30, 41, 59, 80],
          getLineColor: [100, 140, 255, 200],
          lineWidthMinPixels: 2,
          pickable: true,
          autoHighlight: true,
          highlightColor: [100, 140, 255, 40],
          getTooltip: (d: any) => d.properties && {
            html: `<div style="padding: 8px; font-family: sans-serif; font-size: 12px;">
              <div style="font-weight: bold;">${d.properties.name} (${d.properties.abbr})</div>
            </div>`,
          },
        })
      );
    }

    // H3 Hexagon Layer
    if (showH3 && h3Cells.length > 0) {
      const maxPrice = Math.max(...h3Cells.map(c => c.median_price || 0), 1);
      result.push(
        new H3HexagonLayer({
          id: 'h3-hexagons',
          data: h3Cells,
          extruded: true,
          getHexagon: (d: H3Cell) => d.h3_index,
          getElevation: (d: H3Cell) => priceToElevation(d.median_price || 0, maxPrice),
          getFillColor: (d: H3Cell) => cagrToColor(d.avg_cagr || 0),
          getLineColor: [255, 255, 255, 40],
          lineWidthMinPixels: 0.5,
          elevationScale: 100,
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 80],
          transitions: { getFillColor: 600, getElevation: 600 },
          getTooltip: (d: { object: H3Cell }) => d.object && {
            html: `
              <div style="padding: 8px; font-family: sans-serif; font-size: 12px;">
                <div style="font-weight: bold; margin-bottom: 4px;">H3 Cell</div>
                <div>Median Price: ${formatPrice(d.object.median_price || 0)}</div>
                <div>Sales: ${d.object.sale_count}</div>
                <div>Avg CAGR: ${((d.object.avg_cagr || 0) * 100).toFixed(1)}%</div>
              </div>
            `,
          },
        })
      );
    }

    // Heatmap Layer
    if (showHeatmap && heatmapData.length > 0) {
      result.push(
        new HeatmapLayer({
          id: 'heatmap',
          data: heatmapData.filter(d => d.latitude && d.longitude),
          getPosition: (d: SaleRecord) => [d.longitude, d.latitude],
          getWeight: (d: SaleRecord) => d.purchase_price / 1000000,
          radiusPixels: 50,
          intensity: 1.5,
          threshold: 0.1,
          opacity: 0.8,
        })
      );
    }

    // Contour Layer
    if (showContours && heatmapData.length > 0) {
      result.push(
        new ContourLayer({
          id: 'contours',
          data: heatmapData.filter(d => d.latitude && d.longitude),
          getPosition: (d: SaleRecord) => [d.longitude, d.latitude],
          getWeight: (d: SaleRecord) => d.purchase_price / 1000000,
          cellSize: 500,
          contourStrokeWidth: 2,
          contourColor: [100, 200, 255, 180],
          opacity: 0.6,
        })
      );
    }

    // Property Pins (Scatterplot) at zoom 15+
    if (showPins && viewState.zoom >= 15 && sales.length > 0) {
      const maxPrice = Math.max(...sales.map(s => s.purchase_price || 0), 1);
      result.push(
        new ScatterplotLayer({
          id: 'property-pins',
          data: sales.filter(d => d.latitude && d.longitude),
          getPosition: (d: SaleRecord) => [d.longitude, d.latitude],
          getRadius: (d: SaleRecord) => Math.max(5, (d.purchase_price / maxPrice) * 50),
          getFillColor: (d: SaleRecord) => cagrToColor(d.cagr || 0),
          getLineColor: [255, 255, 255, 100],
          lineWidthMinPixels: 1,
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 80],
          transitions: { getFillColor: 600, getRadius: 600 },
          onClick: (info: any) => {
            if (info.object) {
              setSelectedProperty(info.object);
            }
          },
          getTooltip: (d: { object: SaleRecord }) => d.object && {
            html: `
              <div style="padding: 8px; font-family: sans-serif; font-size: 12px;">
                <div style="font-weight: bold; margin-bottom: 4px;">${d.object.property_house_number || ''} ${d.object.property_street_name || ''}</div>
                <div>${d.object.property_locality}</div>
                <div>Price: ${formatPrice(d.object.purchase_price || 0)}</div>
                <div>Date: ${d.object.contract_date instanceof Date ? d.object.contract_date.toISOString().split('T')[0] : d.object.contract_date}</div>
              </div>
            `,
          },
        })
      );
    }

    // Price labels on pins at zoom >= 14
    if (showPins && viewState.zoom >= 14 && sales.length > 0) {
      const maxPrice = Math.max(...sales.map(s => s.purchase_price || 0), 1);
      result.push(
        new TextLayer({
          id: 'price-labels',
          data: sales.filter(d => d.latitude && d.longitude),
          getPosition: (d: SaleRecord) => [d.longitude, d.latitude],
          getText: (d: SaleRecord) => formatPrice(d.purchase_price || 0),
          getSize: 12,
          getColor: [255, 255, 255, 220],
          getPixelOffset: [0, -15],
          fontFamily: 'Inter, system-ui, sans-serif',
          fontWeight: 700,
          outlineWidth: 2,
          outlineColor: [0, 0, 0, 255],
        })
      );
    }

    // Suburb boundary layer (visible at zoom 8-13)
    if (mapZoom >= 8 && mapZoom < 13) {
      result.push(
        new GeoJsonLayer({
          id: 'suburb-boundaries',
          data: nswSuburbsGeoJSON as any,
          stroked: true,
          filled: false,
          lineWidthMinPixels: 1.5,
          getLineColor: [100, 140, 255, 180],
          pickable: true,
          autoHighlight: true,
          highlightColor: [100, 140, 255, 80],
          getTooltip: (d: any) => d.properties && {
            html: `<div style="padding: 8px; font-family: sans-serif; font-size: 12px;">
              <div style="font-weight: bold;">${d.properties.suburb_name}</div>
              <div>Postcode: ${d.properties.postcode}</div>
            </div>`,
          },
        })
      );
    }

    // Suburb labels (visible at zoom 6-14)
    if (mapZoom >= 6 && mapZoom < 14) {
      const labelData = (nswSuburbsGeoJSON as any).features.map((f: any) => ({
        name: f.properties.suburb_name,
        position: f.geometry.coordinates[0].reduce(
          (acc: number[], coord: number[]) => [acc[0] + coord[0], acc[1] + coord[1]],
          [0, 0]
        ).map((v: number, _i: number, arr: number[]) => v / (arr.length / 2)),
      }));
      result.push(
        new TextLayer({
          id: 'suburb-labels',
          data: labelData,
          getPosition: (d: any) => d.position,
          getText: (d: any) => d.name,
          getSize: 14,
          getColor: [200, 220, 255, 220],
          getPixelOffset: [0, -10],
          fontFamily: 'Inter, system-ui, sans-serif',
          fontWeight: 600,
          outlineWidth: 2,
          outlineColor: [0, 0, 0, 255],
        })
      );
    }

    return result;
  }, [showH3, showHeatmap, showContours, showPins, h3Cells, heatmapData, sales, viewState.zoom, mapZoom]);

  // Loading overlay
  if (initError) {
    return (
      <div className="h-screen w-screen flex flex-col bg-slate-950 text-slate-100 overflow-hidden font-sans items-center justify-center">
        <div className="text-center">
          <div className="text-red-400 text-2xl font-black mb-4">INITIALIZATION FAILED</div>
          <p className="text-slate-400 mb-6">{initError}</p>
          <button
            onClick={() => window.location.reload()}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl font-bold transition-colors"
          >
            RETRY
          </button>
        </div>
      </div>
    );
  }

  if (!isInitialized) {
    const totalProgress = Object.values(downloadProgress).reduce((a, b) => a + b, 0) / (Object.keys(downloadProgress).length || 1);
    return (
      <div className="h-screen w-screen flex flex-col bg-slate-950 text-slate-100 overflow-hidden font-sans items-center justify-center">
        <div className="flex flex-col items-center gap-8">
          <div className="relative">
            <div className="h-20 w-20 border-4 border-blue-500/10 border-t-blue-500 rounded-full animate-spin"></div>
            <div className="absolute inset-0 flex items-center justify-center">
              <Loader className="text-blue-500 animate-pulse" size={24} />
            </div>
          </div>
          <div className="text-center">
            <p className="text-blue-400 font-black uppercase tracking-[0.5em] text-[10px] animate-pulse mb-4">
              Loading PropRoo Engine...
            </p>
            {Object.keys(downloadProgress).length > 0 && (
              <div className="space-y-2">
                {Object.entries(downloadProgress).map(([file, pct]) => (
                  <div key={file} className="flex items-center gap-3 text-xs">
                    <span className="text-slate-400 w-32 text-right">{file}.parquet</span>
                    <div className="w-48 h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 transition-all duration-300"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-slate-500 w-12">{pct}%</span>
                  </div>
                ))}
              </div>
            )}
            <p className="text-slate-600 text-[10px] mt-4">
              Total: {Math.round(totalProgress)}%
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Header: h-14 */}
      <header className="h-14 shrink-0 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md px-4 flex justify-between items-center z-50">
        {/* Left: breadcrumb + back button */}
        <div className="flex items-center gap-4">
          {viewLevel !== 'state' && (
            <button onClick={handleBack} className="p-2 hover:bg-slate-800 rounded-full transition-all border border-slate-700 bg-slate-900 shadow-lg group">
              <ArrowLeft size={16} className="group-hover:-translate-x-1 transition-transform" />
            </button>
          )}
          <div className="flex items-center gap-2">
            <button
              onClick={navigateToState}
              className={`text-[10px] font-bold uppercase tracking-[0.2em] transition-colors ${viewLevel === 'state' ? 'text-blue-400' : 'text-slate-400 hover:text-blue-300'}`}
            >
              NSW
            </button>
            {viewLevel !== 'state' && (
              <>
                <ChevronRight size={10} className="text-slate-600" />
                <button
                  onClick={navigateToSuburb}
                  className={`text-[10px] font-bold uppercase tracking-[0.2em] transition-colors ${viewLevel === 'suburb' ? 'text-blue-400' : 'text-slate-400 hover:text-blue-300'}`}
                >
                  {selection.suburb}
                </button>
              </>
            )}
            {viewLevel === 'street' && (
              <>
                <ChevronRight size={10} className="text-slate-600" />
                <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-blue-400">
                  {selection.street}
                </span>
              </>
            )}
          </div>
        </div>

        {/* Right: filters (price, category) */}
        <div className="flex items-center gap-4">
          <div className="w-48 flex flex-col gap-0.5">
            <label className="text-[9px] font-bold text-slate-500 uppercase tracking-widest pl-1">PRICE RANGE</label>
            <DualRangeSlider min={0} max={10000000} onChange={setPriceRange} />
          </div>
          <div className="flex flex-col gap-0.5">
            <label className="text-[9px] font-bold text-slate-500 uppercase tracking-widest pl-1">CATEGORY</label>
            <div className="bg-slate-800 px-3 py-1.5 rounded-xl border border-slate-700">
              <select value={propertyType} onChange={e => setPropertyType(e.target.value)} className="bg-transparent text-xs font-bold focus:outline-none cursor-pointer">
                <option value="">ALL PROPERTIES</option>
                <option value="Residence">RESIDENCE</option>
                <option value="Strata Unit">STRATA UNIT</option>
              </select>
            </div>
          </div>
        </div>
      </header>

      {/* Main workspace: flex-1, horizontal split 80/20 */}
      <div className="flex-1 flex min-h-0">
        {/* Map Area: flex-1 (80%) */}
        <div className="flex-1 relative bg-slate-900">
          {/* Layer Toggles */}
          <div className="absolute top-4 left-4 z-[1000] flex flex-col gap-2">
            <div className="bg-slate-950/90 px-3 py-1.5 rounded-xl border border-slate-800 text-[10px] font-bold tracking-widest text-slate-300 backdrop-blur-sm flex items-center gap-2">
              <Layers size={12} className="text-blue-500" /> LAYERS
            </div>
            <div className="bg-slate-950/90 px-3 py-2 rounded-xl border border-slate-800 backdrop-blur-sm space-y-1.5">
              <label className="flex items-center gap-2 text-[10px] font-bold text-slate-300 cursor-pointer">
                <input type="checkbox" checked={showH3} onChange={e => setShowH3(e.target.checked)} className="accent-blue-500" />
                H3 HEXAGONS
              </label>
              <label className="flex items-center gap-2 text-[10px] font-bold text-slate-300 cursor-pointer">
                <input type="checkbox" checked={showHeatmap} onChange={e => setShowHeatmap(e.target.checked)} className="accent-blue-500" />
                HEATMAP
              </label>
              <label className="flex items-center gap-2 text-[10px] font-bold text-slate-300 cursor-pointer">
                <input type="checkbox" checked={showContours} onChange={e => setShowContours(e.target.checked)} className="accent-blue-500" />
                CONTOURS
              </label>
              <label className="flex items-center gap-2 text-[10px] font-bold text-slate-300 cursor-pointer">
                <input type="checkbox" checked={showPins} onChange={e => setShowPins(e.target.checked)} className="accent-blue-500" />
                PROPERTY PINS
              </label>
            </div>
          </div>

          {/* Year Display */}
          <div className="absolute top-4 right-4 z-[1000] bg-slate-950/90 px-4 py-2 rounded-xl border border-slate-800 backdrop-blur-sm">
            <span className="text-2xl font-black text-blue-400">{selectedYear}</span>
          </div>

          {/* Time Slider */}
          <div className="absolute bottom-4 left-4 right-4 z-[1000] bg-slate-950/90 px-4 py-3 rounded-xl border border-slate-800 backdrop-blur-sm">
            <div className="flex items-center gap-4">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">2001</span>
              <input
                type="range"
                min={2001}
                max={2024}
                value={selectedYear}
                onChange={e => setSelectedYear(parseInt(e.target.value))}
                className="flex-1 h-2 bg-slate-800 rounded-full appearance-none cursor-pointer accent-blue-500"
              />
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">2024</span>
            </div>
          </div>

          {/* Data Attribution Overlay */}
          <div className="absolute bottom-20 right-4 z-[1000] bg-slate-950/80 px-3 py-2 rounded-lg text-[9px] text-slate-400 backdrop-blur-sm border border-slate-800/50">
            <div className="font-bold text-slate-300 mb-1">Data Sources</div>
            <div className="flex items-center gap-1">
              <span>NSW Valuer General</span>
              <span className="text-slate-600">·</span>
              <span>2001-2024</span>
              <a href="https://www.valuergeneral.nsw.gov.au" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline ml-1">↗</a>
            </div>
          </div>

          {/* DeckGL Map */}
          <ErrorBoundary fallback={<div className="absolute inset-0 flex items-center justify-center bg-slate-900 text-slate-400 text-sm">Map rendering unavailable</div>}>
            <DeckGL
              viewState={viewState}
              onViewStateChange={({ viewState: vs }) => {
                setViewState(vs);
                setMapZoom(Math.round(vs.zoom));
              }}
              controller={true}
              layers={layers}
              onClick={handleMapClick}
              onError={(err: Error) => {
                console.warn('DeckGL error:', err.message);
                setWebglError(err.message);
              }}
              width="100%"
              height="100%"
              useDevicePixelRatio={false}
              style={{ position: 'absolute', top: 0, left: 0 }}
            >
              <Map
                mapStyle={CARTO_BASEMAP}
                style={{ width: '100%', height: '100%' }}
              />
            </DeckGL>
          </ErrorBoundary>
        </div>

        {/* Sidebar: w-80 (20%), scrollable */}
        <aside className="w-80 border-l border-slate-800 bg-slate-900/50 flex flex-col overflow-y-auto">
          {/* CAGR Chart */}
          <div className="shrink-0 p-4 border-b border-slate-800">
            <h4 className="flex items-center gap-2 text-blue-400 text-[10px] font-black uppercase tracking-widest mb-4">
              <Home size={14} /> TOP CAGR
            </h4>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={cagrData} layout="vertical">
                  <XAxis type="number" hide />
                  <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 9, fontWeight: 'bold', fill: '#94a3b8' }} width={60} />
                  <Tooltip cursor={{ fill: '#ffffff05' }} contentStyle={{ backgroundColor: '#0f172a', border: 'none', borderRadius: '12px', fontSize: '10px' }} />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20} fill="#10b981" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Sales Table (scrollable within sidebar) */}
          <div className="flex-1 overflow-y-auto">
            <div className="px-4 py-3 border-b border-slate-800/40">
              <p className="text-[10px] font-black tracking-[0.4em] text-slate-500 uppercase">Spatial Entity Archive</p>
            </div>
            <table className="w-full text-left">
              <thead className="sticky top-0 bg-slate-900/95 backdrop-blur-md text-[9px] font-black uppercase tracking-[0.2em] text-slate-500 z-10 border-b border-slate-800/40">
                <tr>
                  <th className="px-4 py-3">Address</th>
                  <th className="px-4 py-3 text-center">Price</th>
                  <th className="px-4 py-3">CAGR</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/30">
                {sales.map(s => (
                  <tr
                    key={s.id}
                    onClick={() => drillDown(viewLevel === 'state' ? 'suburb' : 'street', viewLevel === 'state' ? s.property_locality : s.property_street_name)}
                    className="hover:bg-blue-600/5 group cursor-pointer transition-all"
                  >
                    <td className="px-4 py-3">
                      <p className="font-bold text-xs group-hover:text-blue-400 transition-colors uppercase tracking-tight">{viewLevel === 'state' ? s.property_locality : `${s.property_house_number} ${s.property_street_name}`}</p>
                      <p className="text-[9px] text-slate-600 font-black tracking-[0.1em] mt-0.5">{s.primary_purpose} &bull; {s.contract_date instanceof Date ? s.contract_date.toISOString().split('T')[0] : s.contract_date}</p>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <p className="font-mono text-sm font-black text-slate-200 tracking-tighter">${s.purchase_price?.toLocaleString()}</p>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-1 w-12 bg-slate-800 rounded-full overflow-hidden">
                          <div className="h-full bg-emerald-500" style={{ width: `${Math.max(5, Math.min(100, (s.cagr || 0) * 800))}%` }}></div>
                        </div>
                        <span className="font-black text-emerald-400 text-[10px]">{((s.cagr || 0) * 100).toFixed(1)}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={(e) => { e.stopPropagation(); drillDown('property', s.property_id); }}
                        className="bg-blue-600/10 hover:bg-blue-600 text-blue-400 hover:text-white px-3 py-1.5 rounded-lg text-[9px] font-black tracking-[0.2em] transition-all uppercase border border-blue-500/20"
                      >
                        EXPLORE
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </aside>
      </div>

      {/* Property Detail Popup */}
      {selectedProperty && (
        <div className="absolute top-16 right-84 z-[1000] w-80 bg-slate-900 rounded-xl border border-slate-700 shadow-2xl overflow-hidden">
          <div className="p-4">
            <div className="flex justify-between items-start mb-3">
              <div>
                <h3 className="font-bold text-sm text-white">
                  {selectedProperty.property_house_number} {selectedProperty.property_street_name}
                </h3>
                <p className="text-[10px] text-slate-400">{selectedProperty.property_locality}</p>
              </div>
              <button onClick={() => setSelectedProperty(null)} className="text-slate-500 hover:text-white">✕</button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs mb-4">
              <div>
                <span className="text-slate-500 text-[9px] uppercase tracking-wider">Price</span>
                <p className="font-mono font-bold text-white">${selectedProperty.purchase_price?.toLocaleString()}</p>
              </div>
              <div>
                <span className="text-slate-500 text-[9px] uppercase tracking-wider">Date</span>
                <p className="font-bold text-white">{formatDate(selectedProperty.contract_date)}</p>
              </div>
              <div>
                <span className="text-slate-500 text-[9px] uppercase tracking-wider">Type</span>
                <p className="font-bold text-white">{selectedProperty.primary_purpose}</p>
              </div>
              <div>
                <span className="text-slate-500 text-[9px] uppercase tracking-wider">Area</span>
                <p className="font-bold text-white">{selectedProperty.area || 'N/A'}</p>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-700 text-[9px] text-slate-500">
              <div>Source: NSW Valuer General</div>
              <a href="https://www.valuergeneral.nsw.gov.au" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
                View original record →
              </a>
            </div>
          </div>
        </div>
      )}


      {/* Loading Overlay */}
      {loading && (
        <div className="absolute inset-0 z-[10000] bg-slate-950/80 backdrop-blur-2xl flex items-center justify-center">
          <div className="flex flex-col items-center gap-8">
            <div className="relative">
              <div className="h-20 w-20 border-4 border-blue-500/10 border-t-blue-500 rounded-full animate-spin"></div>
              <div className="absolute inset-0 flex items-center justify-center">
                <Loader className="text-blue-500 animate-pulse" size={24} />
              </div>
            </div>
            <p className="text-blue-400 font-black uppercase tracking-[0.5em] text-[10px] animate-pulse">Orchestrating Unified Intelligence...</p>
          </div>
        </div>
      )}
    </div>
  );
}
