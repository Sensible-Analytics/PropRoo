import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import get_db, Base, engine
from sqlalchemy.orm import sessionmaker

# Set up a test database (in-memory for integration tests)
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
test_engine = sessionmaker(autocommit=False, autoflush=False, bind=engine) # Reuse engine for now but maybe better to use separate

client = TestClient(app)

def test_read_sales():
    response = client.get("/api/sales?limit=5")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_property_history_invalid_id():
    # Should return empty or 404 depending on implementation, 
    # currently it returns empty list if not found
    response = client.get("/api/property/nonexistent_id/history")
    assert response.status_code == 200
    assert response.json() == []

def test_stats_endpoints():
    response = client.get("/api/stats/top_suburbs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
