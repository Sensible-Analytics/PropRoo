import sys
import os

# Add backend to path so we can import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import Sale

def main():
    db = SessionLocal()
    try:
        total = db.query(Sale).count()
        missing_coords = db.query(Sale).filter(Sale.latitude == None).count()
        missing_listings = db.query(Sale).filter(Sale.listings_last_checked == None).count()
        
        print(f"--- Backfill Status ---")
        print(f"Total Sale Records: {total}")
        print(f"Missing Coordinates: {missing_coords} ({((missing_coords/total)*100 if total > 0 else 0):.1f}%)")
        print(f"Missing Listings:    {missing_listings} ({((missing_listings/total)*100 if total > 0 else 0):.1f}%)")
        print(f"-----------------------")
    finally:
        db.close()

if __name__ == "__main__":
    main()
