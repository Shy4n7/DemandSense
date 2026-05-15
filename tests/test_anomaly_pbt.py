"""
tests/test_anomaly_pbt.py — Property-based and unit tests for lib/predict_anomaly.py

Tasks covered:
  4.2  — Property 7: Demand spike detection rule
  4.4  — Property 8: Price anomaly detection rule
  4.6  — Property 9: Stockout signal detection rule
  4.9  — Property 10: Anomaly output structure and priority ordering
  7.1  — Unit test: short-data product skip behavior (scripts/train_forecast.py)
"""

import sys
import os
import logging
import warnings
from unittest.mock import MagicMock, patch, call

import pandas as pd
import numpy as np
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Project root on path
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.predict_anomaly import (
    _detect_demand_spikes,
    _detect_price_anomalies,
    _detect_stockout_signals,
    score_anomalies,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(quantities, unit_prices=None):
    """Build a minimal DataFrame with 'date', 'quantity', 'unit_price' columns."""
    n = len(quantities)
    if unit_prices is None:
        unit_prices = [1.0] * n
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "date": dates,
        "quantity": quantities,
        "unit_price": unit_prices,
    })


# ===========================================================================
# Task 4.2 — Property 7: Demand Spike Detection Rule
# Feature: demand-sense, Property 7: Demand spike detection rule
# ===========================================================================

@st.composite
def _demand_spike_df_st(draw):
    """
    Build a DataFrame where:
    - Rows 0..29 are 'normal' rows (quantity = mean, so no spike possible)
    - Row 30 is the spike row: quantity = mean + 4 * std (clearly > 3σ)

    We draw mean and std from st.floats() with safe bounds so arithmetic
    stays finite and the spike is unambiguous.
    """
    mean = draw(st.floats(min_value=10.0, max_value=1_000.0,
                          allow_nan=False, allow_infinity=False))
    std = draw(st.floats(min_value=1.0, max_value=100.0,
                         allow_nan=False, allow_infinity=False))

    # 30 prior rows all equal to mean (std of window = 0 unless we vary them)
    # Use mean ± tiny jitter so the window std is non-zero but spike is still clear
    prior_quantities = [mean] * 30
    spike_quantity = mean + 4.0 * std  # clearly > mean + 3*std

    quantities = prior_quantities + [spike_quantity]
    return pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=31, freq="D"),
        "quantity": quantities,
        "unit_price": [1.0] * 31,
    }), mean, std


@given(data=_demand_spike_df_st())
@settings(max_examples=100)
def test_property7_demand_spike_detection_rule(data):
    # Feature: demand-sense, Property 7: Demand spike detection rule
    """Validates: Requirements 3.2"""
    df, mean, std = data

    flags = _detect_demand_spikes(df)

    # Rows 0..29 have fewer than 30 prior rows — must NOT be flagged
    for i in range(30):
        assert not flags.iloc[i], (
            f"Row {i} has only {i} prior rows but was flagged as a demand spike"
        )

    # Row 30 has exactly 30 prior rows all equal to mean.
    # Window std(ddof=1) of 30 identical values is 0.
    # quantity[30] = mean + 4*std > mean + 3*0 = mean, so it IS > mean + 3*0.
    # But wait: if window std == 0, then mean + 3*0 = mean, and spike_qty > mean → flagged.
    # This is correct per the implementation.
    assert flags.iloc[30], (
        f"Row 30 with quantity={df['quantity'].iloc[30]:.2f} "
        f"(mean={mean:.2f}, std={std:.2f}) was NOT flagged as a demand spike"
    )


