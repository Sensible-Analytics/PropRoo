from backend.app.ingest import download_recent_data, extract_dat_lines_from_nested_zip, parse_record, Sale, SessionLocal, engine, Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ingest():
    logger.info("Starting test ingestion (2023-2024)...")
    Base.metadata.create_all(bind=engine)
    
    # download only 2023-2024
    files = download_recent_data(start_year=2023, end_year=2024)
    logger.info(f"Downloaded {len(files)} files.")
    
    all_records = []
    for f in files:
        logger.info(f"Processing {f}...")
        lines = extract_dat_lines_from_nested_zip(f)
        logger.info(f"Extracted {len(lines)} lines.")
        count = 0
        for line in lines:
            record = parse_record(line)
            if record:
                all_records.append(record)
                count += 1
        logger.info(f"Parsed {count} records from {f}.")
    
    logger.info(f"Total parsed {len(all_records)} records. Saving to DB...")
    
    db = SessionLocal()
    try:
        # Check if we have data already?
        # db.query(Sale).delete() 
        # Don't delete for test, just append? Or Maybe delete to be clean.
        db.query(Sale).delete()
        
        # Insert in chunks
        chunk_size = 5000
        for i in range(0, len(all_records), chunk_size):
            chunk = all_records[i:i + chunk_size]
            db.bulk_insert_mappings(Sale, chunk)
            db.commit()
            logger.info(f"Inserted chunk {i} - {i+chunk_size}")
            
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
    finally:
        db.close()
        
    logger.info("Test ingestion complete.")

if __name__ == "__main__":
    test_ingest()
