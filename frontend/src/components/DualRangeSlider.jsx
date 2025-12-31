import React, { useState, useEffect, useCallback, useRef } from 'react';

const DualRangeSlider = ({ min, max, onChange }) => {
    const [minVal, setMinVal] = useState(min);
    const [maxVal, setMaxVal] = useState(max);
    const minValRef = useRef(min);
    const maxValRef = useRef(max);
    const range = useRef(null);

    // Helper to calculate percentage position for CSS styling
    const getPercent = useCallback(
        (value) => Math.round(((value - min) / (max - min)) * 100),
        [min, max]
    );

    // Update the visual blue range bar when min changes
    useEffect(() => {
        const minPercent = getPercent(minVal);
        const maxPercent = getPercent(maxValRef.current);

        if (range.current) {
            range.current.style.left = `${minPercent}%`;
            range.current.style.width = `${maxPercent - minPercent}%`;
        }
    }, [minVal, getPercent]);

    // Update the visual blue range bar when max changes
    useEffect(() => {
        const minPercent = getPercent(minValRef.current);
        const maxPercent = getPercent(maxVal);

        if (range.current) {
            range.current.style.width = `${maxPercent - minPercent}%`;
        }
    }, [maxVal, getPercent]);

    // Debounce the onChange callback to avoid excessive API calls
    // while the user is actively sliding the handles.
    useEffect(() => {
        const handler = setTimeout(() => {
            onChange({ min: minVal, max: maxVal });
        }, 300);
        return () => clearTimeout(handler);
    }, [minVal, maxVal, onChange]);

    const formatPrice = (val) => {
        if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`;
        if (val >= 1000) return `${(val / 1000).toFixed(0)}K`;
        return val;
    };

    return (
        <div className="relative w-full flex flex-col items-center pt-2">
            <input
                type="range"
                min={min}
                max={max}
                value={minVal}
                onChange={(event) => {
                    const value = Math.min(Number(event.target.value), maxVal - 1);
                    setMinVal(value);
                    minValRef.current = value;
                }}
                className="thumb thumb--left"
                style={{ zIndex: minVal > max - 100 ? "5" : undefined }}
            />
            <input
                type="range"
                min={min}
                max={max}
                value={maxVal}
                onChange={(event) => {
                    const value = Math.max(Number(event.target.value), minVal + 1);
                    setMaxVal(value);
                    maxValRef.current = value;
                }}
                className="thumb thumb--right"
            />

            <div className="slider relative w-full h-1 bg-slate-800 rounded-full">
                <div ref={range} className="slider__range absolute h-full bg-blue-500 rounded-full" />
            </div>

            <div className="flex justify-between w-full mt-4">
                <div className="text-[10px] font-black text-blue-400 font-mono tracking-tighter bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                    ${formatPrice(minVal)}
                </div>
                <div className="text-[10px] font-black text-blue-400 font-mono tracking-tighter bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                    ${formatPrice(maxVal)}
                </div>
            </div>

            <style dangerouslySetInnerHTML={{
                __html: `
                .thumb, .thumb::-webkit-slider-thumb {
                    -webkit-appearance: none;
                    -webkit-tap-highlight-color: transparent;
                }
                .thumb {
                    pointer-events: none;
                    position: absolute;
                    height: 0;
                    width: 100%;
                    outline: none;
                    top: 8px;
                }
                .thumb::-webkit-slider-thumb {
                    background-color: #3b82f6;
                    border: 2px solid #ffffff;
                    border-radius: 50%;
                    cursor: pointer;
                    height: 14px;
                    width: 14px;
                    margin-top: -5px;
                    pointer-events: all;
                    position: relative;
                    box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
                }
                .thumb::-moz-range-thumb {
                    background-color: #3b82f6;
                    border: 2px solid #ffffff;
                    border-radius: 50%;
                    cursor: pointer;
                    height: 14px;
                    width: 14px;
                    pointer-events: all;
                    position: relative;
                    box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
                }
            `}} />
        </div>
    );
};

export default DualRangeSlider;
