"""
tests/test_inventory.py — Unit tests for lib/inventory.calculate_inventory()

Follows the same pytest pattern as tests/test_preprocess.py.
All tests mock the forecast and data-loading layers so no real models or
data files are required.
"""

import sys
import os
import json
import math
import tempfile
import datetime
from unittest.mock import patch, MagicMock

import pandas as pd
import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Project root on path
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_history(product_id: str = "TEST", n_days: int = 60, qty: float = 50.0) -> list:
    """Build a minimal list of clean.json-style records for a product."""
    base = datetime.date(2020, 1, 1)
    records = []
    for i in range(n_days):
        d = base + datetime.timedelta(days=i)
        records.append({
            "stock_code": product_id,
            "description": f"Test Product {product_id}",
            "date": d.isoformat(),
            "quantity": qty,
            "unit_price": 2.5,
            "day_of_week": d.weekday(),
            "month": d.month,
            "is_weekend": int(d.weekday() >= 5),
            "is_month_end": 0,
            "rolling_7d_mean": qty,
            "rolling_30d_mean": qty,
            "rolling_7d_std": 5.0,
            "lag_1": qty,
            "lag_7": qty,
            "lag_14": qty,
        })
    return records


def _make_forecast_entries(n: int, predicted: float = 50.0) -> list:
    """Build n forecast entries with a fixed predicted value."""
    base = datetime.date(2021, 3, 1)
    return [
        {
            "date": (base + datetime.timedelta(days=i)).isoformat(),
            "predicted": predicted,
            "lower": predicted * 0.8,
            "upper": predicted * 1.2,
        }
        for i in range(n)
    ]


def _call_calculate(
    product_id="TEST",
    current_stock=500.0,
    lead_time_days=14,
    service_level=0.95,
    qty=50.0,
    n_days=60,
    predicted=50.0,
):
    """
    Call calculate_inventory() with mocked data and forecast layers.
    Returns the result dict.
    """
    mock_records = _make_history(product_id, n_days=n_days, qty=qty)
    mock_forecast = _make_forecast_entries(lead_time_days, predicted=predicted)

    import lib.inventory as inv_module

    with patch.object(inv_module, "_load_data", return_value=mock_records), \
         patch("lib.inventory.generate_forecast", return_value=mock_forecast):
        from lib.inventory import calculate_inventory
        return calculate_inventory(
            product_id=product_id,
            current_stock=current_stock,
            lead_time_days=lead_time_days,
            service_level=service_level,
        )


# ---------------------------------------------------------------------------
# Tests: return structure
# ---------------------------------------------------------------------------

class TestCalculateInventoryStructure:
    def test_returns_all_required_keys(self):
        result = _call_calculate()
        required_keys = {
            "product_id", "forecasted_demand", "safety_stock",
            "reorder_point", "current_stock", "suggested_order",
            "status", "reorder_alert",
        }
        assert required_keys.issubset(set(result.keys()))

    def test_product_id_matches_input(self):
        result = _call_calculate(product_id="85123A")
        assert result["product_id"] == "85123A"

    def test_current_stock_matches_input(self):
        result = _call_calculate(current_stock=300.0)
        assert result["current_stock"] == 300.0

    def test_reorder_alert_is_bool(self):
        result = _call_calculate()
        assert isinstance(result["reorder_alert"], bool)

    def test_status_is_valid_string(self):
        result = _call_calculate()
        assert result["status"] in {"SUFFICIENT", "REORDER NOW", "CRITICAL"}


# ---------------------------------------------------------------------------
# Tests: status logic
# ---------------------------------------------------------------------------

class TestStatusLogic:
    def test_sufficient_stock_returns_sufficient(self):
        """current_stock well above reorder_point → SUFFICIENT."""
        # With 14-day lead time and predicted=50/day, forecasted_demand ≈ 700
        # safety_stock ≈ Z(0.95) × std × √14 ≈ 1.645 × 0 × 3.74 = 0 (constant qty)
        # reorder_point ≈ 700; current_stock=2000 → SUFFICIENT
        result = _call_calculate(
            current_stock=2000.0,
            lead_time_days=14,
            predicted=50.0,
            qty=50.0,
        )
        assert result["status"] == "SUFFICIENT"
        assert result["reorder_alert"] is False

    def test_stock_at_reorder_point_returns_reorder_now(self):
        """current_stock == reorder_point → REORDER NOW."""
        # Force a known reorder_point by using constant demand (std=0 → safety_stock=0)
        # forecasted_demand = 14 × 50 = 700; reorder_point = 700
        # current_stock = 700 → REORDER NOW (stock <= reorder_point, > safety_stock=0)
        result = _call_calculate(
            current_stock=700.0,
            lead_time_days=14,
            predicted=50.0,
            qty=50.0,
        )
        assert result["status"] == "REORDER NOW"
        assert result["reorder_alert"] is True

    def test_stock_below_safety_stock_returns_critical(self):
        """current_stock <= safety_stock → CRITICAL."""
        # Use variable demand so safety_stock > 0
        # With std=20, Z(0.95)≈1.645, lead=14: safety_stock ≈ 1.645×20×√14 ≈ 123
        # Set current_stock=10 (well below safety_stock)
        mock_records = _make_history("TEST", n_days=60, qty=50.0)
        # Inject variability: alternate quantities to get std ≈ 20
        for i, r in enumerate(mock_records):
            r["quantity"] = 50.0 + (20.0 if i % 2 == 0 else -20.0)

        mock_forecast = _make_forecast_entries(14, predicted=50.0)

        import lib.inventory as inv_module
        with patch.object(inv_module, "_load_data", return_value=mock_records), \
             patch("lib.inventory.generate_forecast", return_value=mock_forecast):
            from lib.inventory import calculate_inventory
            result = calculate_inventory(
                product_id="TEST",
                current_stock=10.0,
                lead_time_days=14,
                service_level=0.95,
            )

        assert result["status"] == "CRITICAL"
        assert result["reorder_alert"] is True

    def test_reorder_alert_false_when_sufficient(self):
        result = _call_calculate(current_stock=9999.0)
        assert result["reorder_alert"] is False

    def test_reorder_alert_true_when_reorder_now(self):
        result = _call_calculate(current_stock=0.0)
        assert result["reorder_alert"] is True


