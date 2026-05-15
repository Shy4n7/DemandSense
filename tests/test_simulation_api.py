"""
tests/test_simulation_api.py — Tests for api/simulation.py

Follows the same pytest + Flask test client pattern as test_api_handlers.py.
"""

import sys
import os
import datetime
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Project root on path
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import api.simulation as simulation_module
from api.simulation import app as simulation_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_records(product_id: str = "TEST01", n: int = 10) -> list:
    """Build minimal clean.json-style records for a product."""
    base = datetime.date(2020, 1, 1)
    records = []
    for i in range(n):
        d = base + datetime.timedelta(days=i)
        records.append({
            "stock_code": product_id,
            "description": f"Test Product {product_id}",
            "date": d.isoformat(),
            "quantity": float(10 + i),
            "unit_price": 2.5,
        })
    return records


def _make_mixed_records() -> list:
    """Build records for two products with out-of-order dates."""
    base = datetime.date(2020, 6, 1)
    records = []
    # Product A — add in reverse order to test sorting
    for i in range(5, -1, -1):
        d = base + datetime.timedelta(days=i)
        records.append({
            "stock_code": "PROD_A",
            "description": "Product A",
            "date": d.isoformat(),
            "quantity": float(20 + i),
            "unit_price": 3.0,
        })
    # Product B
    for i in range(3):
        d = base + datetime.timedelta(days=i)
        records.append({
            "stock_code": "PROD_B",
            "description": "Product B",
            "date": d.isoformat(),
            "quantity": float(5 + i),
            "unit_price": 1.5,
        })
    return records


# ---------------------------------------------------------------------------
# Test: valid product_id returns 200 with data array and total_days
# ---------------------------------------------------------------------------

class TestSimulationValidRequest:
    def test_returns_200_for_valid_product(self):
        mock_records = _make_records("TEST01", n=10)
        with patch.object(simulation_module, "_data_cache", mock_records), \
             patch.object(simulation_module, "_load_error", None):
            client = simulation_app.test_client()
            response = client.get("/api/simulation?product_id=TEST01")

        assert response.status_code == 200

    def test_response_contains_product_id(self):
        mock_records = _make_records("TEST01", n=5)
        with patch.object(simulation_module, "_data_cache", mock_records), \
             patch.object(simulation_module, "_load_error", None):
            client = simulation_app.test_client()
            response = client.get("/api/simulation?product_id=TEST01")

        data = response.get_json()
        assert data["product_id"] == "TEST01"

    def test_response_contains_data_array(self):
        mock_records = _make_records("TEST01", n=7)
        with patch.object(simulation_module, "_data_cache", mock_records), \
             patch.object(simulation_module, "_load_error", None):
            client = simulation_app.test_client()
            response = client.get("/api/simulation?product_id=TEST01")

        data = response.get_json()
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 7

    def test_response_contains_total_days(self):
        mock_records = _make_records("TEST01", n=12)
        with patch.object(simulation_module, "_data_cache", mock_records), \
             patch.object(simulation_module, "_load_error", None):
            client = simulation_app.test_client()
            response = client.get("/api/simulation?product_id=TEST01")

        data = response.get_json()
        assert "total_days" in data
        assert data["total_days"] == 12

    def test_total_days_equals_data_length(self):
        mock_records = _make_records("TEST01", n=15)
        with patch.object(simulation_module, "_data_cache", mock_records), \
             patch.object(simulation_module, "_load_error", None):
            client = simulation_app.test_client()
            response = client.get("/api/simulation?product_id=TEST01")

        data = response.get_json()
        assert data["total_days"] == len(data["data"])


# ---------------------------------------------------------------------------
# Test: missing product_id returns 400
# ---------------------------------------------------------------------------

class TestSimulationMissingProductId:
    def test_missing_product_id_returns_400(self):
        client = simulation_app.test_client()
        response = client.get("/api/simulation")
        assert response.status_code == 400

    def test_empty_product_id_returns_400(self):
        client = simulation_app.test_client()
        response = client.get("/api/simulation?product_id=")
        assert response.status_code == 400

    def test_400_response_contains_error_field(self):
        client = simulation_app.test_client()
        response = client.get("/api/simulation")
        body = response.get_json()
        assert "error" in body

    def test_whitespace_product_id_returns_400(self):
        client = simulation_app.test_client()
        response = client.get("/api/simulation?product_id=   ")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Test: unknown product_id returns 404
# ---------------------------------------------------------------------------