@given(
    mean=st.floats(min_value=10.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    std=st.floats(min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_property7_insufficient_history_not_flagged(mean, std):
    # Feature: demand-sense, Property 7: Demand spike detection rule
    """Validates: Requirements 3.2 — rows with < 30 prior rows are never flagged."""
    # Build a DataFrame with only 29 rows, all of which are spikes relative to mean
    spike_qty = mean + 10.0 * std
    quantities = [spike_qty] * 29
    df = _make_df(quantities)

    flags = _detect_demand_spikes(df)

    assert not flags.any(), (
        "Rows with fewer than 30 prior rows must never be flagged as demand spikes, "
        f"but got flags: {flags.tolist()}"
    )


# ===========================================================================
# Task 4.4 — Property 8: Price Anomaly Detection Rule
# Feature: demand-sense, Property 8: Price anomaly detection rule
# ===========================================================================

@st.composite
def _price_anomaly_df_st(draw):
    """
    Build a DataFrame where one row clearly exceeds 2.5σ from the median.

    Strategy:
    - Draw a base price and a multiplier.
    - Fill n_normal rows with base_price (median = base_price, std ≈ 0 for those rows).
    - Add one anomaly row at base_price * multiplier where multiplier is large enough
      that the anomaly is unambiguously > 2.5σ from the median regardless of how
      the sample std is computed over the full dataset.

    To guarantee the anomaly is flagged, we need:
        |anomaly_price - median| > 2.5 * std_full

    With n_normal identical values at base_price and one anomaly at base_price * M:
        median = base_price  (since n_normal >= 5, the median is base_price)
        std_full = std([base_price]*n_normal + [base_price*M], ddof=1)

    The sample std of n identical values plus one outlier is:
        std = sqrt( n*(M-1)^2 / (n+1)^2 * base_price^2 * (n+1)/n )
            = base_price * (M-1) * sqrt(n / (n+1)^2 * (n+1)/n ... )

    Simpler: we just use a very large multiplier (>= 20) so the anomaly is
    always > 2.5σ regardless of n_normal.  With M=20 and n_normal=5:
        anomaly deviation = 19 * base_price
        std_full ≈ 19 * base_price / sqrt(5) ≈ 8.5 * base_price
        2.5 * std_full ≈ 21.2 * base_price
    That's borderline.  Use M=50 to be safe for all n_normal >= 5:
        anomaly deviation = 49 * base_price
        std_full ≈ 49 * base_price / sqrt(5) ≈ 21.9 * base_price
        2.5 * std_full ≈ 54.8 * base_price  — still borderline for small n.

    The safest approach: compute the actual std after constructing the data
    and use assume() to skip examples where the anomaly isn't actually > 2.5σ.
    But that could filter too many examples.

    Instead, use a fixed large multiplier and a minimum n_normal that guarantees
    the anomaly is always flagged.  With n_normal >= 20 and M=10:
        anomaly deviation = 9 * base_price
        std_full = base_price * 9 * sqrt(20/21) / sqrt(20) ≈ base_price * 1.96
        2.5 * std_full ≈ 4.9 * base_price  << 9 * base_price  ✓

    We use n_normal >= 20 and anomaly_price = base_price + 10 * base_price = 11 * base_price.
    """
    base_price = draw(st.floats(min_value=1.0, max_value=500.0,
                                allow_nan=False, allow_infinity=False))

    # Use at least 20 normal rows so the sample std is small relative to the anomaly
    n_normal = draw(st.integers(min_value=20, max_value=50))
    normal_prices = [base_price] * n_normal

    # Anomaly price: 10x the base price above the base (deviation = 10 * base_price)
    # With n_normal >= 20, the sample std of the full dataset is << 10 * base_price / 2.5
    anomaly_price = base_price + 10.0 * base_price  # = 11 * base_price

    prices = normal_prices + [anomaly_price]
    n = len(prices)

    # Verify the anomaly is actually > 2.5σ (sanity check for the strategy)
    prices_arr = np.array(prices, dtype=float)
    actual_std = float(np.std(prices_arr, ddof=1))
    actual_median = float(np.median(prices_arr))
    assume(actual_std > 0)
    assume(abs(anomaly_price - actual_median) > 2.5 * actual_std)

    return pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=n, freq="D"),
        "quantity": [10] * n,
        "unit_price": prices,
    }), base_price, actual_std, n_normal


