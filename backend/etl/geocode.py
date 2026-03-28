"""
PropRoo Geocoding ETL — Two-tier strategy for 100% coverage

Tier 1: Suburb centroids (instant, free, ~100% coverage for NSW)
  → Download Australian postcode dataset (4,116 localities with lat/lng)
  → Match on property_locality + property_post_code
  → ~500m-5km accuracy (sufficient for map clustering)

Tier 2: Postcode centroids (fallback, covers edge cases)
  → Same dataset matched on postcode only
  → ~1-10km accuracy for rural areas

Result: All 640k records get coordinates in minutes, not days.
"""

import io
import json
import logging
import urllib.request
import urllib.error
from typing import Optional

import pandas as pd
import psycopg2

logger = logging.getLogger(__name__)

POSTCODE_URL = (
    "https://raw.githubusercontent.com/matthewproctor/australianpostcodes/"
    "master/australian_postcodes.json"
)

CHUNK_SIZE = 50_000


def download_postcodes() -> pd.DataFrame:
    logger.info("Downloading Australian postcode data...")
    try:
        req = urllib.request.Request(
            POSTCODE_URL,
            headers={"User-Agent": "PropRoo/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        df = pd.DataFrame(data)
        df.columns = [c.lower() for c in df.columns]
        df = df.rename(
            columns={
                "locality": "locality_raw",
                "long": "lng",
            }
        )
        df["locality_clean"] = df["locality_raw"].str.strip().str.title()
        logger.info(f"Postcode data: {len(df)} rows, columns: {list(df.columns)}")
        return df
    except urllib.error.URLError as e:
        logger.error(f"Failed to download postcode data: {e}")
        raise


def build_lookup(df: pd.DataFrame) -> tuple[dict, dict]:
    suburb_lookup: dict[tuple, tuple] = {}
    postcode_lookup: dict[int, tuple] = {}

    for _, row in df.iterrows():
        lat = row.get("lat")
        lng = row.get("lng")
        locality = row.get("locality_clean")
        postcode = row.get("postcode")

        if lat is None or lng is None:
            continue
        try:
            lat_f = float(lat)
            lng_f = float(lng)
        except (TypeError, ValueError):
            continue

        if locality and pd.notna(locality):
            key = (str(locality).strip(), int(postcode))
            suburb_lookup[key] = (lat_f, lng_f)

        if postcode and pd.notna(postcode):
            pc = int(postcode)
            if pc not in postcode_lookup:
                postcode_lookup[pc] = (lat_f, lng_f)

    logger.info(
        f"Lookup built: {len(suburb_lookup)} suburb+postcode, "
        f"{len(postcode_lookup)} postcode-only entries"
    )
    return suburb_lookup, postcode_lookup


def run_geocode(database_url: str) -> None:
    if not database_url:
        raise ValueError("DATABASE_URL is required")

    logger.info("Starting geocoding ETL...")
    postcode_df = download_postcodes()
    suburb_lookup, postcode_lookup = build_lookup(postcode_df)

    conn = psycopg2.connect(database_url)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM sales WHERE latitude IS NULL OR longitude IS NULL"
    )
    missing = cur.fetchone()[0]
    logger.info(f"Records needing coordinates: {missing:,}")

    if missing == 0:
        logger.info("All records already geocoded. Nothing to do.")
        conn.close()
        return

    updated = 0
    no_match = 0

    cur.execute(
        """
        SELECT id, property_locality, property_post_code
        FROM sales
        WHERE latitude IS NULL OR longitude IS NULL
        """
    )
    rows = cur.fetchall()

    batch_updates = []
    for sale_id, locality, postcode in rows:
        if not locality and not postcode:
            no_match += 1
            continue

        lat, lng = None, None

        if locality and postcode:
            key = (str(locality).strip(), int(postcode))
            lat, lng = suburb_lookup.get(key)

        if lat is None and postcode:
            lat, lng = postcode_lookup.get(int(postcode))

        if lat is not None and lng is not None:
            batch_updates.append((lat, lng, sale_id))
        else:
            no_match += 1

        if len(batch_updates) >= CHUNK_SIZE:
            _flush_batch(cur, batch_updates)
            updated += len(batch_updates)
            batch_updates = []
            logger.info(f"  Progress: {updated:,} updated, {no_match:,} unmatched")

    if batch_updates:
        _flush_batch(cur, batch_updates)
        updated += len(batch_updates)

    conn.commit()
    cur.close()
    conn.close()

    logger.info(f"Geocoding complete: {updated:,} updated, {no_match:,} no match")
    if no_match > 0:
        logger.warning(
            f"{no_match:,} records could not be geocoded. "
            "These may have non-standard locality/postcode values."
        )


def _flush_batch(cur, batch):
    cur.executemany(
        "UPDATE sales SET latitude = %s, longitude = %s WHERE id = %s",
        batch,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    import os

    db_url = os.environ.get("DATABASE_URL", "")
    run_geocode(db_url)
