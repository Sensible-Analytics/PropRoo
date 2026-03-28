export interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

export interface H3FeatureProperties {
  h3_index: string;
  property_count: number;
  avg_cagr: number;
  avg_price: number;
  last_sale: string;
  suburb?: string;
}

export interface H3Feature {
  type: 'Feature';
  geometry: {
    type: 'Polygon';
    coordinates: number[][][];
  };
  properties: H3FeatureProperties;
}

export interface H3FeatureCollection {
  type: 'FeatureCollection';
  features: H3Feature[];
}

export interface SuburbSummary {
  suburb: string;
  post_code?: number;
  avg_cagr: number;
  unique_properties: number;
  total_sales: number;
}

export interface StreetSummary {
  street_name: string;
  suburb: string;
  post_code?: number;
  avg_cagr: number;
  total_sales: number;
}

export interface GlobalSummary {
  top_suburbs: SuburbSummary[];
  top_streets: StreetSummary[];
  year: number;
}

export interface SaleRecord {
  id: number;
  property_id: string;
  property_locality: string;
  property_street_name: string;
  property_house_number?: string;
  purchase_price: number;
  contract_date: string;
  primary_purpose: string;
  latitude: number;
  longitude: number;
  cagr?: number;
}

export interface ClusterData {
  id: string;
  name: string;
  lat: number;
  lon: number;
  rank: number;
  cagr: number;
  neighbors: Array<{
    name: string;
    lat: number;
    lon: number;
    cagr: number;
  }>;
}

export interface UnifiedMapData {
  clusters: ClusterData[];
}