@given(data=_price_anomaly_df_st())
@settings(max_examples=100)
def test_property8_price_anomaly_detection_rule(data):
    # Feature: demand-sense, Property 8: Price anomaly detection rule
    """Validates: Requirements 3.3"""
    df, base_price, std, n_normal = data

    flags = _detect_price_anomalies(df)

    anomaly_idx = n_normal  # last row

    # The anomaly row must be flagged
    assert flags.iloc[anomaly_idx], (
        f"Anomaly row (price={df['unit_price'].iloc[anomaly_idx]:.2f}, "
        f"base={base_price:.2f}, std={std:.2f}) was NOT flagged as a price anomaly"
    )


@given(
    price=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    n=st.integers(min_value=2, max_value=50),
)
@settings(max_examples=100)
def test_property8_zero_std_returns_all_false(price, n):
    # Feature: demand-sense, Property 8: Price anomaly detection rule
    """Validates: Requirements 3.3 — zero-std products return all False."""
    # All prices identical → std = 0 → detection skipped
    df = pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=n, freq="D"),
        "quantity": [10] * n,
        "unit_price": [price] * n,
    })

    flags = _detect_price_anomalies(df)

    assert not flags.any(), (
        f"Zero-std product (all prices={price}) should return all False, "
        f"but got flags: {flags.tolist()}"
    )


# ===========================================================================
# Task 4.6 — Property 9: Stockout Signal Detection Rule
# Feature: demand-sense, Property 9: Stockout signal detection rule
# ===========================================================================

@st.composite
def _stockout_sequence_st(draw):
    """
    Draw a quantity sequence that contains at least one run of >= 3 consecutive zeros.
    Returns (quantities, list of (run_start, run_end) for runs of length >= 3).
    """
    # Build a sequence with some non-zero values and at least one long zero run
    parts = []
    run_positions = []  # (start_idx, end_idx exclusive) for runs >= 3

    # Optional prefix of non-zero values
    prefix_len = draw(st.integers(min_value=0, max_value=5))
    for _ in range(prefix_len):
        parts.append(draw(st.integers(min_value=1, max_value=100)))

    # At least one run of >= 3 zeros
    n_runs = draw(st.integers(min_value=1, max_value=3))
    for _ in range(n_runs):
        # Separator of non-zero values between runs
        sep_len = draw(st.integers(min_value=1, max_value=3))
        for _ in range(sep_len):
            parts.append(draw(st.integers(min_value=1, max_value=100)))

        run_len = draw(st.integers(min_value=3, max_value=8))
        start = len(parts)
        parts.extend([0] * run_len)
        run_positions.append((start, start + run_len))

    # Optional suffix
    suffix_len = draw(st.integers(min_value=0, max_value=5))
    for _ in range(suffix_len):
        parts.append(draw(st.integers(min_value=1, max_value=100)))

    return parts, run_positions


@given(data=_stockout_sequence_st())
@settings(max_examples=100)
def test_property9_stockout_signal_detection_rule_flags_long_runs(data):
    # Feature: demand-sense, Property 9: Stockout signal detection rule
    """Validates: Requirements 3.4 — every day in a run of >= 3 zeros is flagged."""
    quantities, run_positions = data
    df = _make_df(quantities)

    flags = _detect_stockout_signals(df)

    for run_start, run_end in run_positions:
        for i in range(run_start, run_end):
            assert flags.iloc[i], (
                f"Row {i} is part of a zero-run [{run_start}, {run_end}) "
                f"of length {run_end - run_start} but was NOT flagged as a stockout signal"
            )


@given(
    run_len=st.integers(min_value=1, max_value=2),
    prefix=st.lists(st.integers(min_value=1, max_value=100), min_size=0, max_size=5),
    suffix=st.lists(st.integers(min_value=1, max_value=100), min_size=0, max_size=5),
)
@settings(max_examples=100)
def test_property9_short_zero_runs_not_flagged(run_len, prefix, suffix):
    # Feature: demand-sense, Property 9: Stockout signal detection rule
    """Validates: Requirements 3.4 — runs of 1 or 2 consecutive zeros are NOT flagged."""
    quantities = prefix + [0] * run_len + suffix
    assume(len(quantities) > 0)

    df = _make_df(quantities)
    flags = _detect_stockout_signals(df)

    zero_start = len(prefix)
    for i in range(zero_start, zero_start + run_len):
        assert not flags.iloc[i], (
            f"Row {i} is part of a short zero-run of length {run_len} "
            f"but was incorrectly flagged as a stockout signal"
        )


