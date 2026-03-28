import { useEffect, useCallback } from 'react';
import { useAppStore } from '../store/useAppStore';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export function useStats() {
  const { year, propertyType, setSummaryData, setLoadingSummary } = useAppStore();

  const fetchSummary = useCallback(async () => {
    setLoadingSummary(true);
    try {
      const params = new URLSearchParams({ year: String(year) });
      if (propertyType) params.set('property_type', propertyType);
      
      const res = await fetch(`${API_BASE}/api/stats/global_summary?${params}`);
      const data = await res.json();
      setSummaryData(data);
    } catch (err) {
      console.error('Stats fetch error:', err);
    } finally {
      setLoadingSummary(false);
    }
  }, [year, propertyType, setSummaryData, setLoadingSummary]);

  useEffect(() => { fetchSummary(); }, [fetchSummary]);
  return { refetch: fetchSummary };
}