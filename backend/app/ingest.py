import os
import urllib.request
import zipfile
import io
import pandas as pd
from datetime import date, timedelta, datetime
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base
from .models import Sale

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

URL_BASE = 'https://www.valuergeneral.nsw.gov.au/__psi/'
YEARLY_URL = URL_BASE + 'yearly/'
DOWNLOAD_DIR = Path('backend/data')

def download_file(url: str, filepath: Path) -> bool:
    """
    Download a file from a URL to a local path.
    """
    try:
        logger.info(f"Downloading {url}...")
        # Add a timeout and a user agent if needed
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as response, open(filepath, 'wb') as out_file:
            out_file.write(response.read())
        return True
    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
        return False

def extract_dat_lines_from_nested_zip(zip_filepath: Path) -> List[str]:
    """
    Extract data lines from DAT files inside nested weekly ZIPs within a yearly ZIP.
    """
    dat_lines: List[str] = []
    try:
        # Outer zip (Yearly)
        with zipfile.ZipFile(zip_filepath, 'r') as outer_zip:
            for file_info in outer_zip.namelist():
                # Inner zips (Weekly)
                if file_info.lower().endswith(".zip"):
                    try:
                        inner_zip_data = io.BytesIO(outer_zip.read(file_info))
                        with zipfile.ZipFile(inner_zip_data) as inner_zip:
                            for inner_file in inner_zip.namelist():
                                if inner_file.lower().endswith(".dat"):
                                    try:
                                        content = inner_zip.read(inner_file).decode("utf-8")
                                        dat_lines.extend(content.splitlines())
                                    except UnicodeDecodeError:
                                        # Fallback to latin-1 if utf-8 fails (sometimes common in older datasets)
                                        content = inner_zip.read(inner_file).decode("latin-1")
                                        dat_lines.extend(content.splitlines())
                                    except Exception as e:
                                        logger.warning(f"Failed to read DAT {inner_file} in {file_info}: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to read inner zip {file_info}: {e}")
    except zipfile.BadZipFile:
            logger.error(f"Bad zip file: {zip_filepath}")
    except Exception as e:
        logger.error(f"Error reading outer zip {zip_filepath}: {e}")
    return dat_lines

def download_recent_data(start_year: int = 2001, end_year: int = 2024) -> List[Path]:
    """
    Download yearly ZIP files for the specified range.
    """
    if not DOWNLOAD_DIR.exists():
        DOWNLOAD_DIR.mkdir(parents=True)
    
    downloaded_files: List[Path] = []
    
    # Iterate years
    for year in range(start_year, end_year + 1):
        filename = f"{year}.zip"
        filepath = DOWNLOAD_DIR / filename
        url = YEARLY_URL + filename
        
        if not filepath.exists():
            if download_file(url, filepath):
                downloaded_files.append(filepath)
        else:
            downloaded_files.append(filepath)
            
    return downloaded_files

def parse_record(line: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single line from a DAT file into a dictionary compatible with the Sale model.
    """
    if not line.startswith("B;"):
        return None
    parts = [p.strip() for p in line.split(";")]
    if len(parts) < 25:
        return None
    
    try:
        def parse_date(d_str: str) -> Optional[date]:
            if not d_str: return None
            try:
                return datetime.strptime(d_str, '%Y%m%d').date()
            except ValueError:
                return None
        
        def parse_float(n_str: str) -> Optional[float]:
            if not n_str: return None
            try:
                return float(n_str)
            except ValueError:
                return None

        def parse_int(n_str: str) -> Optional[int]:
            if not n_str: return None
            try:
                # Remove non-numeric chars like commas if any
                clean_str = ''.join(c for c in n_str if c.isdigit() or c == '-')
                return int(clean_str)
            except ValueError:
                return None

        contract_date = parse_date(parts[13])
        # Filter future dates
        if contract_date and contract_date > date.today():
             return None

        return {
            "district_code": parts[1],
            "property_id": parts[2],
            "sale_counter": parts[3],
            "download_datetime": parts[4],
            "property_name": parts[5].title(),
            "property_unit_number": parts[6],
            "property_house_number": parts[7],
            "property_street_name": parts[8].title(),
            "property_locality": parts[9].title(),
            "property_post_code": parse_int(parts[10]),
            "area": parse_float(parts[11]),
            "area_type": parts[12],
            "contract_date": contract_date,
            "settlement_date": parse_date(parts[14]),
            "purchase_price": parse_float(parts[15]),
            "zoning": parts[16],
            "nature_of_property": parts[17],
            "primary_purpose": parts[18].title(),
            "strata_lot_number": parts[19],
            "dealing_number": parts[23],
            "property_legal_description": None 
        }
    except Exception as e:
        logger.error(f"Error parsing line: {e}")
        return None

def ingest_data() -> None:
    """
    Orchestrate the ingestion process: download, parse, and store in DB.
    """
    logger.info("Starting ingestion...")
    Base.metadata.create_all(bind=engine)
    
    files = download_recent_data()
    logger.info(f"Downloaded {len(files)} files.")
    
    all_records: List[Dict[str, Any]] = []
    for f in files:
        lines = extract_dat_lines_from_nested_zip(f)
        for line in lines:
            record = parse_record(line)
            if record:
                all_records.append(record)
    
    logger.info(f"Parsed {len(all_records)} records. Saving to DB...")
    
    db: Session = SessionLocal()
    try:
        # Batch insert
        # Wiping is easier for MVP, but consider upsert for production
        db.query(Sale).delete()
        
        # Bulk insert in chunks to avoid memory issues with massive datasets
        chunk_size = 5000
        for i in range(0, len(all_records), chunk_size):
            chunk = all_records[i:i + chunk_size]
            db.bulk_insert_mappings(Sale, chunk)
            db.commit()
            logger.info(f"Inserted {min(i + chunk_size, len(all_records))} / {len(all_records)} records...")
            
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
    finally:
        db.close()
        
    logger.info("Ingestion complete.")

if __name__ == "__main__":
    ingest_data()