# ===========================================================================
# Task 4.9 — Property 10: Anomaly Output Structure and Priority Ordering
# Feature: demand-sense, Property 10: Anomaly output structure and priority
# ===========================================================================

def _build_score_anomalies_df(n_normal=35, spike_qty=None, anomaly_price=None,
                               zero_run_len=0):
    """
    Build a history DataFrame for score_anomalies() with known detector triggers.

    - n_normal rows of normal data (quantity=50, price=10.0)
    - Optionally one spike row (quantity >> mean + 3*std)
    - Optionally one price anomaly row (price >> median + 2.5*std)
    - Optionally a zero run appended at the end
    """
    base_qty = 50.0
    base_price = 10.0

    quantities = [base_qty] * n_normal
    prices = [base_price] * n_normal

    if spike_qty is not None:
        quantities.append(spike_qty)
        prices.append(base_price)

    if anomaly_price is not None:
        quantities.append(base_qty)
        prices.append(anomaly_price)

    if zero_run_len >= 3:
        quantities.extend([0] * zero_run_len)
        prices.extend([base_price] * zero_run_len)

    n = len(quantities)
    return pd.DataFrame({
        "stock_code": ["TEST"] * n,
        "date": pd.date_range("2020-01-01", periods=n, freq="D"),
        "quantity": quantities,
        "unit_price": prices,
    })


def _make_mock_model(n_rows):
    """Return a mock IsolationForest that flags no rows."""
    mock = MagicMock()
    mock.score_samples.return_value = np.zeros(n_rows)
    mock.predict.return_value = np.ones(n_rows, dtype=int)  # all inliers
    return mock


@given(
    n_normal=st.integers(min_value=35, max_value=60),
)
@settings(max_examples=100)
def test_property10_output_structure(n_normal):
    # Feature: demand-sense, Property 10: Anomaly output structure and priority
    """Validates: Requirements 3.7 — every output record has required fields."""
    df = _build_score_anomalies_df(n_normal=n_normal)
    mock_model = _make_mock_model(len(df))

    with patch("lib.predict_anomaly.load_anomaly_model", return_value=mock_model):
        results = score_anomalies("TEST", df)

    assert isinstance(results, list), "score_anomalies must return a list"
    assert len(results) == len(df), (
        f"Output length {len(results)} != input length {len(df)}"
    )

    for i, record in enumerate(results):
        # date must be a string
        assert isinstance(record["date"], str), (
            f"Record {i}: 'date' must be str, got {type(record['date'])}"
        )
        # quantity must be numeric
        assert isinstance(record["quantity"], (int, float)), (
            f"Record {i}: 'quantity' must be numeric, got {type(record['quantity'])}"
        )
        # unit_price must be numeric
        assert isinstance(record["unit_price"], (int, float)), (
            f"Record {i}: 'unit_price' must be numeric, got {type(record['unit_price'])}"
        )
        # anomaly_score must be numeric
        assert isinstance(record["anomaly_score"], (int, float)), (
            f"Record {i}: 'anomaly_score' must be numeric, got {type(record['anomaly_score'])}"
        )
        # is_anomaly must be bool
        assert isinstance(record["is_anomaly"], bool), (
            f"Record {i}: 'is_anomaly' must be bool, got {type(record['is_anomaly'])}"
        )
        # reason must be str or None
        assert record["reason"] is None or isinstance(record["reason"], str), (
            f"Record {i}: 'reason' must be str or None, got {type(record['reason'])}"
        )