class TestSimulationUnknownProduct:
    def test_unknown_product_returns_404(self):
        mock_records = _make_records("TEST01", n=5)
        with patch.object(simulation_module, "_data_cache", mock_records), \
             patch.object(simulation_module, "_load_error", None):
            client = simulation_app.test_client()
            response = client.get("/api/simulation?product_id=NONEXISTENT")

        assert response.status_code == 404

    def test_404_response_contains_error_field(self):
        mock_records = _make_records("TEST01", n=5)
        with patch.object(simulation_module, "_data_cache", mock_records), \
             patch.object(simulation_module, "_load_error", None):
            client = simulation_app.test_client()
            response = client.get("/api/simulation?product_id=NONEXISTENT")

        body = response.get_json()
        assert "error" in body


# ---------------------------------------------------------------------------
# Test: data is sorted ascending by date
# ---------------------------------------------------------------------------

class TestSimulationDataSorting:
    def test_data_sorted_ascending_by_date(self):
        """Records added in reverse order must be returned sorted ascending."""
        mock_records = _make_mixed_records()
        with patch.object(simulation_module, "_data_cache", mock_records), \
             patch.object(simulation_module, "_load_error", None):
            client = simulation_app.test_client()
            response = client.get("/api/simulation?product_id=PROD_A")

        data = response.get_json()
        dates = [entry["date"] for entry in data["data"]]
        assert dates == sorted(dates), (
            f"Dates are not sorted ascending: {dates}"
        )

    def test_only_requested_product_returned(self):
        """Records for other products must not appear in the response."""
        mock_records = _make_mixed_records()
        with patch.object(simulation_module, "_data_cache", mock_records), \
             patch.object(simulation_module, "_load_error", None):
            client = simulation_app.test_client()
            response = client.get("/api/simulation?product_id=PROD_B")

        data = response.get_json()
        assert data["total_days"] == 3  # PROD_B has 3 records


# ---------------------------------------------------------------------------
# Test: each record has date and actual_quantity fields
# ---------------------------------------------------------------------------

class TestSimulationRecordStructure:
    def test_each_record_has_date_field(self):
        mock_records = _make_records("TEST01", n=5)
        with patch.object(simulation_module, "_data_cache", mock_records), \
             patch.object(simulation_module, "_load_error", None):
            client = simulation_app.test_client()
            response = client.get("/api/simulation?product_id=TEST01")

        data = response.get_json()
        for i, entry in enumerate(data["data"]):
            assert "date" in entry, f"Record {i} missing 'date' field"

    def test_each_record_has_actual_quantity_field(self):
        mock_records = _make_records("TEST01", n=5)
        with patch.object(simulation_module, "_data_cache", mock_records), \
             patch.object(simulation_module, "_load_error", None):
            client = simulation_app.test_client()
            response = client.get("/api/simulation?product_id=TEST01")

        data = response.get_json()
        for i, entry in enumerate(data["data"]):
            assert "actual_quantity" in entry, f"Record {i} missing 'actual_quantity' field"

    def test_date_is_string(self):
        mock_records = _make_records("TEST01", n=3)
        with patch.object(simulation_module, "_data_cache", mock_records), \
             patch.object(simulation_module, "_load_error", None):
            client = simulation_app.test_client()
            response = client.get("/api/simulation?product_id=TEST01")

        data = response.get_json()
        for entry in data["data"]:
            assert isinstance(entry["date"], str)

    def test_actual_quantity_is_numeric(self):
        mock_records = _make_records("TEST01", n=3)
        with patch.object(simulation_module, "_data_cache", mock_records), \
             patch.object(simulation_module, "_load_error", None):
            client = simulation_app.test_client()
            response = client.get("/api/simulation?product_id=TEST01")

        data = response.get_json()
        for entry in data["data"]:
            assert isinstance(entry["actual_quantity"], (int, float))

    def test_actual_quantity_matches_source_quantity(self):
        """actual_quantity in response should equal quantity from source records."""
        mock_records = _make_records("TEST01", n=5)
        with patch.object(simulation_module, "_data_cache", mock_records), \
             patch.object(simulation_module, "_load_error", None):
            client = simulation_app.test_client()
            response = client.get("/api/simulation?product_id=TEST01")

        data = response.get_json()
        # Source records are sorted by date; response should match
        sorted_source = sorted(
            [r for r in mock_records if r["stock_code"] == "TEST01"],
            key=lambda r: r["date"],
        )
        for i, (entry, source) in enumerate(zip(data["data"], sorted_source)):
            assert entry["actual_quantity"] == pytest.approx(source["quantity"]), (
                f"Record {i}: actual_quantity {entry['actual_quantity']} "
                f"!= source quantity {source['quantity']}"
            )
