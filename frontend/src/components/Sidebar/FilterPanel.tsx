import React from 'react';
import { useAppStore } from '../../store/useAppStore';
import { Calendar } from 'lucide-react';
import DualRangeSlider from '../DualRangeSlider';

export default function FilterPanel() {
  const { year, setYear, propertyType, setPropertyType, priceRange, setPriceRange } = useAppStore();
  const availableYears = Array.from({ length: 24 }, (_, i) => 2024 - i);

  return (
    <div className="flex items-center gap-6">
      <div className="w-56 flex flex-col gap-1">
        <label className="text-[9px] font-bold text-slate-500 uppercase tracking-widest pl-1">PRICE RANGE</label>
        <DualRangeSlider min={0} max={10000000} onChange={setPriceRange} />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-[9px] font-bold text-slate-500 uppercase tracking-widest pl-1">CATEGORY</label>
        <div className="bg-slate-800 px-3 py-1.5 rounded-xl border border-slate-700">
          <select
            value={propertyType || ''}
            onChange={e => setPropertyType(e.target.value || null)}
            className="bg-transparent text-xs font-bold focus:outline-none cursor-pointer text-slate-200"
          >
            <option value="">ALL PROPERTIES</option>
            <option value="Residence">RESIDENCE</option>
            <option value="Strata Unit">STRATA UNIT</option>
          </select>
        </div>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-[9px] font-bold text-slate-500 uppercase tracking-widest pl-1">YEAR</label>
        <div className="bg-blue-600/20 px-3 py-1.5 rounded-xl border border-blue-500/30 flex items-center gap-2">
          <Calendar size={12} className="text-blue-400" />
          <select
            value={year}
            onChange={e => setYear(parseInt(e.target.value))}
            className="bg-transparent text-xs font-bold focus:outline-none cursor-pointer text-blue-300"
          >
            {availableYears.map(y => (
              <option key={y} value={y} className="bg-slate-950 font-sans">{y}</option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}