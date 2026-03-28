import React from 'react';
import { useAppStore } from '../../store/useAppStore';
import { TrendingUp, Loader } from 'lucide-react';

const CLUSTER_COLORS = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#64748b'
];

export default function StatsPanel() {
  const { summaryData, loadingSummary, year } = useAppStore();

  if (loadingSummary) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader size={24} className="text-blue-400 animate-spin" />
      </div>
    );
  }

  const topSuburbs = summaryData?.top_suburbs?.slice(0, 5) || [];
  const topStreets = summaryData?.top_streets?.slice(0, 5) || [];

  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-emerald-400 text-[10px] font-black uppercase tracking-widest mb-2 flex items-center gap-2">
          <TrendingUp size={14} /> TOP SUBURBS {year}
        </h4>
        <div className="space-y-1">
          {topSuburbs.map((s, i) => (
            <div key={s.suburb} className="flex items-center gap-2">
              <div
                className="w-1 h-6 rounded-full"
                style={{ backgroundColor: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }}
              />
              <div className="flex-1 min-w-0">
                <p className="text-[10px] font-bold text-slate-300 truncate">{s.suburb}</p>
                <p className="text-[8px] text-slate-600">{s.total_sales} sales</p>
              </div>
              <span className="text-[10px] font-black text-emerald-400">
                {((s.avg_cagr || 0) * 100).toFixed(1)}%
              </span>
            </div>
          ))}
          {topSuburbs.length === 0 && (
            <p className="text-[10px] text-slate-600 italic">No data available</p>
          )}
        </div>
      </div>
      <div>
        <h4 className="text-blue-400 text-[10px] font-black uppercase tracking-widest mb-2">
          TOP STREETS {year}
        </h4>
        <div className="space-y-1">
          {topStreets.map((s, i) => (
            <div key={`${s.street_name}-${s.suburb}`} className="flex items-center gap-2">
              <div
                className="w-1 h-6 rounded-full"
                style={{ backgroundColor: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }}
              />
              <div className="flex-1 min-w-0">
                <p className="text-[10px] font-bold text-slate-300 truncate">
                  {s.street_name}, {s.suburb}
                </p>
              </div>
              <span className="text-[10px] font-black text-blue-400">
                {((s.avg_cagr || 0) * 100).toFixed(1)}%
              </span>
            </div>
          ))}
          {topStreets.length === 0 && (
            <p className="text-[10px] text-slate-600 italic">No data available</p>
          )}
        </div>
      </div>
    </div>
  );
}