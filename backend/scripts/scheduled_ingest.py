"""
Scheduled data ingestion script with retention policy.
Run weekly via Railway cron job or external scheduler.
Keeps only current year data.
"""

import sys
import os
import logging
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models import (
    Sale,
    PropertyGrowth,
    StreetGrowth,
    SuburbGrowth,
    StreetSummary,
    SuburbSummary,
)
from app.ingest import ingest_data
from app.analytics import calculate_growth_metrics

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def apply_retention_policy():
    current_year = datetime.now().year
    cutoff_date = f"{current_year}-01-01"

    db = SessionLocal()
    try:
        old_records = db.query(Sale).filter(Sale.contract_date < cutoff_date).count()

        if old_records > 0:
            logger.info(f"Deleting {old_records} records older than {current_year}...")

            db.query(Sale).filter(Sale.contract_date < cutoff_date).delete(
                synchronize_session=False
            )

            db.query(PropertyGrowth).delete(synchronize_session=False)
            db.query(StreetGrowth).delete(synchronize_session=False)
            db.query(SuburbGrowth).delete(synchronize_session=False)
            db.query(StreetSummary).delete(synchronize_session=False)
            db.query(SuburbSummary).delete(synchronize_session=False)

            db.commit()
            logger.info("Old data deleted. Analytics cleared for recalculation.")
        else:
            logger.info("No old data to delete.")

    except Exception as e:
        logger.error(f"Error during retention policy: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def main():
    logger.info("=== Starting Scheduled Data Ingestion ===")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")

    try:
        logger.info("Step 1: Ingesting new data (latest years first)...")
        try:
            ingest_data(latest_first=True)
            logger.info("Data ingestion complete.")
        except Exception as e:
            logger.warning(f"Data ingestion failed (may be expected): {e}")

        logger.info("Step 2: Applying retention policy (keeping only current year)...")
        apply_retention_policy()

        logger.info("Step 3: Recalculating growth metrics...")
        calculate_growth_metrics()
        logger.info("Analytics recalculated.")

        logger.info("=== Scheduled Ingestion Complete ===")

    except Exception as e:
        logger.error(f"Scheduled ingestion failed: {e}")
        raise


if __name__ == "__main__":
    main()
