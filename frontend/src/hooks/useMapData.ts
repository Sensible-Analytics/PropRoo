import { useEffect, useCallback, useRef } from 'react';
import { useAppStore } from '../store/useAppStore';
import { useDebounce } from './useDebounce';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export function useMapData() {
  const { viewState, year, setMapData, setLoadingMap } = useAppStore();
  const abortRef = useRef<AbortController | null>(null);

  const debouncedViewState = useDebounce(viewState, 300);

  const fetchViewport = useCallback(async () => {
    if (!debouncedViewState) return;

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    const { latitude: lat, longitude: lng, zoom } = debouncedViewState;
    const delta = Math.pow(2, 10 - zoom);

    const params = new URLSearchParams({
      min_lat: String(lat - delta),
      max_lat: String(lat + delta),
      min_lng: String(lng - delta * 1.5),
      max_lng: String(lng + delta * 1.5),
      zoom: String(Math.round(zoom)),
      year: String(year),
    });

    setLoadingMap(true);
    try {
      const res = await fetch(`${API_BASE}/api/map/viewport?${params}`, {
        signal: abortRef.current.signal,
      });
      const data = await res.json();
      setMapData(data);
    } catch (err: any) {
      if (err.name !== 'AbortError') console.error('Map fetch error:', err);
    } finally {
      setLoadingMap(false);
    }
  }, [debouncedViewState, year, setMapData, setLoadingMap]);

  useEffect(() => { fetchViewport(); }, [fetchViewport]);
}