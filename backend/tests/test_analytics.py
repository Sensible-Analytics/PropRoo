import pytest
from backend.app.analytics import calculate_cagr

def test_calculate_cagr_holding_six_months():
    # Held for 1 year, price doubled
    cagr, total = calculate_cagr(100.0, 200.0, 1.0)
    assert cagr == 1.0  # 100% growth
    assert total == 1.0

def test_calculate_cagr_less_than_six_months():
    # Held for 0.4 years, price doubled
    cagr, total = calculate_cagr(100.0, 200.0, 0.4)
    assert cagr == 0.0  # Should ignore CAGR
    assert total == 1.0 # But keep total growth

def test_calculate_cagr_five_years():
    # (150/100)^(1/5) - 1 = 1.5^0.2 - 1 approx 0.08447
    cagr, total = calculate_cagr(100.0, 150.0, 5.0)
    assert pytest.approx(cagr, 0.0001) == 0.08447
    assert total == 0.5

def test_calculate_cagr_loss():
    # (50/100)^(1/1) - 1 = -0.5
    cagr, total = calculate_cagr(100.0, 50.0, 1.0)
    assert cagr == -0.5
    assert total == -0.5

def test_calculate_cagr_zero_years():
    # Should handle division by zero if it somehow bypasses the < 0.5 check
    cagr, total = calculate_cagr(100.0, 200.0, 0.0)
    assert cagr == 0.0
    assert total == 1.0