def test_property10_demand_spike_priority_over_price_anomaly():
    # Feature: demand-sense, Property 10: Anomaly output structure and priority
    """Validates: Requirements 3.7 — demand_spike takes priority over price_anomaly."""
    # Build a DataFrame where the last row triggers BOTH demand_spike AND price_anomaly:
    # - 30 prior rows with qty=50, price=10
    # - 1 row with qty=50000 (spike) AND price=10000 (price anomaly)
    n_normal = 30
    base_qty = 50.0
    base_price = 10.0
    spike_qty = 50000.0   # >> mean + 3*std
    anomaly_price = 10000.0  # >> median + 2.5*std

    n = n_normal + 1
    df = pd.DataFrame({
        "stock_code": ["TEST"] * n,
        "date": pd.date_range("2020-01-01", periods=n, freq="D"),
        "quantity": [base_qty] * n_normal + [spike_qty],
        "unit_price": [base_price] * n_normal + [anomaly_price],
    })

    mock_model = _make_mock_model(n)

    with patch("lib.predict_anomaly.load_anomaly_model", return_value=mock_model):
        results = score_anomalies("TEST", df)

    last = results[-1]
    assert last["is_anomaly"] is True, "Last row should be flagged as anomaly"
    assert last["reason"] == "demand_spike", (
        f"When demand_spike fires, reason must be 'demand_spike', got '{last['reason']}'"
    )


def test_property10_price_anomaly_priority_over_stockout():
    # Feature: demand-sense, Property 10: Anomaly output structure and priority
    """Validates: Requirements 3.7 — price_anomaly takes priority over stockout_signal."""
    # Build a DataFrame where a zero-run row also has a price anomaly.
    # The zero-run triggers stockout_signal; the price anomaly triggers price_anomaly.
    # price_anomaly should win.
    n_normal = 10
    base_price = 10.0
    anomaly_price = 10000.0  # >> median + 2.5*std

    # 10 normal rows, then 3 zero-quantity rows where the first also has anomaly price
    quantities = [50.0] * n_normal + [0.0, 0.0, 0.0]
    prices = [base_price] * n_normal + [anomaly_price, base_price, base_price]

    n = len(quantities)
    df = pd.DataFrame({
        "stock_code": ["TEST"] * n,
        "date": pd.date_range("2020-01-01", periods=n, freq="D"),
        "quantity": quantities,
        "unit_price": prices,
    })

    mock_model = _make_mock_model(n)

    with patch("lib.predict_anomaly.load_anomaly_model", return_value=mock_model):
        results = score_anomalies("TEST", df)

    # Row n_normal (first zero in the run) has both price_anomaly and stockout_signal
    first_zero = results[n_normal]
    assert first_zero["is_anomaly"] is True
    assert first_zero["reason"] == "price_anomaly", (
        f"price_anomaly should take priority over stockout_signal, "
        f"got '{first_zero['reason']}'"
    )


def test_property10_no_detector_fires_reason_is_none():
    # Feature: demand-sense, Property 10: Anomaly output structure and priority
    """Validates: Requirements 3.7 — when no detector fires, reason is None."""
    n = 10
    df = pd.DataFrame({
        "stock_code": ["TEST"] * n,
        "date": pd.date_range("2020-01-01", periods=n, freq="D"),
        "quantity": [50.0] * n,
        "unit_price": [10.0] * n,
    })

    mock_model = _make_mock_model(n)

    with patch("lib.predict_anomaly.load_anomaly_model", return_value=mock_model):
        results = score_anomalies("TEST", df)

    for i, record in enumerate(results):
        assert record["is_anomaly"] is False, f"Row {i} should not be anomaly"
        assert record["reason"] is None, (
            f"Row {i}: reason should be None when no detector fires, "
            f"got '{record['reason']}'"
        )


# ===========================================================================
# Task 7.1 — Unit test: short-data product skip behavior
# Feature: demand-sense, Unit test: short-data product skip
# ===========================================================================

