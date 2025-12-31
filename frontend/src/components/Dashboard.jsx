import React, { useState, useEffect, useMemo } from 'react';
import { Search, Home, TrendingUp, Loader, ArrowLeft, ChevronRight, Calendar, Map as MapIcon, Layers } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup, useMap, CircleMarker, LayerGroup, LayersControl } from 'react-leaflet';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, Legend } from 'recharts';
import 'leaflet/dist/leaflet.css';
import axios from 'axios';
import DualRangeSlider from './DualRangeSlider';

// Fix for default Leaflet icon issues
import L from 'leaflet';
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

// API Base URL
const API_URL = 'http://localhost:8000/api';

// Cluster Colors (Top 10 distinct colors)
const CLUSTER_COLORS = [
    '#3b82f6', // Blue
    '#ef4444', // Red
    '#10b981', // Emerald
    '#f59e0b', // Amber
    '#8b5cf6', // Violet
    '#ec4899', // Pink
    '#06b6d4', // Cyan
    '#f97316', // Orange
    '#84cc16', // Lime
    '#64748b'  // Slate
];

// Map View Contoller
function ChangeView({ center, zoom }) {
    const map = useMap();
    useEffect(() => {
        if (center) {
            map.setView(center, zoom || map.getZoom());
        }
    }, [center, zoom, map]);
    return null;
}

