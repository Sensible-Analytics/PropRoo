# NSW Property Sales Analytics - Backend

This directory contains the FastAPI backend for analyzing NSW property sales data, including data ingestion, geocoding, and growth metrics calculation.

## Architecture

- **`app/`**: Core application logic.
  - **`routers/`**: FastAPI route definitions.
  - **`models.py`**: SQLAlchemy database models.
  - **`database.py`**: Database connection and session management.
  - **`geocoding.py`**: Nominatim-based geocoding and station distance calculation.
  - **`listing_search.py`**: Realestate.com.au and Domain.com.au listing search.
  - **`analytics.py`**: CAGR and growth metrics calculation.
  - **`utils/`**: Shared utilities (e.g., `base_backfill.py`).
- **`data/`**: Source data files (Zipped weekly sales records).
- **`scripts/`**: Operational scripts for maintenance and batch processing.

## Operational Scripts

### 1. Database Initialization
```bash
python3 backend/scripts/init_db.py
```
Initializes the database schema and runs initial analytics.

### 2. Batch Backfilling
The `backfill.py` script handles sequential batch processing for geocoding or listing searches.
```bash
python3 backend/scripts/backfill.py [geocoding|listings] --limit 100 --offset 0
```

### 3. Parallel Processing
To speed up backfilling, use the parallel runner:
```bash
python3 backend/scripts/run_parallel.py [geocoding|listings] --procs 5 --batch 1000
```
- **Geocoding**: Uses staggering to respect Nominatim's rate limit.
- **Listings**: Parallelizes web scraping for efficiency.

## Testing

Unit tests are located in the `backend/tests/` directory. To run the tests, ensure you have `pytest` installed and run:
```bash
PYTHONPATH=backend ./backend/venv/bin/pytest backend/tests
```

## Refactored Structure
The codebase has been refactored for better readability and maintainability:
- **Type Hints**: Added throughout the core modules (`analytics.py`, `ingest.py`, etc.).
- **Modularization**: Extracted CAGR and other logic into utility functions.
- **Error Handling**: Improved resilience during data ingestion and processing.
- **Standardized Logging**: Consistent output format across all scripts.

## API Documentation
Once the server is running (`npm run dev` in project root or manual uvicorn launch), documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
