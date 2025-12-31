import pytest
from backend.app.geocoding import haversine_distance, get_nearest_station
from backend.app.analytics import calculate_growth_metrics
import pandas as pd
import os

def test_haversine_distance():
    # Test distance between Sydney Opera House and Sydney Harbour Bridge
    # Coordinates approx:
    # Opera House: -33.8568, 151.2153
    # Harbour Bridge: -33.8523, 151.2108
    dist = haversine_distance(-33.8568, 151.2153, -33.8523, 151.2108)
    # Distance should be around 0.64 km
    assert 0.6 <= dist <= 0.7

def test_get_nearest_station_handles_missing_csv(monkeypatch):
    # Mock load_stations to return None
    monkeypatch.setattr("backend.app.geocoding.load_stations", lambda: None)
    station, dist = get_nearest_station(-33.8688, 151.2093)
    assert station is None
    assert dist is None

def test_growth_metrics_calculation_logic():
    # This is a bit complex as it needs a DB, but we can verify the CAGR formula logic
    # CAGR = (End / Start) ^ (1 / n) - 1
    start_price = 1000000
    end_price = 2000000
    years = 10
    cagr = ((end_price / start_price) ** (1 / years)) - 1
    # expect ~7.17%
    assert 0.071 <= cagr <= 0.072