# ---------------------------------------------------------------------------
# Tests: suggested_order is never negative
# ---------------------------------------------------------------------------

class TestSuggestedOrderNonNegative:
    def test_suggested_order_non_negative_when_sufficient(self):
        result = _call_calculate(current_stock=99999.0)
        assert result["suggested_order"] >= 0.0

    def test_suggested_order_non_negative_when_zero_stock(self):
        result = _call_calculate(current_stock=0.0)
        assert result["suggested_order"] >= 0.0

    def test_suggested_order_is_zero_when_stock_exceeds_reorder_point(self):
        # With constant demand (std=0), reorder_point = forecasted_demand = 14×50=700
        # current_stock=1000 > 700 → suggested_order = 0
        result = _call_calculate(
            current_stock=1000.0,
            lead_time_days=14,
            predicted=50.0,
            qty=50.0,
        )
        assert result["suggested_order"] == 0.0

    def test_suggested_order_positive_when_stock_below_reorder_point(self):
        result = _call_calculate(current_stock=0.0, lead_time_days=14, predicted=50.0)
        assert result["suggested_order"] > 0.0


# ---------------------------------------------------------------------------
# Tests: service level effect on safety stock
# ---------------------------------------------------------------------------

class TestServiceLevelEffect:
    def _safety_stock_for_sl(self, service_level: float) -> float:
        """Return safety_stock for a given service level with variable demand."""
        mock_records = _make_history("TEST", n_days=60, qty=50.0)
        # Inject variability
        for i, r in enumerate(mock_records):
            r["quantity"] = 50.0 + (15.0 if i % 2 == 0 else -15.0)

        mock_forecast = _make_forecast_entries(14, predicted=50.0)

        import lib.inventory as inv_module
        with patch.object(inv_module, "_load_data", return_value=mock_records), \
             patch("lib.inventory.generate_forecast", return_value=mock_forecast):
            from lib.inventory import calculate_inventory
            result = calculate_inventory(
                product_id="TEST",
                current_stock=500.0,
                lead_time_days=14,
                service_level=service_level,
            )
        return result["safety_stock"]

    def test_service_level_099_produces_higher_safety_stock_than_095(self):
        ss_95 = self._safety_stock_for_sl(0.95)
        ss_99 = self._safety_stock_for_sl(0.99)
        assert ss_99 > ss_95, (
            f"Safety stock at 99% ({ss_99:.2f}) should exceed "
            f"safety stock at 95% ({ss_95:.2f})"
        )

    def test_service_level_095_produces_higher_safety_stock_than_090(self):
        ss_90 = self._safety_stock_for_sl(0.90)
        ss_95 = self._safety_stock_for_sl(0.95)
        assert ss_95 > ss_90, (
            f"Safety stock at 95% ({ss_95:.2f}) should exceed "
            f"safety stock at 90% ({ss_90:.2f})"
        )


# ---------------------------------------------------------------------------
# Tests: formula correctness
# ---------------------------------------------------------------------------

class TestFormulaCorrectness:
    def test_forecasted_demand_equals_sum_of_predictions(self):
        """forecasted_demand should equal sum of predicted values from forecast."""
        predicted_per_day = 42.5
        lead_time = 7
        result = _call_calculate(
            lead_time_days=lead_time,
            predicted=predicted_per_day,
            qty=predicted_per_day,
        )
        expected = predicted_per_day * lead_time
        assert abs(result["forecasted_demand"] - expected) < 0.01

    def test_reorder_point_equals_demand_plus_safety_stock(self):
        result = _call_calculate()
        expected_rp = result["forecasted_demand"] + result["safety_stock"]
        assert abs(result["reorder_point"] - expected_rp) < 0.01

    def test_suggested_order_equals_reorder_point_minus_stock_when_below(self):
        result = _call_calculate(current_stock=0.0, lead_time_days=7, predicted=50.0)
        expected = result["reorder_point"] - 0.0
        assert abs(result["suggested_order"] - expected) < 0.01


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_raises_value_error_for_unknown_product(self):
        import lib.inventory as inv_module
        with patch.object(inv_module, "_load_data", return_value=[]):
            from lib.inventory import calculate_inventory
            with pytest.raises(ValueError, match="No history found"):
                calculate_inventory(
                    product_id="NONEXISTENT",
                    current_stock=100.0,
                    lead_time_days=7,
                )
