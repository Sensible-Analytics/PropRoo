import os
import sys
import logging
from pathlib import Path
from datetime import date, timedelta, datetime
from typing import List, Optional, Dict, Any
import urllib.request
import zipfile
import io
import pandas as pd

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

URL_BASE = "https://www.valuergeneral.nsw.gov.au/__psi/"
YEARLY_URL = URL_BASE + "yearly/"

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent / "data"))


def download_file(url: str, filepath: Path) -> bool:
    try:
        logger.info(f"Downloading {url}...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with (
            urllib.request.urlopen(req, timeout=60) as response,
            open(filepath, "wb") as out_file,
        ):
            out_file.write(response.read())
        return True
    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
        return False


def extract_dat_lines_from_nested_zip(zip_filepath: Path) -> List[str]:
    dat_lines: List[str] = []
    try:
        with zipfile.ZipFile(zip_filepath, "r") as outer_zip:
            for file_info in outer_zip.namelist():
                if file_info.lower().endswith(".zip"):
                    try:
                        inner_zip_data = io.BytesIO(outer_zip.read(file_info))
                        with zipfile.ZipFile(inner_zip_data) as inner_zip:
                            for inner_file in inner_zip.namelist():
                                if inner_file.lower().endswith(".dat"):
                                    try:
                                        content = inner_zip.read(inner_file).decode(
                                            "utf-8"
                                        )
                                        dat_lines.extend(content.splitlines())
                                    except UnicodeDecodeError:
                                        content = inner_zip.read(inner_file).decode(
                                            "latin-1"
                                        )
                                        dat_lines.extend(content.splitlines())
                                    except Exception as e:
                                        logger.warning(
                                            f"Failed to read DAT {inner_file} in {file_info}: {e}"
                                        )
                    except Exception as e:
                        logger.warning(f"Failed to read inner zip {file_info}: {e}")
    except zipfile.BadZipFile:
        logger.error(f"Bad zip file: {zip_filepath}")
    except Exception as e:
        logger.error(f"Error reading outer zip {zip_filepath}: {e}")
    return dat_lines


def parse_record(line: str) -> Optional[Dict[str, Any]]:
    if not line.startswith("B;"):
        return None
    parts = [p.strip() for p in line.split(";")]
    if len(parts) < 25:
        return None

    try:

        def parse_date(d_str: str) -> Optional[date]:
            if not d_str:
                return None
            try:
                return datetime.strptime(d_str, "%Y%m%d").date()
            except ValueError:
                return None

        def parse_float(n_str: str) -> Optional[float]:
            if not n_str:
                return None
            try:
                return float(n_str)
            except ValueError:
                return None

        def parse_int(n_str: str) -> Optional[int]:
            if not n_str:
                return None
            try:
                clean_str = "".join(c for c in n_str if c.isdigit() or c == "-")
                return int(clean_str)
            except ValueError:
                return None

        contract_date = parse_date(parts[13])
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
            "property_legal_description": None,
        }
    except Exception as e:
        logger.error(f"Error parsing line: {e}")
        return None


def download_recent_data(
    start_year: int = 2024, end_year: int = 2024, latest_first: bool = True
) -> List[Path]:
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True)

    downloaded_files: List[Path] = []

    years = list(range(start_year, end_year + 1))
    if latest_first:
        years = sorted(years, reverse=True)

    for year in years:
        filename = f"{year}.zip"
        filepath = DATA_DIR / filename
        url = YEARLY_URL + filename

        if not filepath.exists():
            if download_file(url, filepath):
                downloaded_files.append(filepath)
        else:
            logger.info(f"Using cached file for {year}")
            downloaded_files.append(filepath)

    return downloaded_files


def get_sale_columns() -> List[str]:
    return [
        "district_code",
        "property_id",
        "sale_counter",
        "download_datetime",
        "property_name",
        "property_unit_number",
        "property_house_number",
        "property_street_name",
        "property_locality",
        "property_post_code",
        "area",
        "area_type",
        "contract_date",
        "settlement_date",
        "purchase_price",
        "zoning",
        "nature_of_property",
        "primary_purpose",
        "strata_lot_number",
        "dealing_number",
        "property_legal_description",
    ]


def ingest_data(
    start_year: int = 2024, end_year: int = 2024, latest_first: bool = True
) -> None:
    logger.info(f"Starting ingestion for years {start_year}-{end_year}...")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    files = download_recent_data(
        start_year=start_year, end_year=end_year, latest_first=latest_first
    )
    logger.info(f"Downloaded {len(files)} files.")

    all_records: List[Dict[str, Any]] = []
    for f in files:
        lines = extract_dat_lines_from_nested_zip(f)
        for line in lines:
            record = parse_record(line)
            if record:
                all_records.append(record)

    logger.info(f"Parsed {len(all_records)} records. Writing to Parquet...")

    df = pd.DataFrame(all_records, columns=get_sale_columns())

    df.insert(0, "id", range(1, len(df) + 1))
    df["latitude"] = None
    df["longitude"] = None
    df["realestate_url"] = None
    df["domain_url"] = None
    df["listings_last_checked"] = None

    parquet_path = DATA_DIR / "sales.parquet"
    df.to_parquet(parquet_path, index=False, engine="pyarrow")
    logger.info(f"Written {len(df)} records to {parquet_path}")

    for f in files:
        if f.exists():
            f.unlink()
            logger.info(f"Deleted original ZIP: {f}")

    logger.info("Ingestion complete.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest NSW property sales data")
    parser.add_argument(
        "--start-year", type=int, default=2020, help="Start year (default: 2020)"
    )
    parser.add_argument(
        "--end-year", type=int, default=2024, help="End year (default: 2024)"
    )
    args = parser.parse_args()
    ingest_data(start_year=args.start_year, end_year=args.end_year)
