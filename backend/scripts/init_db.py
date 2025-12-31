import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import Base, engine
from app.models import Sale, PropertyGrowth, StreetGrowth, SuburbGrowth, StreetSummary, SuburbSummary
from app.analytics import calculate_growth_metrics

def main():
    logger.info("Initializing database schema...")
    try:
        # Surgically drop only summary/growth tables to preserve 'sales' data
        # because re-ingesting 2.18M records takes a long time.
        tables_to_drop = [
            PropertyGrowth.__table__,
            StreetGrowth.__table__,
            SuburbGrowth.__table__,
            StreetSummary.__table__,
            SuburbSummary.__table__
        ]
        Base.metadata.drop_all(bind=engine, tables=tables_to_drop)
        logger.info("Summary and growth tables dropped.")
        
        # Create all (including any new ones)
        Base.metadata.create_all(bind=engine)
        logger.info("Tables created successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)

    logger.info("Running analytics to calculate growth metrics...")
    try:
        calculate_growth_metrics()
        logger.info("Analytics complete.")
    except Exception as e:
        logger.error(f"Analytics failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
