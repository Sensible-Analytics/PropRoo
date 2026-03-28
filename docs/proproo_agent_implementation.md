# PropRoo — AI Agent Implementation Guide
## Technology Stack, Architecture, and Complete Build Instructions

**System:** PropRoo Property Analytics Platform  
**Source Data:** NSW Valuer General Property Sales  
**Agent Target:** Fully autonomous implementation from zero to deployed  
**Date:** 2026-03-28

---

## Part 1 — Technology Decisions

---

### 1.1 Map Library Decision

The centrepiece of PropRoo is the geospatial view. 640,000+ property points need to render, cluster, and re-render on pan/zoom without freezing the browser. Three libraries are evaluated.

#### Option A: deck.gl + MapLibre GL JS (Recommended)

**Why deck.gl:**  
deck.gl renders on the GPU via WebGL. At 640,000 points it renders in under 16ms per frame (60fps). React Leaflet and Google Maps render on the CPU via DOM/Canvas and will freeze at this data volume. deck.gl is the library used by Uber, Airbnb, and the NSW government's own spatial tools.

**Why MapLibre GL JS as the base map:**  
MapLibre is the open-source fork of Mapbox GL JS v1. It has no API key requirement, no per-tile pricing, and no usage caps. Mapbox charges per map load after 50,000/month. For a property analytics app with repeat users doing long sessions, Mapbox costs will compound quickly. MapLibre uses free tile sources (OpenStreetMap via Stadia Maps, or self-hosted PMTiles).

**Cost:**
- MapLibre tiles via Stadia Maps free tier: 200,000 tile requests/month free
- deck.gl: MIT licence, zero cost
- Total map cost: $0/month up to ~20,000 sessions/month

```
Stack:
  deck.gl          — GPU-accelerated WebGL layer rendering
  MapLibre GL JS   — base map tiles and viewport management
  @deck.gl/react   — React bindings
```

**Key layers for PropRoo:**
- `HeatmapLayer` — CAGR density heatmap at suburb level (low zoom)
- `ScatterplotLayer` — individual property dots at street level (high zoom)
- `GeoJsonLayer` — suburb polygon fills coloured by avg_cagr (choropleth)
- `TextLayer` — suburb name labels at mid zoom

#### Option B: Mapbox GL JS

Same WebGL rendering as MapLibre (same codebase pre-fork). Better documentation, paid support available. Cost: $0.50 per 1,000 map loads after 50,000 free. For a production app with 500 users doing 10 sessions each per month = 5,000 loads = free. Becomes expensive above 50,000 loads. Use if budget allows or team wants commercial support.

#### Option C: React Leaflet + Leaflet.markercluster

CPU-based rendering. Handles up to ~10,000 markers before visible lag. Fast to implement, large community, extensive plugins. For PropRoo at 640,000 records this will freeze the browser at any zoom level that shows property-level data. Only viable if map always shows suburb-level aggregates and never individual properties.

**Decision: deck.gl + MapLibre GL JS.** Zero licensing cost, GPU rendering, handles full dataset. If the team needs faster initial delivery, start with React Leaflet at suburb level only and migrate to deck.gl when street/property level views are added.

---

### 1.2 Backend Database Decision

The current spec uses PostgreSQL. It works but has three friction points for this use case: geospatial queries require PostGIS extension (not available on Render free tier), analytical aggregations (avg_cagr, quantile filtering) are slow on row-oriented storage at 640k+ rows, and the Render free instance pauses after 15 minutes of inactivity causing 30-second cold start delays.

Four alternatives evaluated:

#### Option A: DuckDB + Parquet on object storage (Recommended for cost)

**What it is:** DuckDB is an in-process analytical database (like SQLite but columnar). It runs inside the Python process with zero server overhead. Data lives in Parquet files on Cloudflare R2 (S3-compatible, zero egress cost).

**Why it fits PropRoo's query pattern:**  
PropRoo's queries are almost entirely analytical: `GROUP BY suburb`, `AVG(cagr)`, `QUANTILE(price, 0.9)`, bounding box filters. These are OLAP queries, not OLTP. DuckDB executes these 10-100x faster than PostgreSQL on equivalent hardware because it reads only the columns needed (columnar) and parallelises across CPU cores automatically.

**Query example — top suburbs by CAGR:**
```sql
-- PostgreSQL on Render free tier: ~800ms
-- DuckDB on same data in Parquet: ~40ms
SELECT suburb, AVG(avg_cagr) as cagr, COUNT(*) as sales
FROM read_parquet('s3://proproo/property_growth/*.parquet')
GROUP BY suburb
ORDER BY cagr DESC
LIMIT 20
```

**Geospatial support:** DuckDB has a `spatial` extension that supports bounding box queries, distance calculations, and H3 hexagonal indexing natively.

**Cost:**
- DuckDB: free, embedded in Python process
- Cloudflare R2: $0.015/GB storage, zero egress fees (unlike AWS S3 which charges $0.09/GB egress)
- 640,000 records as Parquet: ~80MB compressed = $0.0012/month storage
- Total: ~$0/month

**Limitation:** Not suitable for concurrent writes. If multiple ETL runs overlap, use file locking. For PropRoo's weekly ingestion cadence this is not a problem.

```
Architecture with DuckDB:
  ETL (Python) → Parquet files → Cloudflare R2
  API (Flask/FastAPI) → DuckDB reads Parquet from R2 on query
  No database server process, no connection pool management
```

#### Option B: PostgreSQL + TimescaleDB on Supabase free tier

**What it is:** Supabase provides managed PostgreSQL with PostGIS extension included, 500MB storage, and no cold-start pauses (unlike Render free tier). TimescaleDB adds time-series optimisation for the yearly growth tracking queries.

**Why it fits:** PropRoo already has PostgreSQL DDL written. Migration effort is low — just change `DATABASE_URL` to Supabase connection string. PostGIS enables `ST_Within`, `ST_Distance`, and proper spatial indexes.

**Cost:**
- Supabase free tier: 500MB database, 2 CPU, no pauses
- PostGIS: included
- Total: $0/month (upgrade to $25/month Pro when data exceeds 500MB)

**Best choice if:** The team wants to keep existing PostgreSQL DDL and add proper PostGIS geospatial support without rewriting anything.

#### Option C: ClickHouse Cloud free tier

