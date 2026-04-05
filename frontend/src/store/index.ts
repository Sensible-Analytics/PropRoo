import { create } from 'zustand';

// Types (mirroring Dashboard.tsx local types)
export interface SaleRecord {
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

export interface SuburbSummary {
  suburb: string;
  avg_cagr: number;
  unique_properties: number;
  total_sales: number;
  latitude: number;
  longitude: number;
}

export interface StreetSummary {
  street_name: string;
  suburb: string;
  avg_cagr: number;
  unique_properties: number;
  total_sales: number;
  latitude: number;
  longitude: number;
}

export interface H3Cell {
  h3_index: string;
  lat: number;
  lng: number;
  median_price: number;
  sale_count: number;
  avg_cagr: number;
}

// Navigation State
interface NavigationState {
  viewLevel: 'state' | 'suburb' | 'street' | 'property';
  selection: { suburb: string | null; street: string | null; propertyId: string | null };
  setViewLevel: (level: NavigationState['viewLevel']) => void;
  setSelection: (selection: Partial<NavigationState['selection']>) => void;
  handleBack: () => void;
  drillDown: (
    type: string,
    value: string,
    suburbLeaderboard: SuburbSummary[],
    streetLeaderboard: StreetSummary[],
    setViewState: (updater: (prev: any) => any) => void,
  ) => void;
}

export const useNavigationStore = create<NavigationState>((set, get) => ({
  viewLevel: 'state',
  selection: { suburb: null, street: null, propertyId: null },

  setViewLevel: (level) => set({ viewLevel: level }),

  setSelection: (partial) =>
    set((state) => ({
      selection: { ...state.selection, ...partial },
    })),

  handleBack: () => {
    const { viewLevel, selection } = get();
    if (viewLevel === 'property') {
      set({ viewLevel: 'street', selection: { ...selection, propertyId: null } });
    } else if (viewLevel === 'street') {
      set({ viewLevel: 'suburb', selection: { ...selection, street: null } });
    } else if (viewLevel === 'suburb') {
      set({ viewLevel: 'state', selection: { suburb: null, street: null, propertyId: null } });
    }
  },

  drillDown: (type, value, suburbLeaderboard, streetLeaderboard, setViewState) => {
    const { FlyToInterpolator } = require('@deck.gl/core');
    if (type === 'suburb') {
      set({
        selection: { suburb: value, street: null, propertyId: null },
        viewLevel: 'suburb',
      });
      const suburb = suburbLeaderboard.find(s => s.suburb === value);
      if (suburb) {
        setViewState((prev: any) => ({
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
      set((state) => ({
        selection: { ...state.selection, street: value, propertyId: null },
        viewLevel: 'street',
      }));
      const street = streetLeaderboard.find(s => s.street_name === value);
      if (street) {
        setViewState((prev: any) => ({
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
      set((state) => ({
        selection: { ...state.selection, propertyId: value },
        viewLevel: 'property',
      }));
    }
  },
}));

// Filter State
interface FilterState {
  selectedYear: number;
  propertyType: string;
  priceRange: { min: number; max: number };
  setSelectedYear: (year: number) => void;
  setPropertyType: (type: string) => void;
  setPriceRange: (range: { min: number; max: number }) => void;
}

export const useFilterStore = create<FilterState>((set) => ({
  selectedYear: 2024,
  propertyType: '',
  priceRange: { min: 0, max: 10000000 },

  setSelectedYear: (year) => set({ selectedYear: year }),
  setPropertyType: (type) => set({ propertyType: type }),
  setPriceRange: (range) => set({ priceRange: range }),
}));

// Map State
interface MapState {
  viewState: {
    longitude: number;
    latitude: number;
    zoom: number;
    pitch: number;
    bearing: number;
  };
  mapZoom: number;
  setViewState: (updater: Partial<MapState['viewState']> | ((prev: MapState['viewState']) => MapState['viewState'])) => void;
  setMapZoom: (zoom: number) => void;
}

const INITIAL_VIEW_STATE = {
  longitude: 151.2093,
  latitude: -33.8688,
  zoom: 10,
  pitch: 45,
  bearing: 0,
};

export const useMapStore = create<MapState>((set) => ({
  viewState: INITIAL_VIEW_STATE,
  mapZoom: 10,

  setViewState: (updater) =>
    set((state) => ({
      viewState: typeof updater === 'function' ? updater(state.viewState) : { ...state.viewState, ...updater },
    })),

  setMapZoom: (zoom) => set({ mapZoom: zoom }),
}));

// Layer State
interface LayerState {
  showH3: boolean;
  showHeatmap: boolean;
  showContours: boolean;
  showPins: boolean;
  setShowH3: (v: boolean) => void;
  setShowHeatmap: (v: boolean) => void;
  setShowContours: (v: boolean) => void;
  setShowPins: (v: boolean) => void;
}

export const useLayerStore = create<LayerState>((set) => ({
  showH3: true,
  showHeatmap: false,
  showContours: false,
  showPins: false,

  setShowH3: (v) => set({ showH3: v }),
  setShowHeatmap: (v) => set({ showHeatmap: v }),
  setShowContours: (v) => set({ showContours: v }),
  setShowPins: (v) => set({ showPins: v }),
}));

// Data State
interface DataState {
  sales: SaleRecord[];
  suburbLeaderboard: SuburbSummary[];
  streetLeaderboard: StreetSummary[];
  h3Cells: H3Cell[];
  heatmapData: SaleRecord[];
  loading: boolean;
  setSales: (sales: SaleRecord[]) => void;
  setSuburbLeaderboard: (data: SuburbSummary[]) => void;
  setStreetLeaderboard: (data: StreetSummary[]) => void;
  setH3Cells: (cells: H3Cell[]) => void;
  setHeatmapData: (data: SaleRecord[]) => void;
  setLoading: (loading: boolean) => void;
}

export const useDataStore = create<DataState>((set) => ({
  sales: [],
  suburbLeaderboard: [],
  streetLeaderboard: [],
  h3Cells: [],
  heatmapData: [],
  loading: true,

  setSales: (sales) => set({ sales }),
  setSuburbLeaderboard: (data) => set({ suburbLeaderboard: data }),
  setStreetLeaderboard: (data) => set({ streetLeaderboard: data }),
  setH3Cells: (cells) => set({ h3Cells: cells }),
  setHeatmapData: (data) => set({ heatmapData: data }),
  setLoading: (loading) => set({ loading }),
}));
