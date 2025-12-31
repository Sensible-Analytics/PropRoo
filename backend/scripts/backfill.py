#!/usr/bin/env python3
import sys
import os
import argparse
import logging
from typing import Optional, Dict, Any

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.utils.base_backfill import run_backfill
from app.geocoding import geocode_address
from app.listing_search import search_property_listings
from app.models import Sale

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def geocode_processor(sale: Sale) -> Optional[Dict[str, Any]]:
    """Processor for geocoding a sale record."""
    address = f"{sale.property_house_number} {sale.property_street_name}, {sale.property_locality} NSW {sale.property_post_code}"
    lat, lon = geocode_address(address)
    if lat and lon:
        return {'latitude': lat, 'longitude': lon}
    return None

def listing_processor(sale: Sale) -> Optional[Dict[str, Any]]:
    """Processor for searching property listings."""
    results = search_property_listings(sale)
    if results:
        return {
            'realestate_url': results.get('realestate_url'),
            'domain_url': results.get('domain_url'),
            'listings_last_checked': results.get('timestamp')
        }
    return None

def main() -> None:
    parser = argparse.ArgumentParser(description="Consolidated Backfill Utility")
    parser.add_argument("type", choices=["geocoding", "listings"], help="Type of backfill to run")
    parser.add_argument("--limit", type=int, default=100, help="Number of records to process")
    parser.add_argument("--offset", type=int, default=0, help="Number of records to skip")
    parser.add_argument("--batch-id", type=int, default=0, help="Batch identifier for logging")
    args = parser.parse_args()

    if args.type == "geocoding":
        filter_criterion = (Sale.latitude == None)
        run_backfill(geocode_processor, filter_criterion, limit=args.limit, offset=args.offset, batch_id=args.batch_id)
    elif args.type == "listings":
        filter_criterion = (Sale.listings_last_checked == None)
        run_backfill(listing_processor, filter_criterion, limit=args.limit, offset=args.offset, batch_id=args.batch_id)

if __name__ == "__main__":
    main()
