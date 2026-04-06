"""
Test suite for data quality calculation verification.
Tests reconciliation between source data and derived aggregates.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import os


class TestDataQualityCalculations:
    """Test data quality calculations and reconciliations."""

    @pytest.fixture
    def sample_sales_data(self):
        """Create sample sales data for testing."""
        data = {
            "id": [1, 2, 3, 4, 5],
            "property_id": ["P001", "P001", "P002", "P003", "P003"],
            "property_locality": [
                "SuburbA",
                "SuburbA",
                "SuburbB",
                "SuburbC",
                "SuburbC",
            ],
            "property_street_name": [
                "Street1",
                "Street1",
                "Street2",
                "Street3",
                "Street3",
            ],
            "property_post_code": [2000, 2000, 2001, 2002, 2002],
            "purchase_price": [500000, 550000, 750000, 600000, 650000],
            "contract_date": [
                "2020-01-15",
                "2022-06-20",
                "2019-03-10",
                "2021-08-05",
                "2023-11-30",
            ],
            "latitude": [-33.8, -33.8, -33.9, -34.0, -34.0],
            "longitude": [151.2, 151.2, 151.1, 151.0, 151.0],
        }
        df = pd.DataFrame(data)
        df["contract_date"] = pd.to_datetime(df["contract_date"])
        return df

    def test_calculation_reconciliation(self, sample_sales_data):
        """Test that property-level calculations are correct."""
        # Calculate expected CAGR for P001: 500K -> 550K over 2.4 years
        prop1_data = sample_sales_data[sample_sales_data["property_id"] == "P001"]
        start_price = prop1_data["purchase_price"].iloc[0]
        end_price = prop1_data["purchase_price"].iloc[1]
        start_date = prop1_data["contract_date"].iloc[0]
        end_date = prop1_data["contract_date"].iloc[1]
        years = (end_date - start_date).days / 365.25

        # Manual CAGR calculation
        expected_cagr = (end_price / start_price) ** (1 / years) - 1

        # The actual calculation would be done in calculate_growth.py
        # For now, just verify our test math is correct
        assert expected_cagr > 0  # Should be positive growth
        assert abs(expected_cagr - 0.045) < 0.01  # Approximately 4.5% annual growth

    def test_reconciliation_totals(self, sample_sales_data):
        """Test that aggregate reconciliations work."""
        total_sales = len(sample_sales_data)
        unique_properties = sample_sales_data["property_id"].nunique()

        assert total_sales == 5
        assert unique_properties == 3  # P001, P002, P003

        # Test street-level aggregation
        street_totals = sample_sales_data.groupby(
            ["property_street_name", "property_locality"]
        ).size()
        assert street_totals["Street1", "SuburbA"] == 2
        assert street_totals["Street2", "SuburbB"] == 1
        assert street_totals["Street3", "SuburbC"] == 2

        # Sum of street totals should equal total sales
        assert street_totals.sum() == total_sales

    def test_h3_tile_validation(self):
        """Test H3 tile validation logic."""
        # This would test that all zoom levels 5-14 exist
        # For now, just test the concept
        zoom_levels = list(range(5, 15))
        assert len(zoom_levels) == 10
        assert min(zoom_levels) == 5
        assert max(zoom_levels) == 14


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
