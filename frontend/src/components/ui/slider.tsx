import React, { useState, useCallback, useRef, useEffect } from 'react';

interface DualRangeSliderProps {
  min: number;
  max: number;
  value?: [number, number];
  onChange: (range: [number, number]) => void;
  step?: number;
  formatValue?: (val: number) => string;
}

function formatPrice(val: number): string {
  if (val >= 1000000) return `$${(val / 1000000).toFixed(1)}M`;
  if (val >= 1000) return `$${(val / 1000).toFixed(0)}K`;
  return `$${val}`;
}

export default function DualRangeSlider({
  min, max, value, onChange, step = 50000, formatValue = formatPrice
}: DualRangeSliderProps) {
  const [localValue, setLocalValue] = useState<[number, number]>(value || [min, max]);
  const trackRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState<'min' | 'max' | null>(null);

  const pct = useCallback((val: number) => ((val - min) / (max - min)) * 100, [min, max]);

  const handlePointerDown = useCallback((handle: 'min' | 'max') => (e: React.PointerEvent) => {
    e.preventDefault();
    setDragging(handle);
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, []);

  useEffect(() => {
    if (!dragging || !trackRef.current) return;

    const handleMove = (e: PointerEvent) => {
      const rect = trackRef.current!.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const val = Math.round((min + ratio * (max - min)) / step) * step;

      setLocalValue(prev => {
        const next: [number, number] = [...prev];
        if (dragging === 'min') {
          next[0] = Math.min(val, prev[1] - step);
        } else {
          next[1] = Math.max(val, prev[0] + step);
        }
        return next;
      });
    };

    const handleUp = () => {
      setDragging(null);
      onChange(localValue);
    };

    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp);
    return () => {
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
    };
  }, [dragging, min, max, step, localValue, onChange]);

  useEffect(() => {
    if (value) setLocalValue(value);
  }, [value]);

  return (
    <div className="space-y-3">
      <div className="flex justify-between text-[10px] font-mono font-bold">
        <span className="text-blue-400">{formatValue(localValue[0])}</span>
        <span className="text-blue-400">{formatValue(localValue[1])}</span>
      </div>
      <div ref={trackRef} className="relative h-6 flex items-center cursor-pointer">
        <div className="absolute w-full h-1 bg-slate-700 rounded-full" />
        <div
          className="absolute h-1 bg-blue-500 rounded-full"
          style={{ left: `${pct(localValue[0])}%`, width: `${pct(localValue[1]) - pct(localValue[0])}%` }}
        />
        <div
          className="absolute w-4 h-4 bg-slate-900 border-2 border-blue-500 rounded-full shadow-lg shadow-blue-500/30 cursor-grab active:cursor-grabbing transition-shadow hover:shadow-blue-500/50"
          style={{ left: `calc(${pct(localValue[0])}% - 8px)` }}
          onPointerDown={handlePointerDown('min')}
        />
        <div
          className="absolute w-4 h-4 bg-slate-900 border-2 border-blue-500 rounded-full shadow-lg shadow-blue-500/30 cursor-grab active:cursor-grabbing transition-shadow hover:shadow-blue-500/50"
          style={{ left: `calc(${pct(localValue[1])}% - 8px)` }}
          onPointerDown={handlePointerDown('max')}
        />
      </div>
    </div>
  );
}
