"""
tests/test_products_api.py — Tests for api/products.py

Tasks covered:
  9.2 — Property 19: Products Response Completeness and Structure
  9.3 — Property 20: Products Sorted by Descending Sales Volume
  9.4 — Unit test: missing data/clean.json returns 500
"""

import sys
import os
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Project root on path
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import api.products as products_module
from api.products import app


# ===========================================================================
# Task 9.2 — Property 19: Products Response Completeness and Structure
# Feature: demand-sense, Property 19: Products completeness and structure
# ===========================================================================

def _make_records(product_specs):
    """
    Build a list of clean.json-style records from a list of
    (stock_code, description, quantity) tuples.
    """
    records = []
    for stock_code, description, quantity in product_specs:
        records.append({
            "stock_code": stock_code,
            "description": description,
            "date": "2021-01-01",
            "quantity": quantity,
            "unit_price": 1.0,
        })
    return records


@given(
    product_specs=st.lists(
        st.tuples(
            st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=1, max_size=8),
            st.text(min_size=1, max_size=50),
            st.integers(min_value=1, max_value=1000),
        ),
        min_size=1,
        max_size=20,
        unique_by=lambda t: t[0],  # unique stock_codes
    )
)
@settings(max_examples=50)
def test_property19_products_completeness_and_structure(product_specs):
    # Feature: demand-sense, Property 19: Products completeness and structure
    """Validates: Requirements 7.1, 7.2"""
    mock_records = _make_records(product_specs)
    expected_product_ids = {spec[0] for spec in product_specs}

    with patch.object(products_module, "_data_cache", mock_records), \
         patch.object(products_module, "_load_error", None):
        client = app.test_client()
        response = client.get("/api/products")

    assert response.status_code == 200

    data = response.get_json()
    assert isinstance(data, list), "Response must be a JSON array"

    # Response must contain exactly the set of products in the mock data
    returned_ids = {entry["product_id"] for entry in data}
    assert returned_ids == expected_product_ids, (
        f"Returned product IDs {returned_ids} != expected {expected_product_ids}"
    )

    # Every entry must have product_id (str) and description (str)
    for entry in data:
        assert "product_id" in entry, f"Entry missing 'product_id': {entry}"
        assert "description" in entry, f"Entry missing 'description': {entry}"
        assert isinstance(entry["product_id"], str), (
            f"'product_id' must be str, got {type(entry['product_id'])}"
        )
        assert isinstance(entry["description"], str), (
            f"'description' must be str, got {type(entry['description'])}"
        )


# ===========================================================================
# Task 9.3 — Property 20: Products Sorted by Descending Sales Volume
# Feature: demand-sense, Property 20: Products sorted by volume
# ===========================================================================

@given(
    product_specs=st.lists(
        st.tuples(
            st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=1, max_size=8),
            st.text(min_size=1, max_size=50),
            st.integers(min_value=1, max_value=10000),
        ),
        min_size=2,
        max_size=15,
        unique_by=lambda t: t[0],  # unique stock_codes
    )
)
@settings(max_examples=50)
def test_property20_products_sorted_by_descending_volume(product_specs):
    # Feature: demand-sense, Property 20: Products sorted by volume
    """Validates: Requirements 7.3"""
    # Build multiple records per product to test volume aggregation
    mock_records = []
    expected_volumes = {}
    for stock_code, description, quantity in product_specs:
        # Add two records per product so volume = 2 * quantity
        mock_records.append({
            "stock_code": stock_code,
            "description": description,
            "date": "2021-01-01",
            "quantity": quantity,
            "unit_price": 1.0,
        })
        mock_records.append({
            "stock_code": stock_code,
            "description": description,
            "date": "2021-01-02",
            "quantity": quantity,
            "unit_price": 1.0,
        })
        expected_volumes[stock_code] = quantity * 2

    with patch.object(products_module, "_data_cache", mock_records), \
         patch.object(products_module, "_load_error", None):
        client = app.test_client()
        response = client.get("/api/products")

    assert response.status_code == 200

    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) >= 2

    # Assert products are in descending order of total quantity sum
    returned_volumes = [expected_volumes[entry["product_id"]] for entry in data]
    for i in range(len(returned_volumes) - 1):
        assert returned_volumes[i] >= returned_volumes[i + 1], (
            f"Products not sorted descending by volume at index {i}: "
            f"{returned_volumes[i]} < {returned_volumes[i + 1]}"
        )


# ===========================================================================
# Task 9.4 — Unit test: missing data/clean.json returns 500
# Feature: demand-sense, Unit test: missing data returns 500
# ===========================================================================

def test_missing_data_returns_500():
    # Feature: demand-sense, Unit test: missing data returns 500
    """Validates: Requirements 7.4 — missing data/clean.json returns HTTP 500."""
    with patch.object(products_module, "_data_cache", None), \
         patch.object(products_module, "_load_error", "Failed to load product data: file not found"):
        client = app.test_client()
        response = client.get("/api/products")

    assert response.status_code == 500, (
        f"Expected 500 when data is missing, got {response.status_code}"
    )

    body = response.get_json()
    assert "error" in body, "500 response must include an 'error' field"
