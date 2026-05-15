"""
tests/test_api_handlers.py — Tests for api/importance.py, api/forecast.py,
                              and api/anomalies.py

Tasks covered:
  9.6  — Property 18: Feature Importance Response Structure and Ordering
  9.7  — Unit tests for importance endpoint error cases
  10.2 — Property 11: Forecast Array Length Equals Horizon
  10.3 — Property 12: Confidence Band Ordering Invariant
  10.4 — Property 13: Forecast Metrics Are Non-Negative
  10.5 — Property 14: Invalid Horizon Returns HTTP 400
  10.6 — Unit tests for forecast endpoint error cases
  10.8 — Property 15: Anomaly Count Invariant
  10.9 — Property 16: Anomaly Record Structure
  10.10 — Property 17: Missing or Malformed Product ID Returns HTTP 400
  10.11 — Unit test: unknown product_id returns 404 on anomalies endpoint
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Project root on path
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import api.importance as importance_module
import api.forecast as forecast_module
import api.anomalies as anomalies_module

from api.importance import app as importance_app
from api.forecast import app as forecast_app
from api.anomalies import app as anomalies_app

from lib.predict_forecast import ModelNotFoundError as ForecastModelNotFoundError
from lib.predict_forecast import ModelLoadError
from lib.predict_anomaly import ModelNotFoundError as AnomalyModelNotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_clean_records(product_id="TEST01", n=10):
    """Build a minimal list of clean.json-style records for a product."""
    import datetime as _dt
    base = _dt.date(2020, 1, 1)
    records = []
    for i in range(n):
        d = base + _dt.timedelta(days=i)
        records.append({
            "stock_code": product_id,
            "description": f"Test Product {product_id}",
            "date": d.isoformat(),
            "quantity": float(10 + i),
            "unit_price": 2.5,
            "day_of_week": d.weekday(),
            "month": d.month,
            "is_weekend": int(d.weekday() >= 5),
            "is_month_end": 0,
            "rolling_7d_mean": 10.0,
            "rolling_30d_mean": 10.0,
            "rolling_7d_std": 1.0,
            "lag_1": 10.0,
            "lag_7": 10.0,
            "lag_14": 10.0,
        })
    return records


def _make_forecast_entries(n):
    """Build n forecast entries satisfying lower <= predicted <= upper."""
    import datetime as _dt
    base = _dt.date(2021, 3, 1)
    return [
        {
            "date": (base + _dt.timedelta(days=i)).isoformat(),
            "predicted": 50.0 + i,
            "lower": 40.0 + i,
            "upper": 60.0 + i,
        }
        for i in range(n)
    ]


def _make_anomaly_records(n, is_anomaly=False):
    """Build n anomaly records with all required fields."""
    import datetime as _dt
    base = _dt.date(2020, 1, 1)
    return [
        {
            "date": (base + _dt.timedelta(days=i)).isoformat(),
            "quantity": float(10 + i),
            "unit_price": 2.5,
            "anomaly_score": -0.05 if is_anomaly else 0.1,
            "is_anomaly": is_anomaly,
            "reason": "demand_spike" if is_anomaly else None,
        }
        for i in range(n)
    ]


# ===========================================================================
# Task 9.6 — Property 18: Feature Importance Response Structure and Ordering
# Feature: demand-sense, Property 18: Importance structure and ordering
# ===========================================================================

@given(
    importances=st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=10,
    )
)
@settings(max_examples=50)
def test_property18_importance_structure_and_ordering(importances):
    # Feature: demand-sense, Property 18: Importance structure and ordering
    """Validates: Requirements 6.1, 6.2"""
    feature_names = [f"feature_{i}" for i in range(len(importances))]
    mock_features = [
        {"name": name, "importance": imp}
        for name, imp in zip(feature_names, importances)
    ]
    # Sort descending (as the real implementation does)
    mock_features_sorted = sorted(mock_features, key=lambda x: x["importance"], reverse=True)

    with patch("api.importance.get_feature_importances", return_value=mock_features_sorted):
        client = importance_app.test_client()
        response = client.get("/api/importance?product_id=TEST01")

    assert response.status_code == 200

    data = response.get_json()

    # Response must have product_id and features fields
    assert "product_id" in data, "Response missing 'product_id'"
    assert "features" in data, "Response missing 'features'"
    assert data["product_id"] == "TEST01"

    features = data["features"]
    assert isinstance(features, list), "'features' must be a list"

    # Every entry must have name (str) and importance (numeric)
    for entry in features:
        assert "name" in entry, f"Feature entry missing 'name': {entry}"
        assert "importance" in entry, f"Feature entry missing 'importance': {entry}"
        assert isinstance(entry["name"], str), (
            f"'name' must be str, got {type(entry['name'])}"
        )
        assert isinstance(entry["importance"], (int, float)), (
            f"'importance' must be numeric, got {type(entry['importance'])}"
        )

    # features array must be sorted descending by importance
    imp_values = [entry["importance"] for entry in features]
    for i in range(len(imp_values) - 1):
        assert imp_values[i] >= imp_values[i + 1], (
            f"Features not sorted descending at index {i}: "
            f"{imp_values[i]} < {imp_values[i + 1]}"
        )


# ===========================================================================
# Task 9.7 — Unit tests for importance endpoint error cases
# Feature: demand-sense, Unit tests: importance error cases
# ===========================================================================

def test_importance_missing_product_id_returns_400():
    """Missing product_id query param → 400."""
    client = importance_app.test_client()
    response = client.get("/api/importance")
    assert response.status_code == 400, (
        f"Expected 400 for missing product_id, got {response.status_code}"
    )
    body = response.get_json()
    assert "error" in body


def test_importance_empty_product_id_returns_400():
    """Empty product_id query param → 400."""
    client = importance_app.test_client()
    response = client.get("/api/importance?product_id=")
    assert response.status_code == 400, (
        f"Expected 400 for empty product_id, got {response.status_code}"
    )
    body = response.get_json()
    assert "error" in body


def test_importance_unknown_product_id_returns_404():
    """Unknown product_id (ModelNotFoundError) → 404."""
    with patch("api.importance.get_feature_importances",
               side_effect=ForecastModelNotFoundError("UNKNOWN")):
        client = importance_app.test_client()
        response = client.get("/api/importance?product_id=UNKNOWN")

    assert response.status_code == 404, (
        f"Expected 404 for unknown product_id, got {response.status_code}"
    )
    body = response.get_json()
    assert "error" in body


def test_importance_returns_correct_features():
    """Feature importances match what get_feature_importances returns."""
    mock_features = [
        {"name": "lag_1", "importance": 0.5},
        {"name": "rolling_7d_mean", "importance": 0.3},
        {"name": "day_of_week", "importance": 0.2},
    ]

    with patch("api.importance.get_feature_importances", return_value=mock_features):
        client = importance_app.test_client()
        response = client.get("/api/importance?product_id=TEST01")

    assert response.status_code == 200
    data = response.get_json()
    assert data["features"] == mock_features


# ===========================================================================
# Task 10.2 — Property 11: Forecast Array Length Equals Horizon
# Feature: demand-sense, Property 11: Forecast array length equals horizon
# ===========================================================================

@given(horizon=st.sampled_from([7, 14, 30]))
@settings(max_examples=50)
def test_property11_forecast_array_length_equals_horizon(horizon):
    # Feature: demand-sense, Property 11: Forecast array length equals horizon
    """Validates: Requirements 4.1"""
    mock_forecast = _make_forecast_entries(horizon)
    mock_metrics = {"mape": 5.0, "rmse": 10.0}
    mock_records = _make_clean_records("TEST01", n=30)

    with patch.object(forecast_module, "_data_cache", mock_records), \
         patch.object(forecast_module, "_load_error", None), \
         patch("api.forecast.generate_forecast", return_value=mock_forecast), \
         patch("api.forecast.compute_metrics", return_value=mock_metrics):
        client = forecast_app.test_client()
        response = client.post(
            "/api/forecast",
            json={"product_id": "TEST01", "horizon_days": horizon},
        )

    assert response.status_code == 200

    data = response.get_json()
    assert "forecast" in data, "Response missing 'forecast'"
    assert len(data["forecast"]) == horizon, (
        f"Expected forecast length {horizon}, got {len(data['forecast'])}"
    )


# ===========================================================================
# Task 10.3 — Property 12: Confidence Band Ordering Invariant
# Feature: demand-sense, Property 12: Confidence band ordering invariant
# ===========================================================================

@given(
    entries=st.lists(
        st.tuples(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
            st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
        ),
        min_size=1,
        max_size=30,
    )
)
@settings(max_examples=50)
def test_property12_confidence_band_ordering_invariant(entries):
    # Feature: demand-sense, Property 12: Confidence band ordering invariant
    """Validates: Requirements 4.2"""
    # Build forecast entries where lower <= predicted <= upper
    mock_forecast = []
    import datetime as _dt
    base = _dt.date(2021, 3, 1)
    for i, (predicted, lower_offset, upper_offset) in enumerate(entries):
        lower = predicted - lower_offset
        upper = predicted + upper_offset
        mock_forecast.append({
            "date": (base + _dt.timedelta(days=i)).isoformat(),
            "predicted": predicted,
            "lower": lower,
            "upper": upper,
        })

    mock_metrics = {"mape": 5.0, "rmse": 10.0}
    mock_records = _make_clean_records("TEST01", n=30)

    with patch.object(forecast_module, "_data_cache", mock_records), \
         patch.object(forecast_module, "_load_error", None), \
         patch("api.forecast.generate_forecast", return_value=mock_forecast), \
         patch("api.forecast.compute_metrics", return_value=mock_metrics):
        client = forecast_app.test_client()
        response = client.post(
            "/api/forecast",
            json={"product_id": "TEST01", "horizon_days": 7},
        )

    assert response.status_code == 200

    data = response.get_json()
    for i, entry in enumerate(data["forecast"]):
        assert entry["lower"] <= entry["predicted"], (
            f"Entry {i}: lower ({entry['lower']}) > predicted ({entry['predicted']})"
        )
        assert entry["predicted"] <= entry["upper"], (
            f"Entry {i}: predicted ({entry['predicted']}) > upper ({entry['upper']})"
        )


# ===========================================================================
# Task 10.4 — Property 13: Forecast Metrics Are Non-Negative
# Feature: demand-sense, Property 13: Forecast metrics non-negative
# ===========================================================================

@given(
    mape=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    rmse=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50)
def test_property13_forecast_metrics_non_negative(mape, rmse):
    # Feature: demand-sense, Property 13: Forecast metrics non-negative
    """Validates: Requirements 2.5, 4.3"""
    mock_forecast = _make_forecast_entries(7)
    mock_metrics = {"mape": mape, "rmse": rmse}
    mock_records = _make_clean_records("TEST01", n=30)

    with patch.object(forecast_module, "_data_cache", mock_records), \
         patch.object(forecast_module, "_load_error", None), \
         patch("api.forecast.generate_forecast", return_value=mock_forecast), \
         patch("api.forecast.compute_metrics", return_value=mock_metrics):
        client = forecast_app.test_client()
        response = client.post(
            "/api/forecast",
            json={"product_id": "TEST01", "horizon_days": 7},
        )

    assert response.status_code == 200

    data = response.get_json()
    assert "metrics" in data, "Response missing 'metrics'"
    metrics = data["metrics"]

    assert metrics["mape"] >= 0, (
        f"mape must be >= 0, got {metrics['mape']}"
    )
    assert metrics["rmse"] >= 0, (
        f"rmse must be >= 0, got {metrics['rmse']}"
    )


# ===========================================================================
# Task 10.5 — Property 14: Invalid Horizon Returns HTTP 400
# Feature: demand-sense, Property 14: Invalid horizon returns 400
# ===========================================================================

@given(
    horizon=st.integers().filter(lambda x: x not in {7, 14, 30})
)
@settings(max_examples=50)
def test_property14_invalid_horizon_returns_400(horizon):
    # Feature: demand-sense, Property 14: Invalid horizon returns 400
    """Validates: Requirements 4.5"""
    mock_records = _make_clean_records("TEST01", n=30)

    with patch.object(forecast_module, "_data_cache", mock_records), \
         patch.object(forecast_module, "_load_error", None):
        client = forecast_app.test_client()
        response = client.post(
            "/api/forecast",
            json={"product_id": "TEST01", "horizon_days": horizon},
        )

    assert response.status_code == 400, (
        f"Expected 400 for invalid horizon {horizon}, got {response.status_code}"
    )
    body = response.get_json()
    assert "error" in body


# ===========================================================================
# Task 10.6 — Unit tests for forecast endpoint error cases
# Feature: demand-sense, Unit tests: forecast error cases
# ===========================================================================

def test_forecast_unknown_product_id_returns_404():
    """Unknown product_id (ModelNotFoundError) → 404."""
    mock_records = _make_clean_records("TEST01", n=30)

    with patch.object(forecast_module, "_data_cache", mock_records), \
         patch.object(forecast_module, "_load_error", None), \
         patch("api.forecast.generate_forecast",
               side_effect=ForecastModelNotFoundError("UNKNOWN")):
        client = forecast_app.test_client()
        response = client.post(
            "/api/forecast",
            json={"product_id": "UNKNOWN", "horizon_days": 7},
        )

    assert response.status_code == 404, (
        f"Expected 404 for unknown product_id, got {response.status_code}"
    )
    body = response.get_json()
    assert "error" in body


def test_forecast_model_load_failure_returns_500():
    """Model load failure (ModelLoadError) → 500."""
    mock_records = _make_clean_records("TEST01", n=30)

    with patch.object(forecast_module, "_data_cache", mock_records), \
         patch.object(forecast_module, "_load_error", None), \
         patch("api.forecast.generate_forecast",
               side_effect=ModelLoadError("TEST01", "corrupt file")):
        client = forecast_app.test_client()
        response = client.post(
            "/api/forecast",
            json={"product_id": "TEST01", "horizon_days": 7},
        )

    assert response.status_code == 500, (
        f"Expected 500 for model load failure, got {response.status_code}"
    )
    body = response.get_json()
    assert "error" in body


def test_forecast_missing_product_id_returns_400():
    """Missing product_id → 400."""
    mock_records = _make_clean_records("TEST01", n=30)

    with patch.object(forecast_module, "_data_cache", mock_records), \
         patch.object(forecast_module, "_load_error", None):
        client = forecast_app.test_client()
        response = client.post(
            "/api/forecast",
            json={"horizon_days": 7},
        )

    assert response.status_code == 400
    body = response.get_json()
    assert "error" in body


def test_forecast_missing_horizon_returns_400():
    """Missing horizon_days → 400."""
    mock_records = _make_clean_records("TEST01", n=30)

    with patch.object(forecast_module, "_data_cache", mock_records), \
         patch.object(forecast_module, "_load_error", None):
        client = forecast_app.test_client()
        response = client.post(
            "/api/forecast",
            json={"product_id": "TEST01"},
        )

    assert response.status_code == 400
    body = response.get_json()
    assert "error" in body


# ===========================================================================
# Task 10.8 — Property 15: Anomaly Count Invariant
# Feature: demand-sense, Property 15: Anomaly count invariant
# ===========================================================================

@given(n_anomalies=st.integers(min_value=0, max_value=50))
@settings(max_examples=50)
def test_property15_anomaly_count_invariant(n_anomalies):
    # Feature: demand-sense, Property 15: Anomaly count invariant
    """Validates: Requirements 5.1"""
    mock_anomaly_records = _make_anomaly_records(n_anomalies, is_anomaly=True)
    mock_data_records = _make_clean_records("TEST01", n=max(n_anomalies, 1))

    with patch.object(anomalies_module, "_data_cache", mock_data_records), \
         patch.object(anomalies_module, "_load_error", None), \
         patch("api.anomalies.score_anomalies", return_value=mock_anomaly_records):
        client = anomalies_app.test_client()
        response = client.post(
            "/api/anomalies",
            json={"product_id": "TEST01"},
        )

    assert response.status_code == 200

    data = response.get_json()
    assert "anomalies" in data, "Response missing 'anomalies'"
    assert "total_anomalies" in data, "Response missing 'total_anomalies'"

    assert data["total_anomalies"] == len(data["anomalies"]), (
        f"total_anomalies ({data['total_anomalies']}) != "
        f"len(anomalies) ({len(data['anomalies'])})"
    )
    assert data["total_anomalies"] == n_anomalies, (
        f"Expected {n_anomalies} anomalies, got {data['total_anomalies']}"
    )


# ===========================================================================
# Task 10.9 — Property 16: Anomaly Record Structure
# Feature: demand-sense, Property 16: Anomaly record structure
# ===========================================================================

@given(
    records=st.lists(
        st.fixed_dictionaries({
            "date": st.just("2021-01-01"),
            "quantity": st.floats(min_value=0.0, max_value=10000.0,
                                  allow_nan=False, allow_infinity=False),
            "unit_price": st.floats(min_value=0.01, max_value=1000.0,
                                    allow_nan=False, allow_infinity=False),
            "anomaly_score": st.floats(min_value=-1.0, max_value=1.0,
                                       allow_nan=False, allow_infinity=False),
            "is_anomaly": st.booleans(),
            "reason": st.one_of(
                st.none(),
                st.sampled_from(["demand_spike", "price_anomaly",
                                 "stockout_signal", "isolation_forest"]),
            ),
        }),
        min_size=1,
        max_size=20,
    )
)
@settings(max_examples=50)
def test_property16_anomaly_record_structure(records):
    # Feature: demand-sense, Property 16: Anomaly record structure
    """Validates: Requirements 5.2"""
    mock_data_records = _make_clean_records("TEST01", n=30)

    with patch.object(anomalies_module, "_data_cache", mock_data_records), \
         patch.object(anomalies_module, "_load_error", None), \
         patch("api.anomalies.score_anomalies", return_value=records):
        client = anomalies_app.test_client()
        response = client.post(
            "/api/anomalies",
            json={"product_id": "TEST01"},
        )

    assert response.status_code == 200

    data = response.get_json()
    for i, entry in enumerate(data["anomalies"]):
        # date must be str
        assert isinstance(entry["date"], str), (
            f"Entry {i}: 'date' must be str, got {type(entry['date'])}"
        )
        # quantity must be numeric
        assert isinstance(entry["quantity"], (int, float)), (
            f"Entry {i}: 'quantity' must be numeric, got {type(entry['quantity'])}"
        )
        # unit_price must be numeric
        assert isinstance(entry["unit_price"], (int, float)), (
            f"Entry {i}: 'unit_price' must be numeric, got {type(entry['unit_price'])}"
        )
        # anomaly_score must be numeric
        assert isinstance(entry["anomaly_score"], (int, float)), (
            f"Entry {i}: 'anomaly_score' must be numeric, got {type(entry['anomaly_score'])}"
        )
        # is_anomaly must be bool
        assert isinstance(entry["is_anomaly"], bool), (
            f"Entry {i}: 'is_anomaly' must be bool, got {type(entry['is_anomaly'])}"
        )
        # reason must be str or None
        assert entry["reason"] is None or isinstance(entry["reason"], str), (
            f"Entry {i}: 'reason' must be str or None, got {type(entry['reason'])}"
        )


# ===========================================================================
# Task 10.10 — Property 17: Missing or Malformed Product ID Returns HTTP 400
# Feature: demand-sense, Property 17: Missing product_id returns 400
# ===========================================================================

@given(
    product_id=st.one_of(st.none(), st.just(""), st.just("   "))
)
@settings(max_examples=50)
def test_property17_missing_or_malformed_product_id_returns_400(product_id):
    # Feature: demand-sense, Property 17: Missing product_id returns 400
    """Validates: Requirements 5.5"""
    mock_data_records = _make_clean_records("TEST01", n=10)

    with patch.object(anomalies_module, "_data_cache", mock_data_records), \
         patch.object(anomalies_module, "_load_error", None):
        client = anomalies_app.test_client()

        if product_id is None:
            # Send request with no product_id field
            response = client.post(
                "/api/anomalies",
                json={},
            )
        else:
            response = client.post(
                "/api/anomalies",
                json={"product_id": product_id},
            )

    assert response.status_code == 400, (
        f"Expected 400 for product_id={product_id!r}, got {response.status_code}"
    )
    body = response.get_json()
    assert "error" in body


# ===========================================================================
# Task 10.11 — Unit test: unknown product_id returns 404 on anomalies endpoint
# Feature: demand-sense, Unit test: unknown product_id returns 404 (anomalies)
# ===========================================================================

def test_anomalies_unknown_product_id_returns_404():
    """Unknown product_id (ModelNotFoundError) → 404 on /api/anomalies."""
    mock_data_records = _make_clean_records("TEST01", n=10)

    with patch.object(anomalies_module, "_data_cache", mock_data_records), \
         patch.object(anomalies_module, "_load_error", None), \
         patch("api.anomalies.score_anomalies",
               side_effect=AnomalyModelNotFoundError("UNKNOWN")):
        client = anomalies_app.test_client()
        response = client.post(
            "/api/anomalies",
            json={"product_id": "UNKNOWN"},
        )

    assert response.status_code == 404, (
        f"Expected 404 for unknown product_id, got {response.status_code}"
    )
    body = response.get_json()
    assert "error" in body