**What it is:** ClickHouse is a column-oriented database purpose-built for analytical queries. It is what powers many large-scale analytics platforms.

**Query performance:** For `GROUP BY` + `AVG` + `ORDER BY` on 640,000 rows, ClickHouse is typically 50-200x faster than PostgreSQL. The same query that takes 800ms on Render PostgreSQL takes 5-15ms on ClickHouse.

**Cost:**
- ClickHouse Cloud free tier: 1M rows free, then pay-per-query
- For 640,000 property records: free
- Total: $0/month up to ~5M rows

**Limitation:** No PostGIS. Geospatial support is via `pointInPolygon()` and H3 functions, which require data pre-processing. More setup effort than Supabase.

#### Option D: SQLite + Litestream (simplest, lowest cost)

**What it is:** SQLite database file replicated in real-time to S3/R2 via Litestream. The entire database is a single file on the server's disk.

**Why it works:** SQLite handles read-heavy workloads extremely well. PropRoo's API is almost entirely reads. Benchmarks show SQLite outperforming PostgreSQL for read-only workloads with fewer than 10 concurrent writers.

**Cost:** SQLite is free. Litestream is free. R2 storage for a 300MB SQLite file = $0.004/month.

**Limitation:** No analytical query optimisation. Aggregations on 640k rows will still be slow. No spatial extension as capable as PostGIS.

#### Database Decision Matrix

| Database | Analytical Speed | Geospatial | Free Tier | Migration Effort | Recommended For |
|---|---|---|---|---|---|
| DuckDB + R2 Parquet | Excellent | Good (spatial ext) | $0 always | High (rewrite ETL) | Cost-first, analytical-heavy |
| Supabase PostgreSQL | Good | Excellent (PostGIS) | $0 to 500MB | Low (change DB URL) | Fastest path to production |
| ClickHouse Cloud | Excellent | Moderate | $0 to 5M rows | Medium | Scale-first |
| SQLite + Litestream | Moderate | Poor | $0 always | Medium | Simplest ops |

**Recommendation: Supabase PostgreSQL for initial deployment, DuckDB + Parquet for analytics queries once data exceeds 500MB.**

The hybrid approach: use Supabase for the `sale` table (transactional writes during ingestion) and export to Parquet on R2 after each ingestion for all analytical queries. Flask routes that serve the map and stats endpoints query DuckDB against Parquet. Flask routes that serve raw sales data query Supabase PostgreSQL. This gives PostGIS for geospatial and DuckDB speed for analytics, both at zero cost.

---

### 1.3 Full Recommended Stack

