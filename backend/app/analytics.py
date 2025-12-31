import logging
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from .models import Sale, PropertyGrowth, StreetGrowth, SuburbGrowth
from .database import SessionLocal, engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def calculate_cagr(first_price: float, last_price: float, years: float) -> Tuple[float, float]:
    """
    Calculate Compound Annual Growth Rate (CAGR) and total growth.
    
    Args:
        first_price: Price at the start of the period.
        last_price: Price at the end of the period.
        years: Number of years between sales.
        
    Returns:
        A tuple of (cagr, total_growth).
    """
    if years < 0.5:  # Ignore if held for less than 6 months for CAGR purposes
        return 0.0, (last_price - first_price) / first_price

    try:
        cagr = ((last_price / first_price) ** (1 / years)) - 1
    except (ZeroDivisionError, OverflowError) as e:
        logger.error(f"Error calculating CAGR: {e}")
        cagr = 0.0

    total_growth = (last_price - first_price) / first_price
    return cagr, total_growth

def calculate_growth_metrics() -> None:
    """
    Calculate and store growth metrics (CAGR, total growth) at the property, 
    street, and suburb levels, with per-year support.
    """
    logger.info("Starting growth calculation...")
    db: Session = SessionLocal()
    try:
        # Load all sales into a DataFrame
        query = db.query(Sale).statement
        df = pd.read_sql(query, db.bind)

        if df.empty:
            logger.warning("No sales data found.")
            return

        # Ensure dates are datetime objects
        df['contract_date'] = pd.to_datetime(df['contract_date'], errors='coerce')
        df['purchase_price'] = pd.to_numeric(df['purchase_price'], errors='coerce')
        df = df.dropna(subset=['purchase_price', 'contract_date'])
        
        # Add year column
        df['sale_year'] = df['contract_date'].dt.year

        # --- Property Level Growth ---
        property_stats = []
        
        # Sort by date for efficient processing
        df = df.sort_values(by=['property_id', 'contract_date'])

        for pid, group in df.groupby('property_id'):
            if len(group) < 2:
                continue
            
            first_sale = group.iloc[0]
            last_sale = group.iloc[-1]
            
            first_price: float = float(first_sale['purchase_price'])
            last_price: float = float(last_sale['purchase_price'])
            
            first_date = first_sale['contract_date']
            last_date = last_sale['contract_date']
            
            years: float = (last_date - first_date).days / 365.25
            
            cagr, total_growth = calculate_cagr(first_price, last_price, years)

            property_stats.append({
                "property_id": str(pid),
                "cagr": cagr,
                "total_growth": total_growth,
                "years_held": years,
                "last_sale_price": last_price,
                "first_sale_price": first_price,
                "last_sale_year": int(last_sale['sale_year']),
                "property_street_name": first_sale['property_street_name'],
                "property_locality": first_sale['property_locality'],
                "property_post_code": int(first_sale['property_post_code']) if pd.notnull(first_sale['property_post_code']) else 0
            })

        # Save Property Growth (Latest Snapshot)
        db.query(PropertyGrowth).delete()
        if property_stats:
            # Prepare only database fields
            db_property_records = [
                {k: v for k, v in p.items() if k in PropertyGrowth.__table__.columns.keys()}
                for p in property_stats
            ]
            db.bulk_insert_mappings(PropertyGrowth, db_property_records)
            logger.info(f"Calculated growth for {len(property_stats)} properties.")
        
        db.commit()

        # --- Per-Year Aggregation for Street and Suburb ---
        if not property_stats:
            return

        growth_df = pd.DataFrame(property_stats)
        
        years_range = range(2001, 2026) # 2001 to current
        
        street_records = []
        suburb_records = []
        
        logger.info("Aggregating per-year stats...")

        for year in years_range:
            # "include property which has been sold in the year or has been sold in later years"
            # "do not include property which has been sold prior to current year and there is no info about the sale in later year"
            year_active_df = growth_df[growth_df['last_sale_year'] >= year]
            
            if year_active_df.empty:
                continue
                
            # Street Level
            street_stats = year_active_df.groupby(['property_street_name', 'property_locality', 'property_post_code']).agg(
                avg_cagr=('cagr', 'mean'),
                property_count=('property_id', 'count')
            ).reset_index()

            for _, row in street_stats.iterrows():
                street_records.append({
                    "street_name": row['property_street_name'],
                    "suburb": row['property_locality'],
                    "post_code": int(row['property_post_code']),
                    "year": year,
                    "avg_cagr": row['avg_cagr'],
                    "property_count": int(row['property_count'])
                })

            # Suburb Level
            suburb_stats = year_active_df.groupby(['property_locality']).agg(
                avg_cagr=('cagr', 'mean'),
                property_count=('property_id', 'count')
            ).reset_index()

            for _, row in suburb_stats.iterrows():
                suburb_records.append({
                    "suburb": row['property_locality'],
                    "year": year,
                    "avg_cagr": row['avg_cagr'],
                    "property_count": int(row['property_count'])
                })

        db.query(StreetGrowth).delete()
        if street_records:
            # Insert in chunks if too large
            for i in range(0, len(street_records), 10000):
                db.bulk_insert_mappings(StreetGrowth, street_records[i:i+10000])
            logger.info(f"Calculated {len(street_records)} street-year growth records.")

        db.query(SuburbGrowth).delete()
        if suburb_records:
            db.bulk_insert_mappings(SuburbGrowth, suburb_records)
            logger.info(f"Calculated {len(suburb_records)} suburb-year growth records.")

        # --- Overall Summary Calculations ---
        logger.info("Calculating overall summaries...")
        from .models import StreetSummary, SuburbSummary

        # Street Summary
        # We need unique properties and total sales from the original 'df' (which has all records)
        street_summary_stats = df.groupby(['property_street_name', 'property_locality', 'property_post_code']).agg(
            unique_properties=('property_id', 'nunique'),
            total_sales=('id', 'count')
        ).reset_index()

        # Join with avg CAGR from growth_df
        street_cagr_overall = growth_df.groupby(['property_street_name', 'property_locality', 'property_post_code']).agg(
            avg_cagr=('cagr', 'mean')
        ).reset_index()

        street_summary_df = street_summary_stats.merge(street_cagr_overall, on=['property_street_name', 'property_locality', 'property_post_code'], how='left')
        
        # Identify top performers (e.g., top 10% by CAGR)
        cagr_threshold = street_summary_df['avg_cagr'].quantile(0.9) if not street_summary_df['avg_cagr'].dropna().empty else 0
        street_summary_df['is_top_performer'] = (street_summary_df['avg_cagr'] >= cagr_threshold).astype(int)

        street_summary_records = []
        for _, row in street_summary_df.iterrows():
            street_summary_records.append({
                "street_name": row['property_street_name'],
                "suburb": row['property_locality'],
                "post_code": int(row['property_post_code']),
                "unique_properties": int(row['unique_properties']),
                "total_sales": int(row['total_sales']),
                "avg_cagr": row['avg_cagr'],
                "is_top_performer": int(row['is_top_performer'])
            })

        db.query(StreetSummary).delete()
        if street_summary_records:
            for i in range(0, len(street_summary_records), 10000):
                db.bulk_insert_mappings(StreetSummary, street_summary_records[i:i+10000])

        # Suburb Summary
        suburb_summary_stats = df.groupby(['property_locality']).agg(
            unique_properties=('property_id', 'nunique'),
            total_sales=('id', 'count')
        ).reset_index()

        suburb_cagr_overall = growth_df.groupby(['property_locality']).agg(
            avg_cagr=('cagr', 'mean')
        ).reset_index()

        suburb_summary_df = suburb_summary_stats.merge(suburb_cagr_overall, on=['property_locality'], how='left')
        
        cagr_threshold_suburb = suburb_summary_df['avg_cagr'].quantile(0.9) if not suburb_summary_df['avg_cagr'].dropna().empty else 0
        suburb_summary_df['is_top_performer'] = (suburb_summary_df['avg_cagr'] >= cagr_threshold_suburb).astype(int)

        suburb_summary_records = []
        for _, row in suburb_summary_df.iterrows():
            suburb_summary_records.append({
                "suburb": row['property_locality'],
                "unique_properties": int(row['unique_properties']),
                "total_sales": int(row['total_sales']),
                "avg_cagr": row['avg_cagr'],
                "is_top_performer": int(row['is_top_performer'])
            })

        db.query(SuburbSummary).delete()
        if suburb_summary_records:
            db.bulk_insert_mappings(SuburbSummary, suburb_summary_records)

        logger.info(f"Summarized {len(street_summary_records)} streets and {len(suburb_summary_records)} suburbs.")
        db.commit()

    finally:
        db.close()

if __name__ == "__main__":
    calculate_growth_metrics()

