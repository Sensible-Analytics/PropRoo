import { create } from 'zustand';
import type { ViewState, H3FeatureCollection, GlobalSummary } from '../types';

interface AppState {
  year: number;
  propertyType: string | null;
  viewState: ViewState;
  mapData: H3FeatureCollection | null;
  summaryData: GlobalSummary | null;
  loadingMap: boolean;
  loadingSummary: boolean;
  priceRange: { min: number; max: number };

  setYear: (year: number) => void;
  setPropertyType: (type: string | null) => void;
  setViewState: (viewState: ViewState) => void;
  setMapData: (data: H3FeatureCollection | null) => void;
  setSummaryData: (data: GlobalSummary | null) => void;
  setLoadingMap: (loading: boolean) => void;
  setLoadingSummary: (loading: boolean) => void;
  setPriceRange: (range: { min: number; max: number }) => void;
}

export const useAppStore = create<AppState>((set) => ({
  year: 2024,
  propertyType: null,
  viewState: {
    longitude: 151.2093,
    latitude: -33.8688,
    zoom: 9,
    pitch: 0,
    bearing: 0,
  },
  mapData: null,
  summaryData: null,
  loadingMap: false,
  loadingSummary: false,
  priceRange: { min: 0, max: 10000000 },

  setYear: (year) => set({ year }),
  setPropertyType: (propertyType) => set({ propertyType }),
  setViewState: (viewState) => set({ viewState }),
  setMapData: (mapData) => set({ mapData }),
  setSummaryData: (summaryData) => set({ summaryData }),
  setLoadingMap: (loadingMap) => set({ loadingMap }),
  setLoadingSummary: (loadingSummary) => set({ loadingSummary }),
  setPriceRange: (priceRange) => set({ priceRange }),
}));