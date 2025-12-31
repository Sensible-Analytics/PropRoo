from backend.app.database import SessionLocal
from backend.app.models import Sale, PropertyGrowth
import pandas as pd
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_cagr():
    db = SessionLocal()
    try:
        # Get 5 random properties with growth data
        growth_entries = db.query(PropertyGrowth).limit(5).all()
        
        for entry in growth_entries:
            pid = entry.property_id
            stored_cagr = entry.cagr
            stored_years = entry.years_held
            
            # Fetch sales
            sales = db.query(Sale).filter(Sale.property_id == pid).order_by(Sale.contract_date).all()
            if not sales:
                continue
                
            first_sale = sales[0]
            last_sale = sales[-1]
            
            p_start = first_sale.purchase_price
            p_end = last_sale.purchase_price
            d_start = pd.to_datetime(first_sale.contract_date)
            d_end = pd.to_datetime(last_sale.contract_date)
            
            if p_start is None or p_end is None:
                continue
                
            years = (d_end - d_start).days / 365.25
            
            # Recalc
            if p_start > 0 and years > 0:
                calc_cagr = ((p_end / p_start) ** (1 / years)) - 1
            else:
                calc_cagr = 0
                
            logger.info(f"Property {pid}:")
            logger.info(f"  Start: {p_start} on {d_start.date()}")
            logger.info(f"  End:   {p_end} on {d_end.date()}")
            logger.info(f"  Years: {years:.4f} (Stored: {stored_years:.4f})")
            logger.info(f"  CAGR:  {calc_cagr:.6f} (Stored: {stored_cagr:.6f})")
            
            diff = abs(calc_cagr - stored_cagr)
            if diff < 0.0001:
                logger.info("  [PASS] Calculation matches.")
            else:
                logger.error(f"  [FAIL] Mismatch! Diff: {diff}")
            logger.info("-" * 30)
            
    finally:
        db.close()

if __name__ == "__main__":
    verify_cagr()
