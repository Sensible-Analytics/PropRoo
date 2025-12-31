import logging
import time
from datetime import datetime
from typing import Callable, Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import BinaryExpression
from ..models import Sale
from ..database import SessionLocal

logger = logging.getLogger(__name__)

class BaseBackfill:
    """
    Base class for backfill operations to ensure consistent logging, 
    error handling, and database interaction.
    """
    def __init__(self, batch_id: int = 0):
        self.batch_id = batch_id
        self.db: Session = SessionLocal()

    def get_pending_records(self, filter_criterion: Any, offset: int = 0, limit: int = 100) -> List[Sale]:
        """Fetch records that need processing."""
        try:
            return self.db.query(Sale).filter(filter_criterion).offset(offset).limit(limit).all()
        except Exception as e:
            logger.error(f"[Batch {self.batch_id}] Failed to fetch records: {e}")
            return []

    def process_record(self, record: Sale, processing_func: Callable[[Sale], Optional[Dict[str, Any]]]) -> bool:
        """Process a single record using the provided function and commit changes."""
        try:
            results = processing_func(record)
            if results:
                for key, value in results.items():
                    setattr(record, key, value)
                
                self.db.commit()
                return True
        except Exception as e:
            logger.error(f"[Batch {self.batch_id}] Error processing record {record.id}: {e}")
            self.db.rollback()
        return False

    def close(self) -> None:
        """Close the database session."""
        self.db.close()

def run_backfill(processing_func: Callable[[Sale], Optional[Dict[str, Any]]], 
                 filter_criterion: Any, 
                 limit: int = 100, 
                 offset: int = 0, 
                 batch_id: int = 0) -> None:
    """Utility function to run a backfill operation."""
    backfill = BaseBackfill(batch_id=batch_id)
    records = backfill.get_pending_records(filter_criterion, offset=offset, limit=limit)
    
    if not records:
        logger.info(f"[Batch {batch_id}] No records found for processing.")
        backfill.close()
        return

    logger.info(f"[Batch {batch_id}] Processing {len(records)} records (offset: {offset}).")
    
    updated_count = 0
    for record in records:
        if backfill.process_record(record, processing_func):
            updated_count += 1
            
    logger.info(f"[Batch {batch_id}] Successfully updated {updated_count} records.")
    backfill.close()
