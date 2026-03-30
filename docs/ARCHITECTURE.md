COMPREHENSIVE PROPERTY ANALYTICS SYSTEM - TECHNICAL SPECIFICATION
DOCUMENT PURPOSE
Complete technical specification of the PropRoo property analytics platform including data models, ETL pipelines, calculation algorithms, API contracts, and UI data consumption patterns.
1. DATA MODEL LAYER
1.1 Source Data Schema (External)
Source: NSW Valuer General Property Sales  
Format: Yearly ZIP archives containing CSV files with pipe (|) delimiters  
Path: https://www.valuergeneral.nsw.gov.au/__psi/yearly/{YEAR}.zip
CSV Structure (per yearly file):
Column Name	Data Type
property_id	INTEGER
property_street_number	VARCHAR(10)
property_street_name	VARCHAR(100)
property_locality	VARCHAR(50)
property_post_code	INTEGER
property_type	CHAR(1)
purchase_price	DECIMAL(15,2)
contract_date	DATE
settlement_date	DATE
nature_of_property	CHAR(1)
primary_purpose	VARCHAR(50)
area	DECIMAL(10,2)
area_type	CHAR(1)
zoning	VARCHAR(10)
latitude	DECIMAL(10,8)
longitude	DECIMAL(11,8)
realestate_url	VARCHAR(500)
domain_url	VARCHAR(500)
zoning	VARCHAR(10)
nature_of_property	CHAR(1)
1.2 Internal Data Model (PostgreSQL)
Core Entity: sale
CREATE TABLE sale (
    id SERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL REFERENCES sale(property_id),
    property_id INTEGER NOT NULL,
    property_street_number VARCHAR(10),
    property_street_name VARCHAR(100),
    property_locality VARCHAR(50),
    property_post_code INTEGER CHECK (property_post_code BETWEEN 0 AND 9999),
    property_type CHAR(1) CHECK (property_type IN ('R','C','I','V')),
    purchase_price DECIMAL(15,2) NOT NULL CHECK (purchase_price >= 0),
    contract_date DATE NOT NULL,
    settlement_date DATE,
    nature_of_property CHAR(1),
    primary_purpose VARCHAR(50),
    area DECIMAL(10,2) CHECK (area >= 0),
    area_type CHAR(1) CHECK (area_type IN ('H','M')),
    zoning VARCHAR(10),
    latitude DECIMAL(10,8) CHECK (latitude BETWEEN -90 AND 90),
    longitude DECIMAL(11,8) CHECK (longitude BETWEEN -180 AND 180),
    realestate_url VARCHAR(500),
    domain_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Indexes for query performance
CREATE INDEX idx_sale_property_id ON sale(property_id);
CREATE INDEX idx_sale_contract_date ON sale(contract_date);
CREATE INDEX idx_sale_locality_postcode ON sale(property_locality, property_post_code);
CREATE INDEX idx_sale_type_price ON sale(property_type, purchase_price);
CREATE INDEX idx_sale_zoning ON sale(zoning);
Derived Analytics Tables
property_growth - Year-over-year property level growth metrics
CREATE TABLE property_growth (
    id SERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL REFERENCES sale(property_id),
    suburb VARCHAR(50) NOT NULL,
    street_name VARCHAR(100) NOT NULL,
    post_code INTEGER NOT NULL CHECK (post_code BETWEEN 0 AND 9999),
    year INTEGER NOT NULL CHECK (year BETWEEN 1900 AND 2100),
    avg_cagr DECIMAL(10,6) NOT NULL,
    total_growth DECIMAL(10,6) NOT NULL,
    years_held INTEGER NOT NULL CHECK (years_held >= 0),
    last_sale_price DECIMAL(15,2) NOT NULL CHECK (last_sale_price >= 0),
    first_sale_price DECIMAL(15,2) NOT NULL CHECK (first_sale_price >= 0),
    last_sale_year INTEGER NOT NULL CHECK (last_sale_year BETWEEN 1900 AND 2100),
    first_sale_year INTEGER NOT NULL CHECK (first_sale_year BETWEEN 1900 AND 2100),
    property_street_name VARCHAR(100) NOTNULL,
    property_locality VARCHAR(50) NOTNULL,
    property_post_code INTEGER NOT NULL CHECK (property_post_code BETWEEN 0 AND 9999),
    UNIQUE (property_id, suburb, street_name, post_code, year)
);
CREATE INDEX idx_property_growth_property_id ON property_growth(property_id);
CREATE INDEX idx_property_growth_year_suburb ON property_growth(year, suburb);
CREATE INDEX idx_property_growth_avg_cagr ON property_growth(avg_cagr);
street_growth - Street-level year-over-year growth metrics  
(Similar structure to property_growth but at street level)
street_summary - Current street-level snapshot  
CREATE TABLE street_summary (
    id SERIAL PRIMARY KEY,
    street_name VARCHAR(100) NOT NULL,
    suburb VARCHAR(50) NOT NULL,
    post_code INTEGER NOT NULL CHECK (post_code BETWEEN 0 AND 9999),
    unique_properties INTEGER NOT NULL CHECK (unique_properties >= 0),
    total_sales INTEGER NOT NULL CHECK (total_sales >= 0),
    avg_cagr DECIMAL(10,6) NOT NULL,
    property_count INTEGER NOT NULL CHECK (property_count >= 0),
);
CREATE UNIQUE INDEX idx_street_summary_location ON street_summary(street_name, suburb, post_code);
suburb_growth - Suburb-level year-over-year growth metrics  
(Analogous to property_growth at suburb level)
suburb_summary - Current suburb-level snapshot  
CREATE TABLE suburb_summary (
    id SERIAL PRIMARY KEY,
    suburb VARCHAR(50) NOT NULL,
    unique_properties INTEGER NOT NULL CHECK (unique_properties >= 0),
    total_sales INTEGER NOT NULL CHECK (total_sales >= 0),
    avg_cagr DECIMAL(10,6) NOT NULL,
    property_count INTEGER NOT NULL CHECK (property_count >= 0),
);
unified_map - Geospatial clustering for map visualization  
CREATE TABLE unified_map (
    id SERIAL PRIMARY KEY,
    cluster_id INTEGER NOT NULL,
    latitude DECIMAL(10,8) NOTNULL,
    longitude DECIMAL(11,8) NOTNULL,
    property_count INTEGER NOT NULL CHECK (property_count >= 0),
    avg_cagr DECIMAL(10,6) NOTNULL,
    year INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2025),
    level VARCHAR(20) NOTNULL CHECK (level IN ('property','street','suburb')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_unified_map_location ON unified_map(latitude, longitude);
CREATE INDEX idx_unified_map_year_level ON unified_map(year, level);
2. ETL PIPELINE LAYER
2.1 Ingestion Pipeline (ingest_2024.py)
Stages:
1. Download Phase
   - Iterates years from --start-year to --end-year (inclusive)
   - Constructs URL: https://www.valuergeneral.nsw.gov.au/__psi/yearly/{YEAR}.zip
   - Downloads to temporary directory (/tmp/downloads/ for PostgreSQL deployments)
   - Validates HTTP 200 response, skips 404 (missing years)
   - Extracts ZIP in memory using zipfile module
   - Reads CSV with pandas.read_csv(..., sep='|')
2. Transformation Phase
   - Converts contract_date to datetime: pd.to_datetime()
   - Converts purchase_price to numeric: pd.to_numeric(), errors='coerce'
   - Drops rows where either conversion fails: df.dropna(subset=['purchase_price', 'contract_date'])
   - Extracts sale year: df['sale_year'] = df['contract_date'].dt.year
3. Loading Phase - Property Table
   - Upserts into sale table using psycopg2.extras.execute_values()
   - Batch size: 10,000 records per transaction
   - Progress logging every 50,000 records
   - Final commit after all records processed
4. Analytics Phase (triggered automatically after ingestion):
   - Property level growth calculation
   - Street level growth calculation  
   - Suburb level growth calculation
   - Summary table generation
   - Unified map clustering (k-means on lat/lng)
2.2 Ingestion SQL Pattern
For property table upsert:
INSERT INTO sale (
    property_id, property_street_number, property_street_name, property_locality, 
    property_post_code, property_type, purchase_price, contract_date, settlement_date,
    nature_of_property, primary_purpose, area, area_type, zoning, 
    latitude, longitude, realestate_url, domain_url
) VALUES %s
-- Using psycopg2.extras.execute_values with list of tuples
-- Batch committed every 5000-10000 records
3. CALCULATION ALGORITHM LAYER
3.1 Compound Annual Growth Rate (CAGR)
Location: app/analytics.py::calculate_cagr()
Mathematical Formula:
CAGR = (Ending Value / Beginning Value)^(1 / Years) - 1
Total Growth = (Ending Value - Beginning Value) / Beginning Value
Edge Cases:
- Years < 0.5 (less than 6 months): Return (0.0, Total Growth) - ignores CAGR for short holdings
- Division by zero: Handled via try/except, returns (0.0, 0.0)  
- Overflow/Underflow: Handled via try/except, returns (0.0, 0.0)  
- Overflow/Underflow: Handled via try/except, returns (0.0, 0.0)  
- Overflow/Underflow: Handled via try/except, returns (0.0, 0.0)  
- Overflow/Underflow: Handled via try/except, returns (0.0, 0.0)  
- Overflow/Underflow: Handled via try/except, returns (0.0, 0.0)  
- Overflow/Underflow: Handled via try/except, returns (0.0, 0.0)  
Python Implementation:
def calculate_cagr(first_price: float, last_price: float, years: float) -> Tuple[float, float]:
    """
    Calculate Compound Annual Growth Rate (CAGR) and total growth.
    
    Args:
        first_price: Price at the start of the period
        last_price: Price at the end of the period  
        years: Number of years between sales
        
    Returns:
        Tuple of (cagr, total_growth)
    """
    if years < 0.5:  # Ignore if held for less than 6 months for CAGR purposes
        return 0.00 (last_price - first_price) / first_price
    
    try:
        cagr = ((last_price / first_price) ** (1 / years)) - 1
    except (ZeroDivisionError, OverflowError) as e:
        logger.error(f"Error calculating CAGR: {e})
        cagr = 0.0
    
    total_growth = (last_price - first_price) / first_price
    return cagr, total_growth
3.2 Growth Calculation Pipeline (calculate_growth_metrics())
Execution Flow:
1. Load all sales: df = pd.read_sql(query, db.bind)
2. Validate data types: Convert dates/prices, drop invalid rows
3. Add sale_year column: df['sale_year'] = df['contract_date'].dt.year
4. Property Level Processing:
   - Group by property_id
   - Skip groups with < 2 sales (need at least 2 points for growth)
   - For each property:
     * Extract first/last sale by chronological order
     * Calculate years held: (last_date - first_date).days / 365.25
     * Calculate CAGR and total growth using calculate_cagr()
     * Store: property_id, CAGR, total_growth, years_held, first/last prices, property details
5. Save Property Growth: Truncate table, bulk insert results
6. Per-Year Aggregation (Street/Suburb):
   - For each year in range (typically 2001-current):
     * Filter: year_active_df = growth_df[growth_df['last_sale_year'] >= year]
     * Skip if no active properties in year
     * Street Level: Group by [property_street_name, property_locality, property_post_code]
       → Aggregate: avg_cagr=mean(cagr), property_count=count(property_id)
     * Suburb Level: Group by [property_locality]  
       → Aggregate: avg_cagr=mean(cagr), property_count=count(property_id)
7. Overall Summary:
   - Street Summary: Group by street address → unique_properties=count(distinct property_id), total_sales=count(id)
   - Suburb Summary: Group by suburb → unique_properties=count(distinct property_id), total_sales=count(id)
   - Leaderboards: 
     * Sales Activity: Group properties by locality/street, count sales per year
     * Top Performers: Filter by top 10% CAGR using .quantile(0.9)
8. Bulk Insert Results: Truncate tables, insert calculated results in batches
4. API CONTRACT LAYER
4.1 Base URL Convention
All endpoints prefixed with /api  
Base URL: https://{hostname}/api  
Health check: GET /api/health → {"status": "ok"}
4.2 Sales Endpoints
GET /api/sales?limit={int}&offset={int}  
- Returns: Array of sale objects  
- Fields: All sale table columns  
- Pagination: Limit/offset based  
- Sorting: Default by contract_date ascending  
4.3 Statistics Endpoints  
All under /api/stats/ prefix
Global Summary
GET /api/stats/global_summary?year={int}  
- Returns: Object with top_suburbs[], top_streets[] arrays  
- Each item: {suburb: string, avg_cagr: float, unique_properties: int, total_sales: int}
Top Performers  
GET /api/stats/top_performers?year={int}&property_type={string}  
- Returns: Object with growth containing suburbs[] and streets[] arrays  
- Each suburb/street item: {suburb/street_name: string, avg_cagr: float, property_count: int}  
- Includes activity object with sales counts by suburb/street  
- Property type filtering: Optional property_type parameter  
Unified Map  
GET /api/stats/unified_map?level={string}&year={int}  
- Returns: Object with clusters[] array  
- Each cluster: Array of property IDs belonging to cluster  
- Parameters: 
  - level: property|street|suburb (required)
  - year: Integer year (required)
Suburb Centroids  
GET /api/stats/suburb_centroids?year={int}  
- Returns: Object {} (empty for debugging)  
- Parameter: year: Integer year (required)
Neighbors Endpoints
GET /api/stats/neighbors/{suburbs|streets}?suburb={string}  
- Returns: Array of neighboring property objects  
- Each neighbor: {suburb: string, sales_count: int}  
- Parameters: suburb: Target suburb name (required)
5. UI DATA CONSUMPTION PATTERN
5.1 State Level (Homepage) - / Route
Initial Load: 
- GET /api/stats/global_summary?year=2024 (default year from selector)
- Populates state overview metrics
- Sets year selector to 2024 (default)
Component Mapping:
- State overview → Displays summary stats
- Year selector → Options 2020-2025, default 2024  
- CAGR performance chart → Charts top_suburbs[] avg_cagr values
- Transaction count chart → Charts top_streets[] total_sales values  
- Data table → Shows property entries from /api/sales?limit=100
- Price range slider → Bound by min/max purchase_price from sales data
- Category filter → Options from distinct property_type values  
5.2 Year Selection - / Route (POST implicitly via select)
Action: 
- SELECT OPTION on year dropdown
- GET /api/stats/global_summary?year={selected_year}  
- Triggers full dashboard refresh with new year data
5.3 Suburb Level Navigation - /{suburb} Route
Navigation Flow:
1. Click property row in data table (tbody tr)
2. Extract property_id from clicked row
3. GET /api/stats?property_id={id}&limit=1 → Gets specific property  
4. Extract: property_street_name, property_locality, property_post_code  
5. GET /api/stats/unified_map?level=street&year={current_year} → Gets cluster assignments  
6. Extract matched property IDs from cluster results  
7. Show map with only matched properties highlighted  
5.4 Street Level Navigation - /{suburb}/{street} Route
Navigation Flow:
1. Click suburb row in data table
2. Extract property_locality from clicked row  
3. GET /api/stats?property_locality={id}&limit=1 → Gets specific suburb properties  
4. Extract: property_street_name, property_post_code from property  
5. GET /api/stats/unified_map?level=street&year={current_year} → Gets street cluster assignments  
6. Extract matched property IDs from cluster results  
7. Show map with only matched properties highlighted  
5.5 Map Interactions
Cluster Marker Click:
1. Click cluster marker on map
2. Extract cluster_id from marker data  
3. GET /api/sales?cluster_id in (property_id list)&limit=100 → Gets properties in cluster  
4. "Drill Into Cluster" button: Navigates to suburb level showing properties in cluster  
5.6 Filters Sidebar
Category Filter:
1. Select property type from dropdown  
2. GET /api/stats/top_performers?year={current_year}&vehicle_type={selected_type}  
3. Update growth section with filtered results  
Year Filter:
1. Select year from dropdown  
2. GET /api/stats/top_performers?year={selected_year}&property_type={current_type}  
3. Update growth section with filtered results  
5.7 Error Handling
Loading State: 
- Shown during initial data fetch (await page.waitForLoadState('networkidle'))  
- Hidden when data received
Network Errors: 
- Handed globally by test suite  
- Expected: Failed to load resource (429)  
- Not considered critical failures  
6. TECHNICAL CONSTRAINTS
6.1 Data Freshness
- Source data updated weekly by NSW Valuer General  
- Ingestion pipeline can run on demand or scheduled  
- Analytics recalculated after each ingestion  
- API serves pre-calculated results (no runtime computation)
6.2 Performance Characteristics
- Ingestion: ~8-12 minutes for full history (2020-2026)  
- Analytics: ~2-3 minutes post-ingestion  
- API Response: <100ms for cached results  
- Concurrent Users: Limited by database connection pool  
6.3 Scalability Limits
- Maximum properties: ~1M+ records manageable  
- Maximum years: Unlimited (adds new columns to growth tables)  
- API Throughput: ~1K RPM with caching  
- Database Connections: 20-50 pool size recommended  
7. DEPLOYMENT SPECIFICS
7.1 Environment Variables
DATABASE_URL=postgresql://proproo_user:YOcwrcWxWUc01MNYKhsHcjyHVYLoEDSn@dpg-d73f9p6uk2gs73cptno0-a.singapore-postgres.render.com/proproo
PYTHON_VERSION=3.12.0
DATA_DIR=/tmp
7.2 Resource Allocation
- Web Service: 1 CPU, 512MB RAM (Render free tier)
- Database: Shared PostgreSQL instance (Render managed)  
- Storage: Ephemeral (/tmp) for downloads, persistent (database) for data
8. FLOW VALIDATION POINTS
8.1 Ingestion Complete When
- Log shows: "Inserted 640000 / 640000 records into sale"
- DB query: SELECT COUNT(*) FROM sale; = 640000
8.2 Analytics Complete When  
- Log shows: "Inserted X / Y records into table" for all tables
- DB queries: All SELECT COUNT(*) FROM [table]; show expected counts
8.3 API Ready When  
- Health check: {"status": "ok", record_count": 640000}  
- Stats endpoints: Return expected data structures, not empty arrays  
8.4 UI Ready When  
- Dashboard loads without network errors  
- Charts show data (not empty)  
- Filters return results (not empty)  
- Map shows clusters (not empty)  
9. EXTENSION POINTS
9.1 Additional Data Sources
- Domain.com.au and Realestate.com.au listing URLs already captured  
- Could integrate: Auction results, rental yield data, demographic statistics  
9.2 Additional Analytics  
- Vacancy rates, time-on-market, price per square foot  
- Portfolio-level analytics (aggregated across properties)  
- Risk metrics (price volatility, value at risk)  
9.3 Additional API Endpoints  
- /api/properties/{id}/history - Time series for specific property  
- /api/analytics/volatility - Price volatility metrics  
- /api/analytics/portfolio - Aggregated portfolio performance  
9.4 UI Enhancements  
- Property detail pages (drill-down from search results)  
- Comparison tools (side-by-side property analysis)  
- Export capabilities (CSV/Excel download)  
- Alert management (save searches, notification preferences)  
END OF TECHNICAL SPECIFICATION  
Document generated: 2026-03-28  
System: PropRoo Property Analytics Platform  
Version: 1.0.0-production  