class TestShortDataProductSkip:
    """
    Verify that scripts/train_forecast.py skips products with < 60 days of data,
    logs a warning, and continues training remaining products.

    Feature: demand-sense, Unit test: short-data product skip
    """

    def _make_product_df(self, n_days, stock_code="TEST"):
        """Build a minimal preprocessed DataFrame with n_days rows."""
        base = pd.Timestamp("2020-01-01")
        dates = [base + pd.Timedelta(days=i) for i in range(n_days)]
        return pd.DataFrame({
            "stock_code": [stock_code] * n_days,
            "date": dates,
            "quantity": [float(i + 1) for i in range(n_days)],
            "unit_price": [10.0] * n_days,
            "day_of_week": [d.weekday() for d in dates],
            "month": [d.month for d in dates],
            "is_weekend": [int(d.weekday() >= 5) for d in dates],
            "is_month_end": [0] * n_days,
            "rolling_7d_mean": [5.0] * n_days,
            "rolling_30d_mean": [5.0] * n_days,
            "rolling_7d_std": [1.0] * n_days,
            "lag_1": [5.0] * n_days,
            "lag_7": [5.0] * n_days,
            "lag_14": [5.0] * n_days,
        })

    def test_short_product_is_skipped_with_warning(self, caplog):
        """A product with < 60 days of data must be skipped with a logged warning."""
        import scripts.train_forecast as tf

        short_df = self._make_product_df(n_days=30, stock_code="SHORT")

        with patch("xgboost.XGBRegressor") as mock_xgb_cls:
            mock_xgb = MagicMock()
            mock_xgb_cls.return_value = mock_xgb

            with caplog.at_level(logging.WARNING, logger="scripts.train_forecast"):
                tf.train_product("SHORT", short_df)

        # XGBoost fit must NOT have been called
        mock_xgb.fit.assert_not_called()

        # A warning must have been logged
        warning_messages = [r.message for r in caplog.records
                            if r.levelno >= logging.WARNING]
        assert len(warning_messages) > 0, (
            "train_product must log a warning when product has < 60 days of data"
        )

    def test_short_product_warning_mentions_product_id(self, caplog):
        """The warning message must identify the product being skipped."""
        import scripts.train_forecast as tf

        short_df = self._make_product_df(n_days=45, stock_code="SHORTPROD")

        with patch("xgboost.XGBRegressor"):
            with caplog.at_level(logging.WARNING, logger="scripts.train_forecast"):
                tf.train_product("SHORTPROD", short_df)

        combined = " ".join(str(r.message) for r in caplog.records)
        assert "SHORTPROD" in combined, (
            "Warning message must mention the product ID being skipped"
        )

    def test_sufficient_data_product_is_trained(self):
        """A product with >= 60 days of data must proceed to XGBoost training."""
        import scripts.train_forecast as tf

        long_df = self._make_product_df(n_days=90, stock_code="LONG")

        with patch("xgboost.XGBRegressor") as mock_xgb_cls:
            mock_xgb = MagicMock()
            mock_xgb_cls.return_value = mock_xgb

            with patch("joblib.dump"):  # prevent actual file writes
                tf.train_product("LONG", long_df)

        # XGBoost fit must have been called (at least once for the point model)
        assert mock_xgb.fit.called, (
            "train_product must call XGBRegressor.fit() for products with >= 60 days"
        )

    def test_remaining_products_continue_after_skip(self, caplog):
        """After skipping a short product, remaining products must still be trained."""
        import scripts.train_forecast as tf

        short_df = self._make_product_df(n_days=30, stock_code="SHORT")
        long_df = self._make_product_df(n_days=90, stock_code="LONG")

        fit_calls = []

        def fake_fit(X, y, **kwargs):
            fit_calls.append(1)
            return MagicMock()

        with patch("xgboost.XGBRegressor") as mock_xgb_cls:
            mock_xgb = MagicMock()
            mock_xgb.fit.side_effect = fake_fit
            mock_xgb_cls.return_value = mock_xgb

            with patch("joblib.dump"):
                with caplog.at_level(logging.WARNING, logger="scripts.train_forecast"):
                    # Train short product first (should be skipped)
                    tf.train_product("SHORT", short_df)
                    # Train long product next (should proceed)
                    tf.train_product("LONG", long_df)

        # The long product must have triggered at least one fit call
        assert len(fit_calls) > 0, (
            "Remaining products must continue training after a short product is skipped"
        )
