"""
PropRoo Database Migration v1 → v2

Run this script AFTER updating requirements.txt and deploying the new backend code.
Safe to run multiple times (idempotent).

Usage:
    python backend/scripts/migrate_schema.py

Steps:
    1. Enable PostGIS extension
    2. Add geom column + GIST index + trigger to sales table
    3. Add missing columns to property_growth (avg_cagr, total_growth with correct precision)
    4. Create new analytics tables (street_summary, suburb_summary) if missing
    5. Invalidate Redis cache
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.cache import invalidate_all


MIGRATIONS = [
    # Step 1: Enable PostGIS
    ("enable_postgis", "CREATE EXTENSION IF NOT EXISTS postgis;"),
    # Step 2: Add geom column (geography POINT) to sales if not exists
    (
        "add_geom_column",
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sales' AND column_name = 'geom'
            ) THEN
                ALTER TABLE sales ADD COLUMN geom geography(POINT, 4326);
            END IF;
        END $$;
    """,
    ),
    # Step 3: Create trigger function to auto-populate geom from lat/lng
    (
        "create_geom_trigger_fn",
        """
        CREATE OR REPLACE FUNCTION set_sale_geom()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
                NEW.geom = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::geography;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """,
    ),
    # Step 4: Create trigger (skip if exists)
    (
        "create_geom_trigger",
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger WHERE tgname = 'trg_sale_geom'
            ) THEN
                CREATE TRIGGER trg_sale_geom
                    BEFORE INSERT OR UPDATE ON sales
                    FOR EACH ROW EXECUTE FUNCTION set_sale_geom();
            END IF;
        END $$;
    """,
    ),
    # Step 5: Create GIST index on geom if not exists
    (
        "create_geom_index",
        """
        CREATE INDEX IF NOT EXISTS idx_sales_geom ON sales USING GIST(geom);
    """,
    ),
    # Step 6: Add missing columns to property_growth
    (
        "add_pg_columns",
        """
        ALTER TABLE property_growth
            ADD COLUMN IF NOT EXISTS suburb VARCHAR(50),
            ADD COLUMN IF NOT EXISTS street_name VARCHAR(100),
            ADD COLUMN IF NOT EXISTS post_code INTEGER,
            ADD COLUMN IF NOT EXISTS year INTEGER,
            ADD COLUMN IF NOT EXISTS avg_cagr DECIMAL(10,6),
            ADD COLUMN IF NOT EXISTS total_growth DECIMAL(10,6),
            ADD COLUMN IF NOT EXISTS years_held INTEGER,
            ADD COLUMN IF NOT EXISTS first_sale_price DECIMAL(15,2),
            ADD COLUMN IF NOT EXISTS last_sale_price DECIMAL(15,2),
            ADD COLUMN IF NOT EXISTS first_sale_year INTEGER,
            ADD COLUMN IF NOT EXISTS last_sale_year INTEGER;
    """,
    ),
    # Step 7: Ensure suburb_summary table exists with correct schema
    (
        "create_suburb_summary",
        """
        CREATE TABLE IF NOT EXISTS suburb_summary (
            id SERIAL PRIMARY KEY,
            suburb VARCHAR(50) NOT NULL,
            post_code INTEGER,
            unique_properties INTEGER,
            total_sales INTEGER,
            avg_cagr DECIMAL(10,6),
            property_count INTEGER,
            UNIQUE (suburb, post_code)
        );
    """,
    ),
    # Step 8: Ensure street_summary table exists with correct schema
    (
        "create_street_summary",
        """
        CREATE TABLE IF NOT EXISTS street_summary (
            id SERIAL PRIMARY KEY,
            street_name VARCHAR(100) NOT NULL,
            suburb VARCHAR(50) NOT NULL,
            post_code INTEGER,
            unique_properties INTEGER,
            total_sales INTEGER,
            avg_cagr DECIMAL(10,6),
            property_count INTEGER,
            UNIQUE (street_name, suburb, post_code)
        );
    """,
    ),
]


def run_migration():
    if not settings.database_url:
        print("ERROR: DATABASE_URL not set. Set it in backend/.env or environment.")
        sys.exit(1)

    import psycopg2

    print(f"Connecting to database...")
    conn = psycopg2.connect(settings.database_url)
    conn.autocommit = True
    cur = conn.cursor()

    print(f"Running {len(MIGRATIONS)} migrations...")
    for name, sql in MIGRATIONS:
        try:
            print(f"  [{name}] ", end="", flush=True)
            cur.execute(sql)
            print("OK")
        except Exception as e:
            print(f"FAILED: {e}")
            conn.close()
            sys.exit(1)

    conn.close()
    print("\nAll migrations applied successfully!")

    print("\nInvalidating Redis cache...")
    try:
        invalidate_all()
        print("Cache invalidated.")
    except Exception as e:
        print(f"Cache invalidation skipped (Redis not available): {e}")

    print("\nNext steps:")
    print("  1. Run: python -m etl.calculate_growth")
    print("  2. Run: python -m etl.export_parquet")
    print("  3. Deploy: git push")


if __name__ == "__main__":
    run_migration()
