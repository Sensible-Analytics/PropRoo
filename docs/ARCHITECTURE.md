# PropRoo Architecture — Phase 2: UI/Performance Redesign

**Date**: 2026-04-05
**Status**: In Progress
**PR**: TBD

---

## System Context (C4 Level 1)

```mermaid
C4Context
    title PropRoo System Context — Phase 2

    Person(user, "Property Investor", "Researches NSW property investment opportunities")
    System_Boundary(proprio, "PropRoo System") {
        Container(frontend, "React SPA", "React 19 + Vite 7", "Map-based property exploration UI")
        ContainerDb(r2, "Cloudflare R2", "Object Storage", "Parquet files: sales, growth, summaries, H3 tiles")
    }
    System_Ext(valuer, "NSW Valuer General", "Public property sales data source")
    System_Ext(etl, "GitHub Actions ETL", "Daily pipeline", "Ingest → Geocode → Growth → Upload to R2")

    Rel(user, frontend, "Explores property data via map")
    Rel(frontend, r2, "Fetches parquet files (DuckDB-WASM)")
    Rel(etl, valuer, "Downloads sales data")
    Rel(etl, r2, "Uploads processed parquet files")
```

## Container Architecture (C4 Level 2)

```mermaid
C4Container
    title PropRoo Container Architecture — Phase 2

    Person(user, "Property Investor")
    
    Container_Boundary(browser, "User Browser") {
        Container(react, "React SPA", "React 19 + Vite 7", "UI components, state management")
        Container(duckdb, "DuckDB-WASM", "WebAssembly SQL Engine", "In-browser parquet queries")
        Container(deckgl, "deck.gl + MapLibre", "WebGL Rendering", "Map visualization, H3 hexagons")
        ContainerDb(indexeddb, "IndexedDB", "Browser Storage", "Query result cache, parquet cache")
        Container(sw, "Service Worker", "Background Process", "Parquet file caching, offline support")
    }
    
    Container_Boundary(cloudflare, "Cloudflare Edge") {
        Container(pages, "Cloudflare Pages", "Static Hosting", "SPA hosting, CDN")
        Container(cache, "Cloudflare Cache API", "Edge Cache", "Parquet file edge caching")
        Container(r2, "Cloudflare R2", "Object Storage", "Source parquet files")
    }

    Rel(user, react, "Interacts with UI")
    Rel(react, duckdb, "SQL queries on parquet")
    Rel(duckdb, indexeddb, "Cache lookup / store results")
    Rel(duckdb, r2, "Fetches parquet files (parallel)")
    Rel(react, deckgl, "Renders map layers")
    Rel(sw, cache, "Caches parquet at edge")
    Rel(cache, r2, "Origin fetch with stale-while-revalidate")
    Rel(pages, react, "Serves SPA bundle")
```

## Data Flow

```mermaid
flowchart TD
    User["User Opens App"] --> SW["Service Worker Check"]
    SW -->|Cached| Local["Load from IndexedDB"]
    SW -->|Miss| Fetch["Parallel Fetch from R2"]
    Fetch --> DuckDB["DuckDB-WASM Registers Files"]
    Local --> DuckDB
    DuckDB --> Query["SQL Query Execution"]
    Query --> Cache{IndexedDB Cache Hit?}
    Cache -->|Yes| Render["Render deck.gl Layers"]
    Cache -->|No| Execute["Execute DuckDB Query"]
    Execute --> Store["Store in IndexedDB"]
    Store --> Render
    Render --> User
```

## Key Architecture Decisions

### ADR-001: Pure Frontend Architecture
**Decision**: No backend server. All data processing happens in-browser via DuckDB-WASM.
**Rationale**: Eliminates server costs, reduces latency, scales infinitely via CDN.
**Trade-offs**: Initial load is 34MB (mitigated by caching), limited by browser memory.

### ADR-002: IndexedDB Query Caching
**Decision**: Cache DuckDB query results in IndexedDB with TTL tiers.
**Rationale**: Avoids re-running expensive aggregations on filter changes.
**TTL Tiers**: Street summary (7d), Suburb summary (24h), Sales data (1h), H3 tiles (7d).

### ADR-003: Parallel Parquet Loading
**Decision**: Load all parquet files simultaneously via HTTP/2 multiplexing.
**Rationale**: Reduces initial load from ~30s to ~8s.

### ADR-004: 80/20 Layout with Sidebar Table
**Decision**: Map takes 80% of entire app, sidebar (20%) contains charts + scrollable table.
**Rationale**: Map is the primary exploration tool. Table supports, doesn't compete.

### ADR-005: shadcn/ui Design System
**Decision**: Adopt shadcn/ui components with OKLCH color tokens.
**Rationale**: Consistent design language, dark-mode optimized, copy-paste components.

## Performance Targets

| Metric | Current | Target | Method |
|--------|---------|--------|--------|
| Initial load | ~30s | <8s | Parallel loading + edge cache |
| Repeat visit | ~30s | <2s | IndexedDB + Service Worker |
| Query response | ~2s | <200ms | IndexedDB query cache |
| Map FPS | 30-45 | 60 | deck.gl memoization |
| Bundle size | 1.8MB | <1MB | Code splitting + tree shaking |

## File Structure (New)

```
frontend/src/
├── components/
│   ├── Dashboard.tsx          # Main layout (80/20 split)
│   ├── Map/
│   │   ├── PropRooMap.tsx     # deck.gl map with optimized layers
│   │   ├── LayerControls.tsx  # Floating layer toggle panel
│   │   └── TimeSlider.tsx     # Year slider component
│   ├── Sidebar/
│   │   ├── Sidebar.tsx        # 20% sidebar container
│   │   ├── CAGRChart.tsx      # Top CAGR bar chart
│   │   └── DataTable.tsx      # Scrollable sales table
│   ├── Header/
│   │   ├── Header.tsx         # Compact header with breadcrumb
│   │   └── Breadcrumb.tsx     # NSW → Suburb → Street navigation
│   └── ui/                    # shadcn/ui components
│       ├── slider.tsx
│       ├── checkbox.tsx
│       ├── breadcrumb.tsx
│       └── tabs.tsx
├── services/
│   ├── duckdb.ts              # DuckDB-WASM initialization (parallel)
│   ├── query-cache.ts         # IndexedDB query cache with TTL
│   └── sw.ts                  # Service worker registration
├── store/
│   └── index.ts               # Zustand stores (optimized selectors)
├── data/
│   └── nsw_suburbs.geojson    # Suburb boundaries
└── public/
    └── sw.js                  # Service worker script
```
