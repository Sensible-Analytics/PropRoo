import requests
import time
import logging
from sqlalchemy.orm import Session
from .models import Sale
import pandas as pd
import math
import os

logger = logging.getLogger(__name__)

# Nominatim has a strict usage policy: max 1 request per second.
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

def geocode_address(address: str) -> tuple[float, float]:
    """
    Convert a street address into latitude and longitude coordinates using Nominatim.
    
    Args:
        address: The full address string.
        
    Returns:
        A tuple of (latitude, longitude) or (None, None) if not found.
    """
    try:
        headers = {
            'User-Agent': 'AntigravityPropertyAnalytics/1.0',
            'Referer': 'http://localhost'
        }
        params = {
            'q': f"{address}, NSW, Australia",
            'format': 'json',
            'limit': 1
        }
        response = requests.get(NOMINATIM_URL, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
        else:
            logger.error(f"Geocoding error {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Geocoding exception: {e}")
    return None, None

def batch_geocode_sales(db: Session, sale_ids: list[int]) -> int:
    """
    Geocodes a list of sales record IDs and updates the database.
    
    Args:
        db: SQLAlchemy session.
        sale_ids: List of Sale record IDs to geocode.
        
    Returns:
        The number of successfully geocoded records.
    """
    updated_count = 0
    for sale_id in sale_ids:
        sale = db.query(Sale).filter(Sale.id == sale_id).first()
        if sale and not sale.latitude:
            address = f"{sale.property_house_number} {sale.property_street_name}, {sale.property_locality}"
            lat, lon = geocode_address(address)
            if lat and lon:
                sale.latitude = lat
                sale.longitude = lon
                updated_count += 1
                db.commit()
            
            time.sleep(1.5) # Respect Nominatim 1 req/sec limit
            
    return updated_count

# --- Station Distance Logic ---

STATIONS_DF = None

def load_stations() -> pd.DataFrame:
    """
    Load train station coordinates from a CSV file.
    
    Returns:
        Pandas DataFrame containing station names and coordinates.
    """
    global STATIONS_DF
    if STATIONS_DF is not None:
        return STATIONS_DF
    
    try:
        csv_path = "backend/data/stations.csv"
        if os.path.exists(csv_path):
            STATIONS_DF = pd.read_csv(csv_path)
        else:
            logger.warning("Stations CSV not found.")
    except Exception as e:
        logger.error(f"Error loading stations: {e}")
    return STATIONS_DF

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth (in km).
    """
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_nearest_station(lat: float, lon: float) -> tuple[str, float]:
    """
    Find the nearest train station to a given coordinate.
    
    Args:
        lat: Latitude of the property.
        lon: Longitude of the property.
        
    Returns:
        A tuple of (station_name, distance_in_km).
    """
    df = load_stations()
    if df is None or df.empty:
        return None, None
        
    min_dist = float('inf')
    nearest_station = None
    
    for _, row in df.iterrows():
        s_lat = row['Latitude']
        s_lon = row['Longitude']
        dist = haversine_distance(lat, lon, s_lat, s_lon)
        if dist < min_dist:
            min_dist = dist
            nearest_station = row['Station']
            
    return nearest_station, min_dist

