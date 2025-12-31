import sys
import os

# Add backend to path so we can import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import StreetSummary, SuburbSummary, StreetGrowth, SuburbGrowth

def main():
    db = SessionLocal()
    try:
        street_year_count = db.query(StreetGrowth).count()
        suburb_year_count = db.query(SuburbGrowth).count()
        street_summary_count = db.query(StreetSummary).count()
        suburb_summary_count = db.query(SuburbSummary).count()
        
        print(f"--- Analytics Verification ---")
        print(f"Street-Year Records: {street_year_count}")
        print(f"Suburb-Year Records: {suburb_year_count}")
        print(f"Street Summaries:    {street_summary_count}")
        print(f"Suburb Summaries:    {suburb_summary_count}")
        
        # Check a sample
        top_suburb = db.query(SuburbSummary).order_by(SuburbSummary.avg_cagr.desc()).first()
        if top_suburb:
            print(f"\nTop Suburb: {top_suburb.suburb}")
            print(f"Avg CAGR:   {top_suburb.avg_cagr * 100:.2f}%")
            print(f"Properties: {top_suburb.unique_properties}")
            print(f"Sales:      {top_suburb.total_sales}")
            
        print(f"-----------------------------")
    finally:
        db.close()

if __name__ == "__main__":
    main()
