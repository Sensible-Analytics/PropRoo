import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Home, Loader, ArrowLeft, ChevronRight, Calendar, Layers, Tag, SlidersHorizontal, Building2, Hospital, ShoppingBag, GraduationCap, Train } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LabelList } from 'recharts';
import DualRangeSlider from './DualRangeSlider';
import { latLngToCell, cellToLatLng } from 'h3-js';

// deck.gl + MapLibre imports
import DeckGL from '@deck.gl/react';
import { Map } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { H3HexagonLayer } from '@deck.gl/geo-layers';
import { HeatmapLayer, ContourLayer } from '@deck.gl/aggregation-layers';
import { ScatterplotLayer, TextLayer, GeoJsonLayer, IconLayer } from '@deck.gl/layers';
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

interface POI {
  name: string;
  lat: number;
  lng: number;
  type: 'hospital' | 'mall' | 'school' | 'transit';
}

// Constants
const CARTO_BASEMAP = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';
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

// Sample POI data around Sydney
const samplePOIs: POI[] = [
  { name: 'Sydney Hospital', lat: -33.8688, lng: 151.2093, type: 'hospital' },
  { name: 'Westfield Sydney', lat: -33.8700, lng: 151.2100, type: 'mall' },
  { name: 'Sydney Grammar', lat: -33.8650, lng: 151.2050, type: 'school' },
  { name: 'Central Station', lat: -33.8835, lng: 151.2065, type: 'transit' },
  { name: 'St Vincent Hospital', lat: -33.8790, lng: 151.2210, type: 'hospital' },
  { name: 'Broadway Shopping Centre', lat: -33.8840, lng: 151.1930, type: 'mall' },
  { name: 'UTS', lat: -33.8830, lng: 151.2000, type: 'school' },
  { name: 'Town Hall Station', lat: -33.8730, lng: 151.2060, type: 'transit' },
  { name: 'Royal Prince Alfred', lat: -33.8890, lng: 151.1820, type: 'hospital' },
  { name: 'Queen Victoria Building', lat: -33.8720, lng: 151.2065, type: 'mall' },
  { name: 'Sydney Uni', lat: -33.8885, lng: 151.1873, type: 'school' },
  { name: 'Wynyard Station', lat: -33.8650, lng: 151.2050, type: 'transit' },
];