| Layer | Technology | Cost | Reason |
|---|---|---|---|
| Frontend framework | React + Vite | $0 | Fast HMR, small bundles |
| Map rendering | deck.gl + MapLibre GL JS | $0 | GPU rendering, no API key |
| Map tiles | Stadia Maps (free tier) | $0 | 200k tile requests/month free |
| Geospatial indexing | H3 (Uber's hexagonal grid) | $0 | Deterministic clustering at any zoom |
| Charting | Recharts | $0 | React-native, lightweight |
| State management | Zustand | $0 | Simpler than Redux for this scale |
| API framework | FastAPI (Python) | $0 | Auto OpenAPI docs, async support |
| Analytics queries | DuckDB | $0 | Columnar, runs in-process |
| Transactional DB | Supabase PostgreSQL | $0 | PostGIS, no cold starts |
| File storage | Cloudflare R2 | $0 | Zero egress, S3-compatible |
| ETL | Python + pandas + psycopg2 | $0 | Existing, extend for Parquet export |
| Hosting — API | Render free tier | $0 | Existing |
| Hosting — Frontend | Cloudflare Pages | $0 | 500 builds/month free, global CDN |
| Caching | Redis via Upstash | $0 | 10,000 requests/day free tier |

**Total infrastructure cost: $0/month for the first ~20,000 monthly active users.**

---

## Part 2 — Architecture

---

### 2.1 System Architecture

```
NSW Valuer General (weekly ZIP)
         |
         v
   ETL Pipeline (Python)
         |
    ┌────┴─────────────┐
    |                  |
    v                  v
Supabase PostgreSQL   Parquet files
(sale table,          on Cloudflare R2
 raw ingestion)       (analytics export)
    |                  |
    └────────┬─────────┘
             |
        FastAPI backend
             |
    ┌────────┴────────┐
    |                 |
    v                 v
DuckDB (analytics)   PostGIS queries
(reads Parquet       (geospatial bounds,
 from R2)            suburb polygons)
    |
    v
Redis (Upstash)
(response cache,
 5-minute TTL)
    |
    v
React + deck.gl frontend
(Cloudflare Pages)
```

### 2.2 Data Flow

```
Ingestion:
  1. Download ZIP from NSW VG → /tmp/
  2. Parse CSV → pandas DataFrame
  3. Upsert to Supabase sale table (psycopg2)
  4. Export to Parquet → Cloudflare R2 (pyarrow)
  5. Recalculate analytics tables → Supabase
  6. Export analytics to Parquet → R2
  7. Invalidate Redis cache

Query (hot path):
  Browser request
  → FastAPI endpoint
  → Redis cache check (hit: return in <5ms)
  → Cache miss: DuckDB reads Parquet from R2
  → Result stored in Redis (5 min TTL)
  → Response to browser

Geospatial query:
  Map viewport change event
  → POST /api/map/viewport {min_lat, max_lat, min_lng, max_lng, zoom, year}
  → H3 resolution selected based on zoom level
  → DuckDB spatial query on Parquet
  → GeoJSON response
  → deck.gl renders on GPU
```

---

## Part 3 — Complete File Structure

```
proproo/
├── backend/
│   ├── app/
│   │   ├── main.py                 ← FastAPI app entry point
│   │   ├── config.py               ← env vars, constants
│   │   ├── database.py             ← Supabase + DuckDB connections
│   │   ├── cache.py                ← Redis (Upstash) wrapper
│   │   ├── analytics.py            ← CAGR + growth calculations
│   │   ├── h3_utils.py             ← H3 hexagonal indexing helpers
│   │   └── routers/
│   │       ├── sales.py            ← /api/sales endpoints
│   │       ├── stats.py            ← /api/stats endpoints
│   │       └── map.py              ← /api/map endpoints
│   ├── etl/
│   │   ├── ingest.py               ← download + parse + upsert
│   │   ├── export_parquet.py       ← Supabase → Parquet → R2
│   │   └── calculate_growth.py     ← analytics recalculation
│   ├── tests/
│   │   ├── test_analytics.py
│   │   ├── test_api.py
│   │   └── fixtures/
│   │       └── sample_sales.csv
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── store/
│   │   │   └── useAppStore.ts      ← Zustand store
│   │   ├── components/
│   │   │   ├── Map/
│   │   │   │   ├── PropRooMap.tsx  ← deck.gl + MapLibre root
│   │   │   │   ├── HeatmapLayer.tsx
│   │   │   │   ├── ScatterLayer.tsx
│   │   │   │   └── ChoroLayer.tsx  ← suburb choropleth
│   │   │   ├── Charts/
│   │   │   │   ├── CagrChart.tsx
│   │   │   │   └── SalesChart.tsx
│   │   │   ├── Sidebar/
│   │   │   │   ├── FilterPanel.tsx
│   │   │   │   └── StatsPanel.tsx
│   │   │   └── Table/
│   │   │       └── SalesTable.tsx
│   │   ├── hooks/
│   │   │   ├── useMapData.ts       ← viewport-bound data fetching
│   │   │   ├── useStats.ts
│   │   │   └── useDebounce.ts
│   │   ├── api/
│   │   │   └── client.ts           ← typed fetch wrapper
│   │   └── types/
│   │       └── index.ts            ← shared TypeScript types
│   ├── public/
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
├── docker-compose.yml              ← local dev stack
└── README.md
```

---

## Part 4 — Complete Implementation Instructions for AI Agent

**Execute every step in the order listed. Do not skip steps. Do not proceed to the next step until the current step is verified.**

---

### Step 1 — Repository and Environment Setup

```bash
# 1.1 Create project directory
mkdir proproo && cd proproo
git init

# 1.2 Create backend Python environment
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 1.3 Create requirements.txt with exact versions
cat > requirements.txt << 'EOF'
fastapi==0.111.0
uvicorn[standard]==0.29.0
psycopg2-binary==2.9.9
pandas==2.2.2
pyarrow==16.0.0
duckdb==0.10.3
boto3==1.34.0          # for Cloudflare R2 (S3-compatible)
h3==3.7.7              # Uber H3 hexagonal indexing
redis==5.0.4            # Upstash Redis client
python-dotenv==1.0.1
httpx==0.27.0
pydantic==2.7.0
pydantic-settings==2.2.1
pytest==8.2.0
pytest-asyncio==0.23.6
EOF

pip install -r requirements.txt
```

**Verify:**
```bash
python -c "import fastapi, duckdb, h3, redis; print('All imports OK')"
```

---

### Step 2 — Environment Variables

```bash
# Create backend/.env
cat > .env << 'EOF'
# Supabase
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@[YOUR-PROJECT].supabase.co:5432/postgres

# Cloudflare R2 (S3-compatible)
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_BUCKET_NAME=proproo-data
R2_ENDPOINT=https://[ACCOUNT_ID].r2.cloudflarestorage.com

# Upstash Redis
REDIS_URL=rediss://default:[TOKEN]@[HOST].upstash.io:6380

# App
PYTHON_VERSION=3.12.0
DATA_DIR=/tmp
ENVIRONMENT=development
EOF
```

---

### Step 3 — Database Schema (Supabase)

Connect to your Supabase project's SQL editor and run the following. Execute each block separately and verify it succeeds before continuing.

```sql
-- Block 1: Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Block 2: Core sale table (corrected from spec — no duplicate columns, no self-ref FK)
CREATE TABLE IF NOT EXISTS sale (
    id                      SERIAL PRIMARY KEY,
    property_id             INTEGER NOT NULL,
    property_street_number  VARCHAR(10),
    property_street_name    VARCHAR(100),
    property_locality       VARCHAR(50),
    property_post_code      INTEGER CHECK (property_post_code BETWEEN 1000 AND 2999),
    property_type           CHAR(1) CHECK (property_type IN ('R','C','I','V')),
    purchase_price          DECIMAL(15,2) NOT NULL CHECK (purchase_price > 0),
    contract_date           DATE NOT NULL,
    settlement_date         DATE,
    nature_of_property      CHAR(1),
    primary_purpose         VARCHAR(50),
    area                    DECIMAL(10,2) CHECK (area >= 0),
    area_type               CHAR(1) CHECK (area_type IN ('H','M')),
    zoning                  VARCHAR(10),
    latitude                DECIMAL(10,8) CHECK (latitude BETWEEN -90 AND 90),
    longitude               DECIMAL(11,8) CHECK (longitude BETWEEN -180 AND 180),
    geom                    GEOGRAPHY(POINT, 4326),  -- PostGIS column
    realestate_url          VARCHAR(500),
    domain_url              VARCHAR(500),
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (property_id, contract_date)
);

-- Block 3: Indexes
CREATE INDEX IF NOT EXISTS idx_sale_property_id       ON sale(property_id);
CREATE INDEX IF NOT EXISTS idx_sale_contract_date     ON sale(contract_date DESC);
CREATE INDEX IF NOT EXISTS idx_sale_locality          ON sale(property_locality);
CREATE INDEX IF NOT EXISTS idx_sale_type_date         ON sale(property_type, contract_date DESC);
CREATE INDEX IF NOT EXISTS idx_sale_geom              ON sale USING GIST(geom);

-- Block 4: Trigger to auto-populate geom from lat/lng on insert
CREATE OR REPLACE FUNCTION set_geom()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.geom = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::geography;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sale_geom
    BEFORE INSERT OR UPDATE ON sale
    FOR EACH ROW EXECUTE FUNCTION set_geom();

-- Block 5: Analytics tables
CREATE TABLE IF NOT EXISTS property_growth (
    id                  SERIAL PRIMARY KEY,
    property_id         INTEGER NOT NULL,
    suburb              VARCHAR(50) NOT NULL,
    street_name         VARCHAR(100) NOT NULL,
    post_code           INTEGER NOT NULL,
    year                INTEGER NOT NULL,
    avg_cagr            DECIMAL(10,6) NOT NULL,
    total_growth        DECIMAL(10,6) NOT NULL,
    years_held          INTEGER NOT NULL CHECK (years_held >= 0),
    first_sale_price    DECIMAL(15,2) NOT NULL,
    last_sale_price     DECIMAL(15,2) NOT NULL,
    first_sale_year     INTEGER NOT NULL,
    last_sale_year      INTEGER NOT NULL,
    property_street_name VARCHAR(100) NOT NULL,
    property_locality   VARCHAR(50) NOT NULL,
    property_post_code  INTEGER NOT NULL,
    UNIQUE (property_id, year)
);

CREATE TABLE IF NOT EXISTS street_summary (
    id                SERIAL PRIMARY KEY,
    street_name       VARCHAR(100) NOT NULL,
    suburb            VARCHAR(50) NOT NULL,
    post_code         INTEGER NOT NULL,
    unique_properties INTEGER NOT NULL CHECK (unique_properties >= 0),
    total_sales       INTEGER NOT NULL CHECK (total_sales >= 0),
    avg_cagr          DECIMAL(10,6) NOT NULL,
    property_count    INTEGER NOT NULL CHECK (property_count >= 0),
    UNIQUE (street_name, suburb, post_code)
);

CREATE TABLE IF NOT EXISTS suburb_summary (
    id                SERIAL PRIMARY KEY,
    suburb            VARCHAR(50) NOT NULL,
    post_code         INTEGER NOT NULL,
    unique_properties INTEGER NOT NULL CHECK (unique_properties >= 0),
    total_sales       INTEGER NOT NULL CHECK (total_sales >= 0),
    avg_cagr          DECIMAL(10,6) NOT NULL,
    property_count    INTEGER NOT NULL CHECK (property_count >= 0),
    UNIQUE (suburb, post_code)
);

-- Verify all tables created
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
-- Expected: property_growth, sale, street_summary, suburb_summary
```

---

### Step 4 — Backend Core Files

#### Step 4.1 — config.py
```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url:        str
    r2_account_id:       str
    r2_access_key_id:    str
    r2_secret_access_key: str
    r2_bucket_name:      str
    r2_endpoint:         str
    redis_url:           str
    data_dir:            str = '/tmp'
    environment:         str = 'development'

    class Config:
        env_file = '.env'

settings = Settings()
```

#### Step 4.2 — database.py
```python
# backend/app/database.py
import duckdb
import boto3
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from app.config import settings

# PostgreSQL connection pool (Supabase)
pg_pool = ThreadedConnectionPool(
    minconn=2,
    maxconn=10,
    dsn=settings.database_url
)

def get_pg_conn():
    return pg_pool.getconn()

def release_pg_conn(conn):
    pg_pool.putconn(conn)

# DuckDB — in-process, one instance per worker
def get_duck_conn() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(database=':memory:')
    conn.execute("INSTALL httpfs; LOAD httpfs;")
    conn.execute("INSTALL spatial; LOAD spatial;")
    conn.execute(f"""
        SET s3_region='auto';
        SET s3_access_key_id='{settings.r2_access_key_id}';
        SET s3_secret_access_key='{settings.r2_secret_access_key}';
        SET s3_endpoint='{settings.r2_endpoint.replace("https://", "")}';
    """)
    return conn

# R2 client (S3-compatible)
def get_r2_client():
    return boto3.client(
        's3',
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name='auto',
    )
```

#### Step 4.3 — cache.py
```python
# backend/app/cache.py
import json
import hashlib
import redis as redis_lib
from functools import wraps
from app.config import settings

_redis = redis_lib.from_url(settings.redis_url, decode_responses=True)

DEFAULT_TTL = 300  # 5 minutes

def cache_key(*args, **kwargs) -> str:
    raw = json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()

def cached(ttl: int = DEFAULT_TTL):
    """Decorator for caching FastAPI endpoint results in Redis."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = f"proproo:{func.__name__}:{cache_key(*args, **kwargs)}"
            cached_val = _redis.get(key)
            if cached_val:
                return json.loads(cached_val)
            result = await func(*args, **kwargs)
            _redis.setex(key, ttl, json.dumps(result, default=str))
            return result
        return wrapper
    return decorator

def invalidate_all():
    """Call after ETL ingestion completes."""
    keys = _redis.keys('proproo:*')
    if keys:
        _redis.delete(*keys)
```

#### Step 4.4 — analytics.py
```python
# backend/app/analytics.py
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

def calculate_cagr(first_price: float, last_price: float, years: float) -> Tuple[float, float]:
    """
    Returns (cagr, total_growth).
    cagr = 0.0 if years < 0.5 (short hold, not meaningful for annualised rate).
    total_growth always calculated if first_price > 0.
    """
    if first_price <= 0:
        return 0.0, 0.0

    try:
        total_growth = (last_price - first_price) / first_price
    except ZeroDivisionError:
        return 0.0, 0.0

    if years < 0.5:
        return 0.0, total_growth

    try:
        cagr = ((last_price / first_price) ** (1.0 / years)) - 1.0
    except (ZeroDivisionError, OverflowError, ValueError) as e:
        logger.warning(f"CAGR calculation failed: price={first_price}/{last_price} years={years}: {e}")
        cagr = 0.0

    return cagr, total_growth
```

#### Step 4.5 — h3_utils.py
```python
# backend/app/h3_utils.py
import h3
from typing import Optional

# H3 resolution by map zoom level
# Lower zoom = larger hexagons = suburb level
# Higher zoom = smaller hexagons = property level
ZOOM_TO_H3_RES = {
    range(0,  8):  4,   # state/region level
    range(8,  11): 6,   # suburb level
    range(11, 13): 7,   # street level
    range(13, 22): 9,   # property level
}

def zoom_to_resolution(zoom: int) -> int:
    for zoom_range, res in ZOOM_TO_H3_RES.items():
        if zoom in zoom_range:
            return res
    return 7  # default

def lat_lng_to_h3(lat: float, lng: float, resolution: int) -> str:
    return h3.geo_to_h3(lat, lng, resolution)

def h3_to_boundary(h3_index: str) -> list[list[float]]:
    """Returns polygon boundary as [[lat,lng], ...] for GeoJSON."""
    return list(h3.h3_to_geo_boundary(h3_index, geo_json=True))
```

---

### Step 5 — ETL Pipeline

#### Step 5.1 — ingest.py
```python
# backend/etl/ingest.py
"""
Usage:
  python -m etl.ingest --start-year 2020 --end-year 2024
"""
import argparse
import io
import logging
import zipfile
from typing import Optional

import httpx
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from app.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://www.valuergeneral.nsw.gov.au/__psi/yearly/{year}.zip"
BATCH_SIZE = 10_000

UPSERT_SQL = """
    INSERT INTO sale (
        property_id, property_street_number, property_street_name,
        property_locality, property_post_code, property_type,
        purchase_price, contract_date, settlement_date,
        nature_of_property, primary_purpose, area, area_type,
        zoning, latitude, longitude, realestate_url, domain_url
    ) VALUES %s
    ON CONFLICT (property_id, contract_date)
    DO UPDATE SET
        purchase_price  = EXCLUDED.purchase_price,
        settlement_date = EXCLUDED.settlement_date,
        updated_at      = CURRENT_TIMESTAMP
"""

def download_year(year: int) -> Optional[pd.DataFrame]:
    url = BASE_URL.format(year=year)
    logger.info(f"Downloading {url}")
    try:
        resp = httpx.get(url, timeout=120, follow_redirects=True)
        if resp.status_code == 404:
            logger.warning(f"Year {year} not available (404)")
            return None
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.error(f"Download failed for {year}: {e}")
        return None

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        csv_files = [f for f in zf.namelist() if f.endswith('.csv')]
        if not csv_files:
            logger.error(f"No CSV in ZIP for {year}")
            return None
        with zf.open(csv_files[0]) as f:
            df = pd.read_csv(f, sep='|', low_memory=False)

    logger.info(f"Year {year}: {len(df)} raw rows")
    return df

def transform(df: pd.DataFrame) -> pd.DataFrame:
    df['contract_date']  = pd.to_datetime(df['contract_date'], errors='coerce')
    df['purchase_price'] = pd.to_numeric(df['purchase_price'], errors='coerce')
    df = df.dropna(subset=['purchase_price', 'contract_date'])
    df = df[df['purchase_price'] > 0]
    return df

def load(df: pd.DataFrame, conn):
    cols = [
        'property_id','property_street_number','property_street_name',
        'property_locality','property_post_code','property_type',
        'purchase_price','contract_date','settlement_date',
        'nature_of_property','primary_purpose','area','area_type',
        'zoning','latitude','longitude','realestate_url','domain_url'
    ]
    # Only keep columns that exist in source data
    df = df[[c for c in cols if c in df.columns]].copy()
    # Fill missing optional columns with None
    for c in cols:
        if c not in df.columns:
            df[c] = None

    records = [tuple(row) for row in df[cols].itertuples(index=False)]
    total = len(records)
    inserted = 0

    with conn.cursor() as cur:
        for i in range(0, total, BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            execute_values(cur, UPSERT_SQL, batch)
            inserted += len(batch)
            if inserted % 50_000 == 0:
                logger.info(f"Upserted {inserted} / {total} records into sale")
        conn.commit()

    logger.info(f"Inserted {total} / {total} records into sale")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start-year', type=int, default=2020)
    parser.add_argument('--end-year',   type=int, default=2024)
    args = parser.parse_args()

    conn = psycopg2.connect(settings.database_url)
    try:
        for year in range(args.start_year, args.end_year + 1):
            df = download_year(year)
            if df is None:
                continue
            df = transform(df)
            load(df, conn)
    finally:
        conn.close()

    logger.info("Ingestion complete. Running analytics...")
    from etl.calculate_growth import run_all
    run_all()

    logger.info("Exporting to Parquet...")
    from etl.export_parquet import export_all
    export_all()

    from app.cache import invalidate_all
    invalidate_all()
    logger.info("Cache invalidated. Pipeline complete.")

if __name__ == '__main__':
    main()
```

#### Step 5.2 — calculate_growth.py
```python
# backend/etl/calculate_growth.py
import logging
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from app.config import settings
from app.analytics import calculate_cagr

logger = logging.getLogger(__name__)
CHUNK_SIZE = 50_000

def run_all():
    conn = psycopg2.connect(settings.database_url)
    try:
        _calc_property_growth(conn)
        _calc_street_summary(conn)
        _calc_suburb_summary(conn)
    finally:
        conn.close()

def _calc_property_growth(conn):
    logger.info("Calculating property growth...")
    engine_url = settings.database_url
    import sqlalchemy
    engine = sqlalchemy.create_engine(engine_url)

    results = []
    query = "SELECT property_id, property_street_name, property_locality, property_post_code, purchase_price, contract_date FROM sale ORDER BY property_id, contract_date"

    for chunk in pd.read_sql(query, engine, chunksize=CHUNK_SIZE):
        chunk['contract_date'] = pd.to_datetime(chunk['contract_date'])
        for prop_id, group in chunk.groupby('property_id'):
            if len(group) < 2:
                continue
            g = group.sort_values('contract_date')
            first, last = g.iloc[0], g.iloc[-1]
            years = (last['contract_date'] - first['contract_date']).days / 365.25
            cagr, total_growth = calculate_cagr(
                float(first['purchase_price']),
                float(last['purchase_price']),
                years
            )
            results.append((
                int(prop_id),
                last['property_locality'],
                last['property_street_name'],
                int(last['property_post_code'] or 0),
                last['contract_date'].year,
                round(cagr, 6),
                round(total_growth, 6),
                int(years),
                float(first['purchase_price']),
                float(last['purchase_price']),
                first['contract_date'].year,
                last['contract_date'].year,
                last['property_street_name'],
                last['property_locality'],
                int(last['property_post_code'] or 0),
            ))

    staging = 'property_growth_staging'
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
        cur.execute(f"CREATE TABLE {staging} (LIKE property_growth INCLUDING ALL)")
        execute_values(cur, f"""
            INSERT INTO {staging} (
                property_id, suburb, street_name, post_code, year,
                avg_cagr, total_growth, years_held,
                first_sale_price, last_sale_price,
                first_sale_year, last_sale_year,
                property_street_name, property_locality, property_post_code
            ) VALUES %s
        """, results)
        cur.execute("ALTER TABLE property_growth RENAME TO property_growth_old")
        cur.execute(f"ALTER TABLE {staging} RENAME TO property_growth")
        cur.execute("DROP TABLE property_growth_old")
        conn.commit()

    logger.info(f"Property growth: {len(results)} records written")

def _calc_street_summary(conn):
    logger.info("Calculating street summary...")
    with conn.cursor() as cur:
        cur.execute("TRUNCATE street_summary")
        cur.execute("""
            INSERT INTO street_summary (street_name, suburb, post_code, unique_properties, total_sales, avg_cagr, property_count)
            SELECT
                s.property_street_name,
                s.property_locality,
                s.property_post_code,
                COUNT(DISTINCT s.property_id),
                COUNT(s.id),
                AVG(pg.avg_cagr),
                COUNT(DISTINCT pg.property_id)
            FROM sale s
            LEFT JOIN property_growth pg ON pg.property_id = s.property_id
            GROUP BY s.property_street_name, s.property_locality, s.property_post_code
            ON CONFLICT (street_name, suburb, post_code) DO UPDATE
            SET avg_cagr = EXCLUDED.avg_cagr,
                total_sales = EXCLUDED.total_sales
        """)
        conn.commit()

def _calc_suburb_summary(conn):
    logger.info("Calculating suburb summary...")
    with conn.cursor() as cur:
        cur.execute("TRUNCATE suburb_summary")
        cur.execute("""
            INSERT INTO suburb_summary (suburb, post_code, unique_properties, total_sales, avg_cagr, property_count)
            SELECT
                s.property_locality,
                s.property_post_code,
                COUNT(DISTINCT s.property_id),
                COUNT(s.id),
                AVG(pg.avg_cagr),
                COUNT(DISTINCT pg.property_id)
            FROM sale s
            LEFT JOIN property_growth pg ON pg.property_id = s.property_id
            GROUP BY s.property_locality, s.property_post_code
            ON CONFLICT (suburb, post_code) DO UPDATE
            SET avg_cagr = EXCLUDED.avg_cagr,
                total_sales = EXCLUDED.total_sales
        """)
        conn.commit()
```

#### Step 5.3 — export_parquet.py
```python
# backend/etl/export_parquet.py
"""Exports Supabase tables to Parquet on Cloudflare R2 after ingestion."""
import io
import logging
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import sqlalchemy
from app.config import settings
from app.database import get_r2_client

logger = logging.getLogger(__name__)

TABLES = ['sale', 'property_growth', 'street_summary', 'suburb_summary']

def export_all():
    engine = sqlalchemy.create_engine(settings.database_url)
    r2 = get_r2_client()
    for table in TABLES:
        _export_table(engine, r2, table)

def _export_table(engine, r2_client, table: str):
    logger.info(f"Exporting {table} to Parquet...")
    df = pd.read_sql(f"SELECT * FROM {table}", engine)
    buffer = io.BytesIO()
    pq.write_table(
        pa.Table.from_pandas(df),
        buffer,
        compression='snappy',   # fast decompression, good ratio
    )
    buffer.seek(0)
    key = f"parquet/{table}/latest.parquet"
    r2_client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=buffer.getvalue(),
        ContentType='application/octet-stream',
    )
    logger.info(f"Exported {table}: {len(df)} rows → r2://{settings.r2_bucket_name}/{key}")
```

---

### Step 6 — FastAPI Routes

#### Step 6.1 — main.py
```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import sales, stats, map as map_router

app = FastAPI(title='PropRoo API', version='2.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],   # restrict to frontend domain in production
    allow_methods=['GET'],
    allow_headers=['*'],
)

app.include_router(sales.router,      prefix='/api/sales',  tags=['sales'])
app.include_router(stats.router,      prefix='/api/stats',  tags=['stats'])
app.include_router(map_router.router, prefix='/api/map',    tags=['map'])

@app.get('/api/health')
async def health():
    from app.database import get_pg_conn, release_pg_conn
    conn = get_pg_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sale")
            count = cur.fetchone()[0]
    finally:
        release_pg_conn(conn)
    return {'status': 'ok', 'record_count': count}
```

#### Step 6.2 — routers/map.py (viewport-bounded map endpoint)
```python
# backend/app/routers/map.py
from fastapi import APIRouter, Query
from app.database import get_duck_conn
from app.h3_utils import zoom_to_resolution, lat_lng_to_h3, h3_to_boundary
from app.cache import cached
from app.config import settings

router = APIRouter()

@router.get('/viewport')
@cached(ttl=120)
async def viewport_data(
    min_lat: float = Query(-38.0),
    max_lat: float = Query(-28.0),
    min_lng: float = Query(140.0),
    max_lng: float = Query(154.0),
    zoom:    int   = Query(8),
    year:    int   = Query(2024),
):
    """
    Returns H3-aggregated property data for the visible map viewport.
    Resolution scales with zoom level — coarse hexagons at low zoom, fine at high zoom.
    """
    resolution = zoom_to_resolution(zoom)
    r2_path = f"s3://{settings.r2_bucket_name}/parquet/sale/latest.parquet"

    duck = get_duck_conn()
    rows = duck.execute(f"""
        SELECT
            h3_h3_to_string(h3_latlng_to_cell(latitude, longitude, {resolution})) AS h3_index,
            COUNT(*)                     AS property_count,
            AVG(pg.avg_cagr)             AS avg_cagr,
            AVG(s.purchase_price)        AS avg_price,
            MAX(s.contract_date)::VARCHAR AS last_sale
        FROM read_parquet('{r2_path}') s
        LEFT JOIN read_parquet('s3://{settings.r2_bucket_name}/parquet/property_growth/latest.parquet') pg
            ON pg.property_id = s.property_id
        WHERE s.latitude  BETWEEN {min_lat} AND {max_lat}
          AND s.longitude BETWEEN {min_lng} AND {max_lng}
          AND EXTRACT(YEAR FROM s.contract_date::DATE) <= {year}
          AND s.latitude IS NOT NULL
        GROUP BY 1
        ORDER BY property_count DESC
        LIMIT 5000
    """).fetchall()

    features = []
    for row in rows:
        h3_idx, count, cagr, price, last_sale = row
        if not h3_idx:
            continue
        boundary = h3_to_boundary(h3_idx)
        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'Polygon',
                'coordinates': [boundary],
            },
            'properties': {
                'h3_index':       h3_idx,
                'property_count': count,
                'avg_cagr':       round(float(cagr or 0), 4),
                'avg_price':      round(float(price or 0), 0),
                'last_sale':      last_sale,
            }
        })

    return {'type': 'FeatureCollection', 'features': features}
```

#### Step 6.3 — routers/stats.py
```python
# backend/app/routers/stats.py
from fastapi import APIRouter, Query
from app.database import get_duck_conn
from app.cache import cached
from app.config import settings

router = APIRouter()

def _r2(table: str) -> str:
    return f"s3://{settings.r2_bucket_name}/parquet/{table}/latest.parquet"

@router.get('/global_summary')
@cached(ttl=300)
async def global_summary(year: int = Query(2024)):
    duck = get_duck_conn()

    top_suburbs = duck.execute(f"""
        SELECT suburb, post_code, avg_cagr, unique_properties, total_sales
        FROM read_parquet('{_r2("suburb_summary")}')
        WHERE avg_cagr > 0
        ORDER BY avg_cagr DESC
        LIMIT 20
    """).df().to_dict('records')

    top_streets = duck.execute(f"""
        SELECT street_name, suburb, post_code, avg_cagr, total_sales
        FROM read_parquet('{_r2("street_summary")}')
        WHERE avg_cagr > 0
        ORDER BY avg_cagr DESC
        LIMIT 20
    """).df().to_dict('records')

    return {'top_suburbs': top_suburbs, 'top_streets': top_streets, 'year': year}

@router.get('/top_performers')
@cached(ttl=300)
async def top_performers(
    year:          int = Query(2024),
    property_type: str = Query(None),
):
    duck = get_duck_conn()
    type_filter = f"AND s.property_type = '{property_type}'" if property_type else ""

    rows = duck.execute(f"""
        SELECT
            pg.suburb,
            pg.post_code,
            AVG(pg.avg_cagr)    AS avg_cagr,
            COUNT(pg.property_id) AS property_count
        FROM read_parquet('{_r2("property_growth")}') pg
        JOIN read_parquet('{_r2("sale")}') s ON s.property_id = pg.property_id
        WHERE pg.last_sale_year <= {year}
          {type_filter}
          AND pg.avg_cagr >= (
              SELECT QUANTILE(avg_cagr, 0.9)
              FROM read_parquet('{_r2("property_growth")}')
          )
        GROUP BY pg.suburb, pg.post_code
        ORDER BY avg_cagr DESC
        LIMIT 20
    """).df().to_dict('records')

    return {'growth': {'suburbs': rows}}

@router.get('/suburb_centroids')
@cached(ttl=600)
async def suburb_centroids(year: int = Query(2024)):
    duck = get_duck_conn()
    rows = duck.execute(f"""
        SELECT
            s.property_locality   AS suburb,
            AVG(s.latitude)       AS lat,
            AVG(s.longitude)      AS lng,
            ss.avg_cagr,
            ss.total_sales
        FROM read_parquet('{_r2("sale")}') s
        JOIN read_parquet('{_r2("suburb_summary")}') ss
            ON ss.suburb = s.property_locality
        WHERE EXTRACT(YEAR FROM s.contract_date::DATE) <= {year}
          AND s.latitude IS NOT NULL
        GROUP BY s.property_locality, ss.avg_cagr, ss.total_sales
    """).df().to_dict('records')

    return {'centroids': rows}
```

---

### Step 7 — Frontend Setup

```bash
cd ../frontend
npm create vite@latest . -- --template react-ts
npm install

# Map libraries
npm install deck.gl @deck.gl/react @deck.gl/layers @deck.gl/geo-layers
npm install maplibre-gl react-map-gl

# Charts and state
npm install recharts
npm install zustand

# Utilities
npm install @turf/turf   # geospatial utilities for bounding box calculations
```

#### Step 7.1 — Zustand Store
```typescript
// frontend/src/store/useAppStore.ts
import { create } from 'zustand';

interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

interface AppState {
  year:         number;
  propertyType: string | null;
  viewState:    ViewState;
  mapData:      any | null;
  summaryData:  any | null;
  loadingMap:   boolean;
  loadingSummary: boolean;

  setYear:         (y: number)         => void;
  setPropertyType: (t: string | null)  => void;
  setViewState:    (v: ViewState)      => void;
  setMapData:      (d: any)            => void;
  setSummaryData:  (d: any)            => void;
  setLoadingMap:   (v: boolean)        => void;
  setLoadingSummary: (v: boolean)      => void;
}

export const useAppStore = create<AppState>((set) => ({
  year:           2024,
  propertyType:   null,
  viewState: {
    longitude: 151.2093,   // Sydney
    latitude:  -33.8688,
    zoom:      9,
    pitch:     0,
    bearing:   0,
  },
  mapData:        null,
  summaryData:    null,
  loadingMap:     false,
  loadingSummary: false,

  setYear:           (year)         => set({ year }),
  setPropertyType:   (propertyType) => set({ propertyType }),
  setViewState:      (viewState)    => set({ viewState }),
  setMapData:        (mapData)      => set({ mapData }),
  setSummaryData:    (summaryData)  => set({ summaryData }),
  setLoadingMap:     (loadingMap)   => set({ loadingMap }),
  setLoadingSummary: (v)            => set({ loadingSummary: v }),
}));
```

#### Step 7.2 — useMapData Hook (viewport-bound fetching)
```typescript
// frontend/src/hooks/useMapData.ts
import { useEffect, useCallback, useRef } from 'react';
import { useAppStore } from '../store/useAppStore';
import { useDebounce } from './useDebounce';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export function useMapData() {
  const { viewState, year, setMapData, setLoadingMap } = useAppStore();
  const abortRef = useRef<AbortController | null>(null);

  // Debounce viewport changes — only fire after 300ms of no movement
  const debouncedViewState = useDebounce(viewState, 300);

  const fetchViewport = useCallback(async () => {
    if (!debouncedViewState) return;

    // Cancel previous in-flight request
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    // Compute bounding box from viewport
    // A rough approximation — turf.js bbox would be more precise for tilted views
    const { latitude: lat, longitude: lng, zoom } = debouncedViewState;
    const delta = Math.pow(2, 10 - zoom);   // degrees of lat/lng visible

    const params = new URLSearchParams({
      min_lat: String(lat - delta),
      max_lat: String(lat + delta),
      min_lng: String(lng - delta * 1.5),
      max_lng: String(lng + delta * 1.5),
      zoom:    String(Math.round(zoom)),
      year:    String(year),
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
```

#### Step 7.3 — useDebounce Hook
```typescript
// frontend/src/hooks/useDebounce.ts
import { useState, useEffect } from 'react';

export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState<T>(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}
```

#### Step 7.4 — PropRooMap Component
```typescript
// frontend/src/components/Map/PropRooMap.tsx
import React, { useMemo } from 'react';
import Map, { NavigationControl } from 'react-map-gl/maplibre';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer } from '@deck.gl/layers';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useAppStore } from '../../store/useAppStore';
import { useMapData } from '../../hooks/useMapData';

// Free OSM tiles via Stadia Maps — no API key for <200k requests/month
const MAP_STYLE = 'https://tiles.stadiamaps.com/styles/alidade_smooth.json';

// CAGR colour scale: red (negative) → yellow → green (high growth)
function cagrToColor(cagr: number): [number, number, number, number] {
  if (cagr <= 0)    return [220,  50,  50, 200];
  if (cagr < 0.05)  return [240, 180,  50, 200];
  if (cagr < 0.10)  return [100, 200,  80, 200];
  return                   [ 30, 150,  50, 220];
}

export default function PropRooMap() {
  const { viewState, setViewState, mapData } = useAppStore();
  useMapData();   // starts viewport-bound fetching

  const hexLayer = useMemo(() => {
    if (!mapData?.features?.length) return null;

    return new GeoJsonLayer({
      id: 'h3-hexagons',
      data: mapData,
      filled: true,
      stroked: true,
      extruded: false,
      getFillColor: (f: any) => cagrToColor(f.properties.avg_cagr),
      getLineColor: [255, 255, 255, 60],
      lineWidthMinPixels: 0.5,
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 80],
      onClick: (info: any) => {
        if (info.object) {
          console.log('Clicked hex:', info.object.properties);
          // Navigate to suburb detail here
        }
      },
      getTooltip: (f: any) => f && {
        text: [
          `Suburb: ${f.properties.suburb || 'Unknown'}`,
          `CAGR: ${(f.properties.avg_cagr * 100).toFixed(1)}%`,
          `Avg Price: $${f.properties.avg_price?.toLocaleString()}`,
          `Properties: ${f.properties.property_count}`,
        ].join('\n'),
      },
    });
  }, [mapData]);

  return (
    <DeckGL
      viewState={viewState}
      onViewStateChange={({ viewState: vs }: any) => setViewState(vs)}
      controller={true}
      layers={hexLayer ? [hexLayer] : []}
      style={{ position: 'relative', width: '100%', height: '100vh' }}
    >
      <Map
        mapStyle={MAP_STYLE}
        style={{ width: '100%', height: '100%' }}
      >
        <NavigationControl position="top-right" />
      </Map>
    </DeckGL>
  );
}
```

---

### Step 8 — Verify Each Layer Before Continuing

Run these checks in order. Fix any failures before proceeding.

```bash
# 8.1 Database schema
psql $DATABASE_URL -c "\dt"
# Expected: sale, property_growth, street_summary, suburb_summary

# 8.2 ETL dry run (single year, small dataset)
cd backend
python -m etl.ingest --start-year 2023 --end-year 2023
# Expected last log line: "Cache invalidated. Pipeline complete."

# 8.3 Verify sale count
psql $DATABASE_URL -c "SELECT COUNT(*) FROM sale"
# Expected: > 0

# 8.4 Verify Parquet exported to R2
python -c "
from app.database import get_r2_client
from app.config import settings
r2 = get_r2_client()
objs = r2.list_objects(Bucket=settings.r2_bucket_name, Prefix='parquet/')
for o in objs.get('Contents', []):
    print(o['Key'], o['Size'])
"
# Expected: 4 .parquet files listed

# 8.5 Start API
uvicorn app.main:app --reload --port 8000

# 8.6 Health check
curl http://localhost:8000/api/health
# Expected: {"status":"ok","record_count": <number > 0>}

# 8.7 Stats endpoint
curl "http://localhost:8000/api/stats/global_summary?year=2023"
# Expected: {"top_suburbs":[...],"top_streets":[...],"year":2023}

# 8.8 Map endpoint
curl "http://localhost:8000/api/map/viewport?min_lat=-34.5&max_lat=-33.5&min_lng=150.5&max_lng=151.5&zoom=9&year=2023"
# Expected: {"type":"FeatureCollection","features":[...]}

# 8.9 Frontend
cd ../frontend
npm run dev
# Open http://localhost:5173
# Expected: Map renders with coloured hexagons over Sydney area
```

---

### Step 9 — Deployment

#### Step 9.1 — Backend (Render)
```yaml
# render.yaml
services:
  - type: web
    name: proproo-api
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: R2_ACCESS_KEY_ID
        sync: false
      - key: R2_SECRET_ACCESS_KEY
        sync: false
      - key: R2_ENDPOINT
        sync: false
      - key: R2_BUCKET_NAME
        value: proproo-data
      - key: REDIS_URL
        sync: false
      - key: PYTHON_VERSION
        value: 3.12.0
```

#### Step 9.2 — Frontend (Cloudflare Pages)
```bash
cd frontend
# Create .env.production
echo "VITE_API_URL=https://proproo-api.onrender.com" > .env.production

npm run build
# Deploy dist/ to Cloudflare Pages:
npx wrangler pages deploy dist --project-name proproo
```

---

## Part 5 — Known Constraints and Limits

| Constraint | Value | Mitigation |
|---|---|---|
| Render free tier RAM | 512MB | Chunked ETL (50k rows/chunk) |
| Render free tier sleep | 15 min inactivity | Health check ping every 10 min via UptimeRobot (free) |
| Supabase free tier DB | 500MB | Export to Parquet at ~80MB compressed; keep only recent 2 years in Supabase live table |
| Upstash Redis free | 10k req/day | Cache TTL 5 min; only stats endpoints cached, not raw sales |
| Stadia Maps free | 200k tile req/month | Sufficient for ~5k users/month; upgrade to $20/month if exceeded |
| DuckDB R2 egress | $0 (R2 has no egress fee) | No mitigation needed |
| H3 resolution 9 | ~174m² hexagons | At property level, multiple properties may share a hex. Show count, not individual points |
