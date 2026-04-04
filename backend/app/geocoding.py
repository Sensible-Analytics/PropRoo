import math
import os
from pathlib import Path
from typing import Optional

import pandas as pd

_STATIONS_DF: Optional[pd.DataFrame] = None


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _load_stations() -> Optional[pd.DataFrame]:
    global _STATIONS_DF
    if _STATIONS_DF is not None:
        return _STATIONS_DF
    stations_path = Path(__file__).resolve().parent.parent / "data" / "stations.csv"
    if stations_path.exists():
        try:
            _STATIONS_DF = pd.read_csv(stations_path)
        except Exception:
            pass
    return _STATIONS_DF


def get_nearest_station(
    lat: float, lon: float
) -> tuple[Optional[str], Optional[float]]:
    df = _load_stations()
    if df is None or df.empty:
        return None, None
    min_dist = float("inf")
    nearest = None
    for _, row in df.iterrows():
        dist = haversine_distance(lat, lon, row["Latitude"], row["Longitude"])
        if dist < min_dist:
            min_dist = dist
            nearest = row["Station"]
    return nearest, min_dist