const poiColorMap: Record<string, [number, number, number, number]> = {
  hospital: [239, 68, 68, 220],
  mall: [245, 158, 11, 220],
  school: [59, 130, 246, 220],
  transit: [16, 185, 129, 220],
};

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
  const cached = await cacheGet<T[]>(sql);
  if (cached) return cached;
  const result = await query<T>(sql);
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
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [showContours, setShowContours] = useState(true);
  const [showPins, setShowPins] = useState(true);
  const [showStreets, setShowStreets] = useState(true);
  const [showSuburbs, setShowSuburbs] = useState(true);
  const [showPOI, setShowPOI] = useState(true);
  const [showChoropleth, setShowChoropleth] = useState(true);
  const [layersExpanded, setLayersExpanded] = useState(true);

  // Selected property for popup
  const [selectedProperty, setSelectedProperty] = useState<SaleRecord | null>(null);

  // Map-table sync
  const [selectedSuburb, setSelectedSuburb] = useState<string | null>(null);
  const [highlightedPropertyId, setHighlightedPropertyId] = useState<string | null>(null);

  // Table sorting
  const [tableSort, setTableSort] = useState<{ field: string; direction: 'asc' | 'desc' }>({ field: 'cagr', direction: 'desc' });

  // Initialize DuckDB on mount
  useEffect(() => {
    let cancelled = false;

    const originalErrorHandler = window.onerror;
    window.onerror = (message, source, lineno, colno, error) => {
      if (typeof message === 'string' && (message.includes('maxTextureDimension2D') || message.includes('luma'))) {
        return true;
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

          if (selectedSuburb) {
            sql += ` AND property_locality = '${selectedSuburb}'`;
          } else if (viewLevel === 'suburb' && selection.suburb) {
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
  }, [isInitialized, viewLevel, selection, selectedYear, propertyType, priceRange, mapZoom, selectedSuburb]);

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
      setSelectedSuburb(value);
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
        const suburbName = object.properties.suburb_name;
        if (suburbName) {
          setSelectedSuburb(suburbName);
        }
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

  const handleRowClick = useCallback((sale: SaleRecord) => {
    if (sale.latitude && sale.longitude) {
      setViewState(prev => ({
        ...prev,
        longitude: sale.longitude,
        latitude: sale.latitude,
        zoom: Math.max(prev.zoom, 14),
        pitch: 45,
        transitionDuration: 1000,
        transitionInterpolator: new FlyToInterpolator(),
      }));
      setHighlightedPropertyId(sale.property_id);
      setTimeout(() => setHighlightedPropertyId(null), 3000);
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

  const sortedSales = useMemo(() => {
    const sorted = [...sales].sort((a, b) => {
      const dir = tableSort.direction === 'asc' ? 1 : -1;
      if (tableSort.field === 'cagr') return ((a.cagr || 0) - (b.cagr || 0)) * dir;
      if (tableSort.field === 'price') return ((a.purchase_price || 0) - (b.purchase_price || 0)) * dir;
      if (tableSort.field === 'address') {
        const aAddr = viewLevel === 'state' ? (a.property_locality || '') : `${a.property_house_number} ${a.property_street_name}`;
        const bAddr = viewLevel === 'state' ? (b.property_locality || '') : `${b.property_house_number} ${b.property_street_name}`;
        return aAddr.localeCompare(bAddr) * dir;
      }
      return 0;
    });
    return sorted.map(s => ({
      ...s,
      houseCount: s.primary_purpose === 'Residence' ? 1 : 0,
      unitCount: s.primary_purpose === 'Strata Unit' ? 1 : 0,
      totalTransactions: 1,
    }));
  }, [sales, tableSort, viewLevel]);

  // deck.gl layers
  const layers = useMemo(() => {
    const result: any[] = [];

    // National boundary (zoom 1-4)
    if (mapZoom >= 1 && mapZoom <= 4) {
      result.push(
        new GeoJsonLayer({
          id: 'national-boundary',
          data: australiaStatesGeoJSON as any,
          stroked: true,
          filled: false,
          getLineColor: [100, 140, 255, 150],
          lineWidthMinPixels: 2,
          pickable: false,
        })
      );
    }

    // State boundaries layer (zoom 1-8)
    if (mapZoom >= 1 && mapZoom <= 8) {
      result.push(
        new GeoJsonLayer({
          id: 'state-boundaries',
          data: australiaStatesGeoJSON as any,
          stroked: true,
          filled: true,
          getFillColor: [241, 245, 249, 80],
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

    // Suburb/postcode boundaries (zoom 6-14)
    if (mapZoom >= 6 && mapZoom <= 14) {
      result.push(
        new GeoJsonLayer({
          id: 'postcode-boundaries',
          data: nswSuburbsGeoJSON as any,
          stroked: true,
          filled: false,
          getLineColor: [148, 163, 184, 150],
          lineWidthMinPixels: 1.5,
          pickable: false,
        })
      );
    }

    // Choropleth layer (zoom 8-13)
    if (showChoropleth && mapZoom >= 8 && mapZoom <= 13) {
      result.push(
        new GeoJsonLayer({
          id: 'suburb-choropleth',
          data: nswSuburbsGeoJSON as any,
          filled: true,
          stroked: true,
          lineWidthMinPixels: 1,
          getFillColor: (d: any) => {
            const suburb = suburbLeaderboard.find(s => s.suburb === d.properties?.suburb_name);
            return cagrToColor(suburb?.avg_cagr || 0);
          },
          getLineColor: [100, 100, 100, 100],
          opacity: 0.6,
          pickable: true,
          autoHighlight: true,
          highlightColor: [59, 130, 246, 80],
          onClick: (info: any) => {
            if (info.object?.properties?.suburb_name) {
              setSelectedSuburb(info.object.properties.suburb_name);
            }
          },
          getTooltip: (d: any) => {
            const suburb = suburbLeaderboard.find(s => s.suburb === d.properties?.suburb_name);
            return d.properties && {
              html: `<div style="padding: 8px; font-family: sans-serif; font-size: 12px;">
                <div style="font-weight: bold;">${d.properties.suburb_name}</div>
                <div>Postcode: ${d.properties.postcode}</div>
                ${suburb ? `<div>Avg CAGR: ${(suburb.avg_cagr * 100).toFixed(1)}%</div>` : ''}
              </div>`,
            };
          },
        })
      );
    }

    // Suburb boundaries (zoom 6-15)
    if (showSuburbs && mapZoom >= 6 && mapZoom < 15) {
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
          onClick: (info: any) => {
            if (info.object?.properties?.suburb_name) {
              setSelectedSuburb(info.object.properties.suburb_name);
            }
          },
          getTooltip: (d: any) => d.properties && {
            html: `<div style="padding: 8px; font-family: sans-serif; font-size: 12px;">
              <div style="font-weight: bold;">${d.properties.suburb_name}</div>
              <div>Postcode: ${d.properties.postcode}</div>
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
          getLineColor: [100, 116, 139, 60],
          lineWidthMinPixels: 0.5,
          elevationScale: 100,
          pickable: true,
          autoHighlight: true,
          highlightColor: [59, 130, 246, 80],
          transitions: { getFillColor: 600, getElevation: 600 },
          onClick: (info: any) => {
            if (info.object) {
              const { lat, lng } = info.object;
              setViewState(prev => ({
                ...prev,
                longitude: lng,
                latitude: lat,
                zoom: Math.min(prev.zoom + 2, 15),
                pitch: 45,
                transitionDuration: 1500,
                transitionInterpolator: new FlyToInterpolator(),
              }));
            }
          },
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
          contourColor: [59, 130, 246, 180],
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
          highlightColor: [59, 130, 246, 120],
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
      result.push(
        new TextLayer({
          id: 'price-labels',
          data: sales.filter(d => d.latitude && d.longitude),
          getPosition: (d: SaleRecord) => [d.longitude, d.latitude],
          getText: (d: SaleRecord) => formatPrice(d.purchase_price || 0),
          getSize: 12,
          getColor: [30, 41, 59, 220],
          getPixelOffset: [0, -15],
          fontFamily: 'Inter, system-ui, sans-serif',
          fontWeight: 700,
          outlineWidth: 2,
          outlineColor: [255, 255, 255, 200],
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
          getColor: [51, 65, 85, 220],
          getPixelOffset: [0, -10],
          fontFamily: 'Inter, system-ui, sans-serif',
          fontWeight: 600,
          outlineWidth: 2,
          outlineColor: [255, 255, 255, 200],
        })
      );
    }

    // POI Layer
    if (showPOI && mapZoom >= 8) {
      result.push(
        new ScatterplotLayer({
          id: 'poi-markers',
          data: samplePOIs,
          getPosition: (d: POI) => [d.lng, d.lat],
          getRadius: 12,
          getFillColor: (d: POI) => poiColorMap[d.type] || [100, 100, 100, 200],
          getLineColor: [255, 255, 255, 200],
          lineWidthMinPixels: 1.5,
          pickable: true,
          autoHighlight: true,
          highlightColor: [59, 130, 246, 120],
          getTooltip: (d: { object: POI }) => d.object && {
            html: `<div style="padding: 8px; font-family: sans-serif; font-size: 12px;">
              <div style="font-weight: bold;">${d.object.name}</div>
              <div style="text-transform: capitalize;">${d.object.type}</div>
            </div>`,
          },
        })
      );
    }

    return result;
  }, [showH3, showHeatmap, showContours, showPins, showSuburbs, showPOI, showChoropleth, h3Cells, heatmapData, sales, viewState.zoom, mapZoom, suburbLeaderboard]);

  // Loading overlay
  if (initError) {
    return (
      <div className="h-screen w-screen flex flex-col bg-slate-50 text-slate-900 overflow-hidden font-sans items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 text-2xl font-black mb-4">INITIALIZATION FAILED</div>
          <p className="text-slate-600 mb-6">{initError}</p>
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
      <div className="h-screen w-screen flex flex-col bg-slate-50 text-slate-900 overflow-hidden font-sans items-center justify-center">
        <div className="flex flex-col items-center gap-8">
          <div className="relative">
            <div className="h-20 w-20 border-4 border-blue-500/10 border-t-blue-500 rounded-full animate-spin"></div>
            <div className="absolute inset-0 flex items-center justify-center">
              <Loader className="text-blue-500 animate-pulse" size={24} />
            </div>
          </div>
          <div className="text-center">
            <p className="text-blue-600 font-black uppercase tracking-[0.5em] text-[10px] animate-pulse mb-4">
              Loading PropRoo Engine...
            </p>
            {Object.keys(downloadProgress).length > 0 && (
              <div className="space-y-2">
                {Object.entries(downloadProgress).map(([file, pct]) => (
                  <div key={file} className="flex items-center gap-3 text-xs">
                    <span className="text-slate-500 w-32 text-right">{file}.parquet</span>
                    <div className="w-48 h-2 bg-slate-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 transition-all duration-300"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-slate-400 w-12">{pct}%</span>
                  </div>
                ))}
              </div>
            )}
            <p className="text-slate-400 text-[10px] mt-4">
              Total: {Math.round(totalProgress)}%
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-50 text-slate-900 overflow-hidden font-sans">
      {/* Main workspace: flex-1, horizontal split 80/20 */}
      <div className="flex-1 flex min-h-0">
        {/* Map Area: flex-1 (80%) */}
        <div className="flex-1 relative bg-white">
          {/* Layers Panel — bottom-left */}
          <div className="absolute bottom-20 left-4 z-[1000] flex flex-col gap-2">
            <button
              onClick={() => setLayersExpanded(!layersExpanded)}
              className="bg-white/90 px-3 py-1.5 rounded-xl border border-slate-200 text-[10px] font-bold tracking-widest text-slate-600 backdrop-blur-sm shadow-sm flex items-center gap-2 cursor-pointer hover:bg-white transition-colors"
            >
              <Layers size={12} className="text-blue-600" /> LAYERS
              <ChevronRight size={12} className={`transition-transform ${layersExpanded ? 'rotate-90' : ''}`} />
            </button>
            {layersExpanded && (
              <div className="bg-white/90 px-3 py-2 rounded-xl border border-slate-200 backdrop-blur-sm shadow-sm space-y-1.5">
                <label className="flex items-center gap-2 text-[10px] font-bold text-slate-600 cursor-pointer">
                  <input type="checkbox" checked={showH3} onChange={e => setShowH3(e.target.checked)} className="accent-blue-600" />
                  Property Zones
                </label>
                <label className="flex items-center gap-2 text-[10px] font-bold text-slate-600 cursor-pointer">
                  <input type="checkbox" checked={showHeatmap} onChange={e => setShowHeatmap(e.target.checked)} className="accent-blue-600" />
                  Price Density
                </label>
                <label className="flex items-center gap-2 text-[10px] font-bold text-slate-600 cursor-pointer">
                  <input type="checkbox" checked={showContours} onChange={e => setShowContours(e.target.checked)} className="accent-blue-600" />
                  Price Contours
                </label>
                <label className="flex items-center gap-2 text-[10px] font-bold text-slate-600 cursor-pointer">
                  <input type="checkbox" checked={showPins} onChange={e => setShowPins(e.target.checked)} className="accent-blue-600" />
                  Properties
                </label>
                <label className="flex items-center gap-2 text-[10px] font-bold text-slate-600 cursor-pointer">
                  <input type="checkbox" checked={showStreets} onChange={e => setShowStreets(e.target.checked)} className="accent-blue-600" />
                  Street Names
                </label>
                <label className="flex items-center gap-2 text-[10px] font-bold text-slate-600 cursor-pointer">
                  <input type="checkbox" checked={showSuburbs} onChange={e => setShowSuburbs(e.target.checked)} className="accent-blue-600" />
                  Suburb Boundaries
                </label>
                <label className="flex items-center gap-2 text-[10px] font-bold text-slate-600 cursor-pointer">
                  <input type="checkbox" checked={showPOI} onChange={e => setShowPOI(e.target.checked)} className="accent-blue-600" />
                  Points of Interest
                </label>
                <label className="flex items-center gap-2 text-[10px] font-bold text-slate-600 cursor-pointer">
                  <input type="checkbox" checked={showChoropleth} onChange={e => setShowChoropleth(e.target.checked)} className="accent-blue-600" />
                  Growth Map
                </label>
              </div>
            )}
          </div>

          {/* Data Attribution Overlay */}
          <div className="absolute bottom-20 right-4 z-[1000] bg-white/80 px-3 py-2 rounded-lg text-[9px] text-slate-500 backdrop-blur-sm border border-slate-200/50 shadow-sm">
            <div className="font-bold text-slate-700 mb-1">Data Sources</div>
            <div className="flex items-center gap-1">
              <span>NSW Valuer General</span>
              <span className="text-slate-400">·</span>
              <span>2001-2024</span>
              <a href="https://www.valuergeneral.nsw.gov.au/property-sales-data" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline ml-1">↗</a>
            </div>
          </div>

          {/* Selected Suburb Indicator */}
          {selectedSuburb && (
            <div className="absolute top-4 left-4 z-[1000] bg-white/90 px-3 py-2 rounded-xl border border-slate-200 backdrop-blur-sm shadow-sm flex items-center gap-2">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Suburb:</span>
              <span className="text-xs font-black text-blue-600">{selectedSuburb}</span>
              <button
                onClick={() => setSelectedSuburb(null)}
                className="text-slate-400 hover:text-slate-600 transition-colors"
              >
                ✕
              </button>
            </div>
          )}

          {/* DeckGL Map */}
          <ErrorBoundary fallback={<div className="absolute inset-0 flex items-center justify-center bg-slate-100 text-slate-500 text-sm">Map rendering unavailable</div>}>
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
        <aside className="w-80 border-l border-slate-200 bg-white flex flex-col overflow-y-auto">
          {/* Filters Section — TOP of sidebar */}
          <div className="shrink-0 p-4 border-b border-slate-200 space-y-4">
            {/* Year Slider */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">2001</span>
                <span className="text-xl font-black text-blue-600">{selectedYear}</span>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">2024</span>
              </div>
              <input
                type="range"
                min={2001}
                max={2024}
                value={selectedYear}
                onChange={e => setSelectedYear(parseInt(e.target.value))}
                className="w-full h-2 bg-slate-200 rounded-full appearance-none cursor-pointer accent-blue-600"
              />
            </div>

            {/* Price Range */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5 text-slate-600">
                <Tag size={10} className="text-blue-600" />
                <label className="text-[9px] font-bold uppercase tracking-widest">Price</label>
              </div>
              <DualRangeSlider min={0} max={10000000} onChange={setPriceRange} />
              <div className="flex justify-between text-[9px] text-slate-400 font-mono">
                <span>{formatPrice(priceRange.min)}</span>
                <span>{formatPrice(priceRange.max)}</span>
              </div>
            </div>
          </div>

          {/* CAGR Chart */}
          <div className="shrink-0 p-4 border-b border-slate-200">
            <h4 className="flex items-center gap-2 text-blue-600 text-[10px] font-black uppercase tracking-widest mb-4">
              <Home size={14} /> TOP CAGR
            </h4>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={cagrData} layout="vertical">
                  <XAxis type="number" hide />
                  <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 9, fontWeight: 'bold', fill: '#64748b' }} width={60} />
                  <Tooltip cursor={{ fill: '#00000005' }} contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', fontSize: '10px', color: '#0f172a' }} />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20} fill="#10b981">
                    <LabelList dataKey="value" position="right" formatter={(v: number) => `${v}%`} style={{ fontSize: '10px', fontWeight: 'bold', fill: '#059669' }} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Sales Table (scrollable within sidebar) */}
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-left">
              <thead className="sticky top-0 bg-white/95 backdrop-blur-md text-[9px] font-black uppercase tracking-[0.2em] text-slate-400 z-10 border-b border-slate-200/60">
                <tr>
                  <th className="px-4 py-3 cursor-pointer hover:text-slate-600 transition-colors" onClick={() => { if (tableSort.field === 'address') setTableSort({ field: 'address', direction: tableSort.direction === 'asc' ? 'desc' : 'asc' }); else setTableSort({ field: 'address', direction: 'asc' }); }}>Address {tableSort.field === 'address' ? (tableSort.direction === 'asc' ? '↑' : '↓') : ''}</th>
                  <th className="px-4 py-3 cursor-pointer hover:text-slate-600 transition-colors" onClick={() => { if (tableSort.field === 'cagr') setTableSort({ field: 'cagr', direction: tableSort.direction === 'asc' ? 'desc' : 'asc' }); else setTableSort({ field: 'cagr', direction: 'desc' }); }}>CAGR {tableSort.field === 'cagr' ? (tableSort.direction === 'asc' ? '↑' : '↓') : ''}</th>
                  <th className="px-4 py-3 text-center cursor-pointer hover:text-slate-600 transition-colors" onClick={() => { if (tableSort.field === 'price') setTableSort({ field: 'price', direction: tableSort.direction === 'asc' ? 'desc' : 'asc' }); else setTableSort({ field: 'price', direction: 'desc' }); }}>Price {tableSort.field === 'price' ? (tableSort.direction === 'asc' ? '↑' : '↓') : ''}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {sortedSales.map(s => (
                  <tr
                    key={s.id}
                    onDoubleClick={() => {
                      handleRowClick(s);
                      drillDown(viewLevel === 'state' ? 'suburb' : 'street', viewLevel === 'state' ? s.property_locality : s.property_street_name);
                    }}
                    className={`hover:bg-blue-50 group cursor-pointer transition-all ${
                      highlightedPropertyId === s.property_id ? 'bg-blue-50 ring-1 ring-blue-200' : ''
                    }`}
                  >
                    <td className="px-4 py-3">
                      <p className="font-bold text-xs group-hover:text-blue-600 transition-colors uppercase tracking-tight">{viewLevel === 'state' ? s.property_locality : `${s.property_house_number} ${s.property_street_name}`}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="flex items-center gap-0.5 text-[9px] text-slate-500"><Home size={9} className="text-slate-400" /> {s.houseCount || 0}</span>
                        <span className="flex items-center gap-0.5 text-[9px] text-slate-500"><Building2 size={9} className="text-slate-400" /> {s.unitCount || 0}</span>
                      </div>
                      <p className="text-[9px] text-slate-400 mt-0.5">{s.totalTransactions || 0} large transactions recorded</p>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-1 w-12 bg-slate-200 rounded-full overflow-hidden">
                          <div className="h-full bg-emerald-500" style={{ width: `${Math.max(5, Math.min(100, (s.cagr || 0) * 800))}%` }}></div>
                        </div>
                        <span className="font-black text-emerald-600 text-[10px]">{((s.cagr || 0) * 100).toFixed(1)}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <p className="font-mono text-sm font-black text-slate-700 tracking-tighter">${s.purchase_price?.toLocaleString()}</p>
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
        <div className="absolute top-4 right-84 z-[1000] w-80 bg-white rounded-xl border border-slate-200 shadow-2xl overflow-hidden">
          <div className="p-4">
            <div className="flex justify-between items-start mb-3">
              <div>
                <h3 className="font-bold text-sm text-slate-900">
                  {selectedProperty.property_house_number} {selectedProperty.property_street_name}
                </h3>
                <p className="text-[10px] text-slate-500">{selectedProperty.property_locality}</p>
              </div>
              <button onClick={() => setSelectedProperty(null)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs mb-4">
              <div>
                <span className="text-slate-400 text-[9px] uppercase tracking-wider">Price</span>
                <p className="font-mono font-bold text-slate-900">${selectedProperty.purchase_price?.toLocaleString()}</p>
              </div>
              <div>
                <span className="text-slate-400 text-[9px] uppercase tracking-wider">Date</span>
                <p className="font-bold text-slate-900">{formatDate(selectedProperty.contract_date)}</p>
              </div>
              <div>
                <span className="text-slate-400 text-[9px] uppercase tracking-wider">Type</span>
                <p className="font-bold text-slate-900">{selectedProperty.primary_purpose}</p>
              </div>
              <div>
                <span className="text-slate-400 text-[9px] uppercase tracking-wider">Area</span>
                <p className="font-bold text-slate-900">{selectedProperty.area || 'N/A'}</p>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-200 text-[9px] text-slate-400">
              <div>Source: NSW Valuer General</div>
              <a href={`https://www.valuergeneral.nsw.gov.au/property-sales-data?property_id=${selectedProperty.property_id}`} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                View original record →
              </a>
            </div>
          </div>
        </div>
      )}


      {/* Loading Overlay */}
      {loading && (
        <div className="absolute inset-0 z-[10000] bg-slate-50/80 backdrop-blur-2xl flex items-center justify-center">
          <div className="flex flex-col items-center gap-8">
            <div className="relative">
              <div className="h-20 w-20 border-4 border-blue-500/10 border-t-blue-500 rounded-full animate-spin"></div>
              <div className="absolute inset-0 flex items-center justify-center">
                <Loader className="text-blue-500 animate-pulse" size={24} />
              </div>
            </div>
            <p className="text-blue-600 font-black uppercase tracking-[0.5em] text-[10px] animate-pulse">Orchestrating Unified Intelligence...</p>
          </div>
        </div>
      )}
    </div>
  );
}
