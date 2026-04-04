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
from pathlib import Path
from typing import Optional

import pandas as pd

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


def run_geocode(data_dir: str = None) -> None:
    if data_dir is None:
        data_dir = str(Path(__file__).resolve().parent.parent / "data")
    data_path = Path(data_dir)
    sales_path = data_path / "sales.parquet"

    if not sales_path.exists():
        raise FileNotFoundError(f"Sales parquet not found at {sales_path}")

    logger.info("Starting geocoding ETL...")
    postcode_df = download_postcodes()
    suburb_lookup, postcode_lookup = build_lookup(postcode_df)

    sales_df = pd.read_parquet(sales_path)

    missing_mask = sales_df["latitude"].isna() | sales_df["longitude"].isna()
    missing_count = missing_mask.sum()
    logger.info(f"Records needing coordinates: {missing_count:,}")

    if missing_count == 0:
        logger.info("All records already geocoded. Nothing to do.")
        return

    # Vectorized geocoding
    sales_df["latitude"] = sales_df["latitude"].astype(float)
    sales_df["longitude"] = sales_df["longitude"].astype(float)

    # Build suburb lookup key: (locality_stripped, postcode_int)
    locality_clean = sales_df["property_locality"].astype(str).str.strip()
    postcode_clean = pd.to_numeric(sales_df["property_post_code"], errors="coerce")

    # Suburb match: (locality, postcode) -> (lat, lng)
    suburb_lats = {k: v[0] for k, v in suburb_lookup.items()}
    suburb_lngs = {k: v[1] for k, v in suburb_lookup.items()}
    suburb_keys = locality_clean + "|" + postcode_clean.astype("Int64").astype(str)
    suburb_key_map = {f"{k[0]}|{k[1]}": v for k, v in suburb_lats.items()}
    suburb_lng_map = {f"{k[0]}|{k[1]}": v for k, v in suburb_lngs.items()}

    matched_lat = suburb_key_map.get
    matched_lng = suburb_lng_map.get

    lat_from_suburb = suburb_keys.map(matched_lat)
    lng_from_suburb = suburb_keys.map(matched_lng)

    # Postcode-only fallback
    pc_lats = {k: v[0] for k, v in postcode_lookup.items()}
    pc_lngs = {k: v[1] for k, v in postcode_lookup.items()}
    lat_from_pc = postcode_clean.map(pc_lats)
    lng_from_pc = postcode_clean.map(pc_lngs)

    # Prefer suburb match, fall back to postcode
    sales_df["latitude"] = lat_from_suburb.fillna(lat_from_pc)
    sales_df["longitude"] = lng_from_suburb.fillna(lng_from_pc)

    updated = sales_df["latitude"].notna().sum() - (~missing_mask).sum()
    no_match = missing_count - max(updated, 0)

    sales_df.to_parquet(sales_path, index=False, engine="pyarrow")

    logger.info(f"Geocoding complete: {updated:,} updated, {no_match:,} no match")
    if no_match > 0:
        logger.warning(
            f"{no_match:,} records could not be geocoded. "
            "These may have non-standard locality/postcode values."
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    import argparse

    parser = argparse.ArgumentParser(description="Geocode NSW property sales data")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Data directory (default: script's parent/data)",
    )
    args = parser.parse_args()
    run_geocode(data_dir=args.data_dir)