const Dashboard = () => {
    // Navigation State
    const [viewLevel, setViewLevel] = useState('state'); // 'state', 'suburb', 'street', 'property'
    const [selection, setSelection] = useState({ suburb: null, street: null, propertyId: null });

    // Data State
    const [sales, setSales] = useState([]);
    const [leaderboards, setLeaderboards] = useState({ growth: { suburbs: [], streets: [] }, activity: { suburbs: [], streets: [] } });
    const [unifiedData, setUnifiedData] = useState({ clusters: [] });
    const [loading, setLoading] = useState(true);

    // Global Filters
    const [selectedYear, setSelectedYear] = useState(2024);
    const [propertyType, setPropertyType] = useState('');
    const [priceRange, setPriceRange] = useState({ min: 0, max: 10000000 });
    const [mapCenter, setMapCenter] = useState([-33.8688, 151.2093]);
    const [mapZoom, setMapZoom] = useState(11);

    // Available Years (2001-2024)
    const availableYears = Array.from({ length: 24 }, (_, i) => 2024 - i);

    useEffect(() => {
        fetchData();
    }, [viewLevel, selection, selectedYear, propertyType, priceRange]);

    const fetchData = async () => {
        setLoading(true);
        try {
            // 1. Fetch Leaderboards (Top 5)
            const lbRes = await axios.get(`${API_URL}/stats/top_performers`, {
                params: { year: selectedYear, property_type: propertyType || undefined }
            });
            setLeaderboards(lbRes.data);

            // 2. Fetch Unified Map Data (Clusters + Neighbors)
            const mapRes = await axios.get(`${API_URL}/stats/unified_map`, {
                params: { level: viewLevel === 'state' ? 'suburb' : viewLevel === 'suburb' ? 'street' : 'suburb', year: selectedYear }
            });
            setUnifiedData(mapRes.data);

            // 3. Base Params for detailed list
            const baseParams = {
                limit: 100,
                start_date: `${selectedYear}-01-01`,
                end_date: `${selectedYear}-12-31`,
                property_type: propertyType || undefined,
                min_price: priceRange.min || undefined,
                max_price: priceRange.max >= 10000000 ? undefined : priceRange.max
            };

            // 4. Detailed level data
            if (viewLevel === 'state') {
                const res = await axios.get(`${API_URL}/sales`, { params: baseParams });
                setSales(res.data);
                setMapCenter([-33.8688, 151.2093]);
                setMapZoom(11);
            } else if (viewLevel === 'suburb') {
                const res = await axios.get(`${API_URL}/sales`, { params: { ...baseParams, suburb: selection.suburb } });
                setSales(res.data);
                if (res.data.length > 0) {
                    setMapCenter([res.data[0].latitude, res.data[0].longitude]);
                    setMapZoom(13);
                }
            } else if (viewLevel === 'street') {
                const res = await axios.get(`${API_URL}/sales`, { params: { ...baseParams, suburb: selection.suburb } });
                const streetSales = res.data.filter(s => s.property_street_name === selection.street);
                setSales(streetSales);
                if (streetSales.length > 0) {
                    setMapCenter([streetSales[0].latitude, streetSales[0].longitude]);
                    setMapZoom(15);
                }
            } else if (viewLevel === 'property') {
                const histRes = await axios.get(`${API_URL}/property/${selection.propertyId}/history`);
                setSales(histRes.data);
                if (histRes.data.length > 0) {
                    setMapCenter([histRes.data[0].latitude, histRes.data[0].longitude]);
                    setMapZoom(17);
                }
            }
        } catch (error) {
            console.error("Fetch failed:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleBack = () => {
        if (viewLevel === 'property') setViewLevel('street');
        else if (viewLevel === 'street') setViewLevel('suburb');
        else if (viewLevel === 'suburb') setViewLevel('state');
    };

    const drillDown = (type, value) => {
        if (type === 'suburb') {
            setSelection({ suburb: value, street: null, propertyId: null });
            setViewLevel('suburb');
        } else if (type === 'street') {
            setSelection({ ...selection, street: value, propertyId: null });
            setViewLevel('street');
        } else if (type === 'property') {
            setSelection({ ...selection, propertyId: value });
            setViewLevel('property');
        }
    };

    const cagrData = useMemo(() => {
        return (viewLevel === 'state' ? leaderboards.growth.suburbs : leaderboards.growth.streets)
            .slice(0, 5)
            .map(i => ({
                name: (i.suburb || i.street_name).split(' ')[0],
                value: parseFloat((i.avg_cagr * 100).toFixed(1)),
                fullName: i.suburb || i.street_name
            }));
    }, [leaderboards, viewLevel]);

    const activityData = useMemo(() => {
        return (viewLevel === 'state' ? leaderboards.activity.suburbs : leaderboards.activity.streets)
            .slice(0, 5)
            .map(i => ({
                name: (i.suburb || i.street_name).split(' ')[0],
                value: i.sales_count || i.property_count,
                fullName: i.suburb || i.street_name
            }));
    }, [leaderboards, viewLevel]);

    return (
        <div className="h-screen w-screen flex flex-col bg-slate-950 text-slate-100 overflow-hidden font-sans">
            {/* Header */}
            <div className="h-20 shrink-0 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md px-6 flex justify-between items-center z-50">
                <div className="flex items-center gap-6">
                    {viewLevel !== 'state' && (
                        <button onClick={handleBack} className="p-2 hover:bg-slate-800 rounded-full transition-all border border-slate-700 bg-slate-900 shadow-lg group">
                            <ArrowLeft size={18} className="group-hover:-translate-x-1 transition-transform" />
                        </button>
                    )}
                    <div className="flex flex-col">
                        <div className="flex items-center gap-2 text-[10px] font-bold opacity-30 uppercase tracking-[0.2em] mb-0.5">
                            NSW UNIFIED SPATIAL <ChevronRight size={10} /> {viewLevel}
                        </div>
                        <p className="text-lg font-black tracking-tight text-white leading-none">
                            {viewLevel === 'state' ? 'STATE OVERVIEW' :
                                viewLevel === 'suburb' ? selection.suburb :
                                    viewLevel === 'street' ? selection.street :
                                        `ANALYSIS`}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-6">
                    <div className="w-56 flex flex-col gap-1">
                        <label className="text-[9px] font-bold text-slate-500 uppercase tracking-widest pl-1">PRICE RANGE</label>
                        <DualRangeSlider min={0} max={10000000} onChange={setPriceRange} />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-[9px] font-bold text-slate-500 uppercase tracking-widest pl-1">CATEGORY</label>
                        <div className="bg-slate-800 px-3 py-1.5 rounded-xl border border-slate-700">
                            <select value={propertyType} onChange={e => setPropertyType(e.target.value)} className="bg-transparent text-xs font-bold focus:outline-none cursor-pointer">
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
                            <select value={selectedYear} onChange={e => setSelectedYear(parseInt(e.target.value))} className="bg-transparent text-xs font-bold focus:outline-none cursor-pointer text-blue-300">
                                {availableYears.map(y => <option key={y} value={y} className="bg-slate-950 font-sans">{y}</option>)}
                            </select>
                        </div>
                    </div>
                </div>
            </div>

            {/* Main Visual Workspace */}
            <div className="h-[520px] shrink-0 p-4 grid grid-cols-12 gap-4">
                {/* Unified Unified Map (70% width) */}
                <div className="col-span-12 lg:col-span-8 bg-slate-900 rounded-3xl border border-slate-800 overflow-hidden relative shadow-2xl">
                    <div className="absolute top-4 left-4 z-[1000] flex gap-2">
                        <div className="bg-slate-950/90 px-3 py-1.5 rounded-xl border border-slate-800 text-[10px] font-bold tracking-widest text-slate-300 backdrop-blur-sm flex items-center gap-2">
                            <Layers size={12} className="text-blue-500" /> UNIFIED SPATIAL LAYER
                        </div>
                        <div className="bg-blue-900/40 px-3 py-1.5 rounded-xl border border-blue-500/30 text-[10px] font-bold tracking-widest text-blue-200 backdrop-blur-sm">
                            {unifiedData.clusters.length} PERFORMANCE CLUSTERS
                        </div>
                    </div>

                    <MapContainer center={mapCenter} zoom={mapZoom} zoomControl={false} style={{ height: "100%", width: "100%" }}>
                        <TileLayer url="https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png" />
                        <ChangeView center={mapCenter} zoom={mapZoom} />

                        {unifiedData.clusters.map((cluster, idx) => {
                            const clusterColor = CLUSTER_COLORS[idx % CLUSTER_COLORS.length];
                            return (
                                <LayerGroup key={cluster.id}>
                                    {/* Main Entity Marker */}
                                    <CircleMarker
                                        center={[cluster.lat, cluster.lon]}
                                        radius={18}
                                        fillOpacity={0.9}
                                        color={clusterColor}
                                        fillColor={clusterColor}
                                        weight={4}
                                        className="animate-pulse"
                                    >
                                        <Popup>
                                            <div className="text-slate-900 font-sans p-3 min-w-[200px]">
                                                <div className="flex justify-between items-start border-b-2 pb-2 mb-2">
                                                    <div>
                                                        <p className="text-[10px] font-black text-blue-600 uppercase tracking-tighter">Rank #{cluster.rank}</p>
                                                        <p className="font-bold text-base leading-tight">{cluster.name}</p>
                                                    </div>
                                                    <div className="bg-emerald-50 px-2 py-1 rounded-lg">
                                                        <p className="text-[10px] font-black text-emerald-600 uppercase">CAGR</p>
                                                        <p className="text-sm font-black text-emerald-700">{((cluster.cagr || 0) * 100).toFixed(2)}%</p>
                                                    </div>
                                                </div>
                                                <button
                                                    onClick={() => drillDown(viewLevel === 'state' ? 'suburb' : 'street', cluster.name)}
                                                    className="w-full bg-slate-900 text-white py-2 rounded-lg text-[10px] font-bold tracking-widest uppercase mt-2 hover:bg-slate-800"
                                                >
                                                    Drill Into Cluster
                                                </button>
                                            </div>
                                        </Popup>
                                    </CircleMarker>

                                    {/* Neighbors */}
                                    {cluster.neighbors.map((neighbor, nIdx) => (
                                        <CircleMarker
                                            key={`${cluster.id}-n-${nIdx}`}
                                            center={[neighbor.lat, neighbor.lon]}
                                            radius={8}
                                            fillOpacity={0.6}
                                            color={clusterColor}
                                            fillColor={clusterColor}
                                            weight={1}
                                            dashArray="3, 3"
                                        >
                                            <Popup>
                                                <div className="text-slate-900 font-sans p-2">
                                                    <p className="text-[9px] font-black text-slate-400 uppercase">Neighbor of {cluster.name}</p>
                                                    <p className="font-bold text-sm">{neighbor.name}</p>
                                                    <p className="text-xs font-black text-blue-600 mt-1">CAGR: {((neighbor.cagr || 0) * 100).toFixed(1)}%</p>
                                                </div>
                                            </Popup>
                                        </CircleMarker>
                                    ))}
                                </LayerGroup>
                            );
                        })}

                        {/* Direct Sales Markers for the active level */}
                        {sales.filter(s => s.latitude && s.longitude).map(s => (
                            <Marker
                                key={s.id}
                                position={[s.latitude, s.longitude]}
                                opacity={0.6}
                                zIndexOffset={-1000}
                            />
                        ))}
                    </MapContainer>
                </div>

                {/* Analytical Charts (30% width) */}
                <div className="col-span-12 lg:col-span-4 flex flex-col gap-4 h-full">
                    <div className="flex-1 bg-slate-900/50 border border-slate-800 rounded-3xl p-5 overflow-hidden flex flex-col">
                        <h4 className="flex items-center gap-2 text-emerald-400 text-[10px] font-black uppercase tracking-widest mb-4">
                            <TrendingUp size={14} /> CAGR % PERFORMANCE
                        </h4>
                        <div className="flex-grow">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={cagrData} layout="vertical">
                                    <XAxis type="number" hide domain={[0, 'dataMax + 2']} />
                                    <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 9, fontWeight: 'bold', fill: '#94a3b8' }} width={60} />
                                    <Tooltip cursor={{ fill: '#ffffff05' }} contentStyle={{ backgroundColor: '#0f172a', border: 'none', borderRadius: '12px', fontSize: '10px' }} />
                                    <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
                                        {cagrData.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={CLUSTER_COLORS[index % CLUSTER_COLORS.length]} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    <div className="flex-1 bg-slate-900/50 border border-slate-800 rounded-3xl p-5 overflow-hidden flex flex-col">
                        <h4 className="flex items-center gap-2 text-blue-400 text-[10px] font-black uppercase tracking-widest mb-4">
                            <Home size={14} /> TRANSACTION COUNT
                        </h4>
                        <div className="flex-grow">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={activityData} layout="vertical">
                                    <XAxis type="number" hide />
                                    <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 9, fontWeight: 'bold', fill: '#94a3b8' }} width={60} />
                                    <Tooltip cursor={{ fill: '#ffffff05' }} contentStyle={{ backgroundColor: '#0f172a', border: 'none', borderRadius: '12px', fontSize: '10px' }} />
                                    <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20} fill="#3b82f6" />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>
            </div>

            {/* Bottom Entity Table */}
            <div className="flex-grow p-4 min-h-0 bg-slate-950">
                <div className="h-full bg-slate-900/20 border border-slate-800/40 rounded-3xl flex flex-col overflow-hidden">
                    <div className="px-8 py-4 border-b border-slate-800/40 flex justify-between items-center bg-slate-950/40">
                        <p className="text-[10px] font-black tracking-[0.4em] text-slate-500 uppercase">Spatial Entity Archive</p>
                    </div>
                    <div className="flex-grow overflow-auto custom-scrollbar">
                        <table className="w-full text-left">
                            <thead className="sticky top-0 bg-slate-950/90 backdrop-blur-md text-[9px] font-black uppercase tracking-[0.2em] text-slate-500 z-10 border-b border-slate-800/40">
                                <tr>
                                    <th className="px-8 py-4">Contextual Address</th>
                                    <th className="px-8 py-4 text-center">Market Valuation</th>
                                    <th className="px-8 py-4">Growth performance</th>
                                    <th className="px-8 py-4 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800/30">
                                {sales.map(s => (
                                    <tr
                                        key={s.id}
                                        onClick={() => drillDown(viewLevel === 'state' ? 'suburb' : 'street', viewLevel === 'state' ? s.property_locality : s.property_street_name)}
                                        className="hover:bg-blue-600/5 group cursor-pointer transition-all"
                                    >
                                        <td className="px-8 py-4">
                                            <p className="font-bold text-sm group-hover:text-blue-400 transition-colors uppercase tracking-tight">{viewLevel === 'state' ? s.property_locality : `${s.property_house_number} ${s.property_street_name}`}</p>
                                            <p className="text-[9px] text-slate-600 font-black tracking-[0.1em] mt-0.5">{s.primary_purpose} &bull; {s.contract_date}</p>
                                        </td>
                                        <td className="px-8 py-4 text-center">
                                            <p className="font-mono text-base font-black text-slate-200 tracking-tighter">${s.purchase_price?.toLocaleString()}</p>
                                        </td>
                                        <td className="px-8 py-4">
                                            <div className="flex items-center gap-4">
                                                <div className="h-1 w-20 bg-slate-800 rounded-full overflow-hidden">
                                                    <div className="h-full bg-emerald-500" style={{ width: `${Math.max(5, Math.min(100, (s.cagr || 0) * 800))}%` }}></div>
                                                </div>
                                                <span className="font-black text-emerald-400 text-xs">{((s.cagr || 0) * 100).toFixed(1)}%</span>
                                            </div>
                                        </td>
                                        <td className="px-8 py-4 text-right">
                                            <button
                                                onClick={(e) => { e.stopPropagation(); drillDown('property', s.property_id); }}
                                                className="bg-blue-600/10 hover:bg-blue-600 text-blue-400 hover:text-white px-5 py-2 rounded-xl text-[9px] font-black tracking-[0.2em] transition-all uppercase border border-blue-500/20"
                                            >
                                                EXPLORE
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

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
};

export default Dashboard;
