import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { X, ChevronDown, ChevronUp, TrendingUp, TrendingDown, Minus, ExternalLink } from 'lucide-react';
import axios from 'axios';
import 'leaflet/dist/leaflet.css';

const API_URL = 'http://localhost:8000/api';

const PropertyDetailModal = ({ sale, onClose }) => {
    // State for property-specific historical and comparative data
    const [salesHistory, setSalesHistory] = useState([]);
    const [streetStats, setStreetStats] = useState(null);
    const [suburbStats, setSuburbStats] = useState(null);
    const [streetTrend, setStreetTrend] = useState([]);
    const [suburbTrend, setSuburbTrend] = useState([]);
    const [showMoreDetails, setShowMoreDetails] = useState(false);
    const [loading, setLoading] = useState(true);

    // Fetch details whenever the selected property (sale.property_id) changes
    useEffect(() => {
        fetchPropertyDetails();
    }, [sale.property_id]);

    /**
     * Orchestrates multiple API calls to gather:
     * 1. Sales history for this specific property
     * 2. Current year average CAGR for the street and suburb
     * 3. Long-term growth trends for street and suburb
     */
    const fetchPropertyDetails = async () => {
        setLoading(true);
        try {
            const [historyRes, streetRes, suburbRes, streetTrendRes, suburbTrendRes] = await Promise.all([
                axios.get(`${API_URL}/property/${sale.property_id}/history`),
                axios.get(`${API_URL}/stats/street_cagr`, {
                    params: {
                        street_name: sale.property_street_name,
                        suburb: sale.property_locality,
                        year: 2024
                    }
                }),
                axios.get(`${API_URL}/stats/suburb_cagr`, {
                    params: {
                        suburb: sale.property_locality,
                        year: 2024
                    }
                }),
                axios.get(`${API_URL}/stats/street_trend`, {
                    params: {
                        street_name: sale.property_street_name,
                        suburb: sale.property_locality
                    }
                }),
                axios.get(`${API_URL}/stats/suburb_trend`, {
                    params: { suburb: sale.property_locality }
                })
            ]);

            setSalesHistory(historyRes.data);
            setStreetStats(streetRes.data);
            setSuburbStats(suburbRes.data);
            setStreetTrend(streetTrendRes.data);
            setSuburbTrend(suburbTrendRes.data);
        } catch (error) {
            console.error('Error fetching property details:', error);
        } finally {
            setLoading(false);
        }
    };

    const getComparisonIndicator = (propertyCagr, streetAvg, suburbAvg) => {
        if (!propertyCagr || propertyCagr === null) {
            return { color: 'text-gray-500', icon: Minus, label: 'N/A', bgColor: 'bg-gray-100' };
        }

        const pCagr = propertyCagr * 100;
        const sStreet = streetAvg ? streetAvg * 100 : null;
        const sSuburb = suburbAvg ? suburbAvg * 100 : null;

        // Green: Better than both street and suburb
        if ((sStreet === null || pCagr > sStreet) && (sSuburb === null || pCagr > sSuburb)) {
            return { color: 'text-green-600', icon: TrendingUp, label: 'Above Average', bgColor: 'bg-green-50' };
        }

        // Red: Worse than both street and suburb
        if ((sStreet !== null && pCagr < sStreet) && (sSuburb !== null && pCagr < sSuburb)) {
            return { color: 'text-red-600', icon: TrendingDown, label: 'Below Average', bgColor: 'bg-red-50' };
        }

        // Yellow/Orange: Mixed performance
        return { color: 'text-yellow-600', icon: Minus, label: 'Mixed Performance', bgColor: 'bg-yellow-50' };
    };

    const indicator = getComparisonIndicator(sale.cagr, streetStats?.avg_cagr, suburbStats?.avg_cagr);
    const IconComponent = indicator.icon;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[90vh] overflow-y-auto">
                {/* Header */}
                <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center rounded-t-2xl z-10">
                    <div>
                        <h2 className="text-2xl font-bold text-gray-800">
                            {sale.property_house_number} {sale.property_street_name}
                        </h2>
                        <p className="text-gray-500">{sale.property_locality}, NSW {sale.property_post_code}</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-gray-100 rounded-full transition-colors"
                    >
                        <X size={24} className="text-gray-600" />
                    </button>
                </div>

                {loading ? (
                    <div className="p-10 text-center text-gray-500">Loading property details...</div>
                ) : (
                    <div className="p-6 space-y-6">
                        {/* Map Section */}
                        {sale.latitude && sale.longitude && (
                            <div className="bg-gray-50 rounded-xl p-4">
                                <h3 className="text-lg font-semibold text-gray-800 mb-3">Property Location</h3>
                                <div className="h-80 rounded-lg overflow-hidden">
                                    <MapContainer
                                        center={[sale.latitude, sale.longitude]}
                                        zoom={16}
                                        scrollWheelZoom={false}
                                        style={{ height: '100%', width: '100%' }}
                                    >
                                        <TileLayer
                                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                                            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                                        />
                                        <Marker position={[sale.latitude, sale.longitude]}>
                                            <Popup>
                                                <strong>{sale.property_house_number} {sale.property_street_name}</strong>
                                            </Popup>
                                        </Marker>
                                    </MapContainer>
                                </div>
                            </div>
                        )}

                        {/* CAGR Comparison Section */}
                        <div className="bg-gradient-to-br from-indigo-50 to-purple-50 rounded-xl p-6">
                            <h3 className="text-lg font-semibold text-gray-800 mb-4">Growth Performance</h3>

                            {/* Performance Indicator */}
                            <div className={`${indicator.bgColor} rounded-lg p-4 mb-4 flex items-center justify-center gap-3`}>
                                <IconComponent size={28} className={indicator.color} />
                                <span className={`text-xl font-bold ${indicator.color}`}>{indicator.label}</span>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                {/* Property CAGR */}
                                <div className="bg-white rounded-lg p-4 shadow-sm border-t-2 border-green-500">
                                    <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Property CAGR</p>
                                    <p className={`text-2xl font-bold ${sale.cagr > 0 ? 'text-green-600' : 'text-red-600'}`}>
                                        {sale.cagr ? `${(sale.cagr * 100).toFixed(2)}%` : 'N/A'}
                                    </p>
                                    <p className="text-[10px] text-gray-400 mt-1">Held for {sale.years_held?.toFixed(1)} years</p>
                                </div>

                                {/* Street Average */}
                                <div className="bg-white rounded-lg p-4 shadow-sm border-t-2 border-blue-500">
                                    <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Street Avg (2024)</p>
                                    <p className="text-2xl font-bold text-blue-600">
                                        {streetStats?.avg_cagr ? `${(streetStats.avg_cagr * 100).toFixed(2)}%` : 'N/A'}
                                    </p>
                                    <p className="text-[10px] text-gray-400 mt-1">Based on {streetStats?.property_count || 0} properties</p>
                                </div>

                                {/* Suburb Average */}
                                <div className="bg-white rounded-lg p-4 shadow-sm border-t-2 border-purple-500">
                                    <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Suburb Avg (2024)</p>
                                    <p className="text-2xl font-bold text-purple-600">
                                        {suburbStats?.avg_cagr ? `${(suburbStats.avg_cagr * 100).toFixed(2)}%` : 'N/A'}
                                    </p>
                                    <p className="text-[10px] text-gray-400 mt-1">Based on {suburbStats?.property_count || 0} properties</p>
                                </div>
                            </div>
                        </div>

                        {/* Trend Charts */}
                        <div className="bg-white border border-gray-100 rounded-xl p-6 shadow-sm">
                            <h3 className="text-lg font-semibold text-gray-800 mb-6 flex items-center gap-2">
                                <TrendingUp size={20} className="text-indigo-600" />
                                Historical Growth Trends
                            </h3>
                            <div className="h-[300px] w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={suburbTrend}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                                        <XAxis
                                            dataKey="year"
                                            axisLine={false}
                                            tickLine={false}
                                            tick={{ fill: '#9ca3af', fontSize: 12 }}
                                        />
                                        <YAxis
                                            axisLine={false}
                                            tickLine={false}
                                            tick={{ fill: '#9ca3af', fontSize: 12 }}
                                            tickFormatter={(val) => `${(val * 100).toFixed(0)}%`}
                                        />
                                        <Tooltip
                                            contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                                            formatter={(val) => [`${(val * 100).toFixed(2)}%`, 'Avg CAGR']}
                                        />
                                        <Legend />
                                        <Line
                                            name="Suburb Trend"
                                            type="monotone"
                                            dataKey="avg_cagr"
                                            stroke="#8b5cf6"
                                            strokeWidth={3}
                                            dot={{ r: 4, fill: '#8b5cf6' }}
                                            activeDot={{ r: 6 }}
                                        />
                                        {streetTrend.length > 0 && (
                                            <Line
                                                name="Street Trend"
                                                type="monotone"
                                                data={streetTrend}
                                                dataKey="avg_cagr"
                                                stroke="#3b82f6"
                                                strokeWidth={3}
                                                dot={{ r: 4, fill: '#3b82f6' }}
                                                activeDot={{ r: 6 }}
                                            />
                                        )}
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* Current Listings Section */}
                        {(sale.realestate_url || sale.domain_url || (salesHistory.length > 0 && (salesHistory[0].realestate_url || salesHistory[0].domain_url))) && (
                            <div className="bg-white border border-indigo-100 rounded-xl p-6 shadow-sm">
                                <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
                                    <ExternalLink size={20} className="text-indigo-600" />
                                    Current Listings
                                </h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {(sale.realestate_url || (salesHistory.length > 0 && salesHistory[0].realestate_url)) && (
                                        <a
                                            href={sale.realestate_url || salesHistory[0].realestate_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="flex items-center justify-between p-4 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg transition-colors group"
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 bg-red-600 rounded flex items-center justify-center text-white font-bold text-xs">RE</div>
                                                <span className="font-semibold text-red-900">View on Realestate.com.au</span>
                                            </div>
                                            <ExternalLink size={18} className="text-red-400 group-hover:text-red-700" />
                                        </a>
                                    )}
                                    {(sale.domain_url || (salesHistory.length > 0 && salesHistory[0].domain_url)) && (
                                        <a
                                            href={sale.domain_url || salesHistory[0].domain_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="flex items-center justify-between p-4 bg-green-50 hover:bg-green-100 border border-green-200 rounded-lg transition-colors group"
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 bg-green-600 rounded flex items-center justify-center text-white font-bold text-xs">D</div>
                                                <span className="font-semibold text-green-900">View on Domain.com.au</span>
                                            </div>
                                            <ExternalLink size={18} className="text-green-400 group-hover:text-green-700" />
                                        </a>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Sales History */}
                        <div className="bg-gray-50 rounded-xl p-6">
                            <h3 className="text-lg font-semibold text-gray-800 mb-4">Sales History</h3>
                            {salesHistory.length > 0 ? (
                                <div className="space-y-3">
                                    {salesHistory.map((s, idx) => (
                                        <div key={s.id} className="bg-white rounded-lg p-4 shadow-sm border-l-4 border-indigo-500">
                                            <div className="flex justify-between items-start">
                                                <div>
                                                    <p className="text-sm text-gray-500">Sale {idx + 1} - {s.contract_date}</p>
                                                    <p className="text-xl font-bold text-gray-800 mt-1">
                                                        ${s.purchase_price?.toLocaleString()}
                                                    </p>
                                                </div>
                                                {s.cagr && (
                                                    <div className={`px-3 py-1 rounded-full text-sm font-semibold ${s.cagr > 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                                                        {(s.cagr * 100).toFixed(2)}% CAGR
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-gray-500 text-center py-4">No sales history available</p>
                            )}
                        </div>

                        {/* More Details (Expandable) */}
                        <div className="bg-gray-50 rounded-xl p-6">
                            <button
                                onClick={() => setShowMoreDetails(!showMoreDetails)}
                                className="w-full flex justify-between items-center text-left"
                            >
                                <h3 className="text-lg font-semibold text-gray-800">More Details</h3>
                                {showMoreDetails ? (
                                    <ChevronUp size={20} className="text-gray-600" />
                                ) : (
                                    <ChevronDown size={20} className="text-gray-600" />
                                )}
                            </button>

                            {showMoreDetails && (
                                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div>
                                        <p className="text-xs font-semibold text-gray-500 uppercase">Zoning</p>
                                        <p className="text-sm text-gray-800">{sale.zoning || 'N/A'}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs font-semibold text-gray-500 uppercase">Nature of Property</p>
                                        <p className="text-sm text-gray-800">{sale.nature_of_property || 'N/A'}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs font-semibold text-gray-500 uppercase">Area</p>
                                        <p className="text-sm text-gray-800">{sale.area ? `${sale.area} ${sale.area_type}` : 'N/A'}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs font-semibold text-gray-500 uppercase">Property Type</p>
                                        <p className="text-sm text-gray-800">{sale.primary_purpose || 'N/A'}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs font-semibold text-gray-500 uppercase">Dealing Number</p>
                                        <p className="text-sm text-gray-800">{sale.dealing_number || 'N/A'}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs font-semibold text-gray-500 uppercase">Strata Lot Number</p>
                                        <p className="text-sm text-gray-800">{sale.strata_lot_number || 'N/A'}</p>
                                    </div>
                                    <div className="md:col-span-2">
                                        <p className="text-xs font-semibold text-gray-500 uppercase">Legal Description</p>
                                        <p className="text-sm text-gray-800">{sale.property_legal_description || 'N/A'}</p>
                                    </div>
                                    {sale.nearest_station && (
                                        <>
                                            <div>
                                                <p className="text-xs font-semibold text-gray-500 uppercase">Nearest Station</p>
                                                <p className="text-sm text-gray-800">{sale.nearest_station}</p>
                                            </div>
                                            <div>
                                                <p className="text-xs font-semibold text-gray-500 uppercase">Distance to Station</p>
                                                <p className="text-sm text-gray-800">{sale.distance_to_station?.toFixed(2)} km</p>
                                            </div>
                                        </>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default PropertyDetailModal;
