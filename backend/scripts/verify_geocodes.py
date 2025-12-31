import sys
import os

# Add backend to path so we can import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import Sale

def main():
    db = SessionLocal()
    try:
        sales = db.query(Sale).filter(Sale.latitude != None).limit(5).all()
        print(f"Sales with coordinates: {len(sales)}")
        for sale in sales:
            print(f"ID: {sale.id}, Address: {sale.property_house_number} {sale.property_street_name}, {sale.property_locality}, Lat: {sale.latitude}, Lon: {sale.longitude}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
