"""
lib/predict_anomaly.py — Anomaly Detection Inference for DemandSense

Provides rule-based anomaly detectors and Isolation Forest model loading,
used by both the training script and the /api/anomalies serverless function.
"""

import os
import joblib
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Path to the models/ directory, relative to the project root.
# This file lives at lib/predict_anomaly.py, so the project root is one level up.
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")

# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------


class ModelNotFoundError(FileNotFoundError):
    """Raised when an Isolation Forest model file cannot be found on disk.

    Attributes:
        product_id: The product ID for which the model was not found.
    """

    def __init__(self, product_id: str) -> None:
        self.product_id = product_id
        super().__init__(
            f"Isolation Forest model not found for product '{product_id}'. "
            f"Expected file: {os.path.join(MODELS_DIR, f'iso_{product_id}.pkl')}"
        )


# ---------------------------------------------------------------------------
# Module-level model cache
# ---------------------------------------------------------------------------

_iso_cache: dict = {}

# ---------------------------------------------------------------------------
# Model Loading
# ---------------------------------------------------------------------------


def load_anomaly_model(product_id: str):
    """Load the Isolation Forest model for a given product, with caching.

    On the first call for a given product_id, loads the model from
    ``models/iso_{product_id}.pkl`` using joblib and stores it in the
    module-level ``_iso_cache``. Subsequent calls return the cached model
    without touching disk.

    Requirements: 3.1, 3.6

    Args:
        product_id: The StockCode string identifying the product.

    Returns:
        The loaded (or cached) IsolationForest model object.

    Raises:
        ModelNotFoundError: If the model file does not exist on disk.
    """
    if product_id not in _iso_cache:
        model_path = os.path.join(MODELS_DIR, f"iso_{product_id}.pkl")
        try:
            model = joblib.load(model_path)
        except FileNotFoundError:
            raise ModelNotFoundError(product_id)
        _iso_cache[product_id] = model
    return _iso_cache[product_id]


# ---------------------------------------------------------------------------
# Rule-Based Detectors
# ---------------------------------------------------------------------------


def _detect_demand_spikes(df: pd.DataFrame) -> pd.Series:
    """Flag rows where quantity exceeds 3 standard deviations above the
    30-day rolling mean, using only prior rows (exclusive window).

    For each row, the rolling mean and std are computed over the 30 rows
    immediately preceding it (i.e., the current row is NOT included in the
    window). If fewer than 30 prior rows exist for a given row, the demand
    spike flag is left unset (False) for that row.

    Requirements: 3.2

    Args:
        df: DataFrame for a single product with at least the columns:
            - ``date``: chronologically sorted dates
            - ``quantity``: daily sales quantity (numeric)
            The DataFrame must already be sorted chronologically.

    Returns:
        A boolean Series aligned with ``df.index``. True indicates a demand
        spike; False indicates no spike or insufficient history.
    """
    qty = df["quantity"].reset_index(drop=True)
    n = len(qty)

    spike_flags = pd.Series(False, index=range(n))

    for i in range(n):
        # We need at least 30 prior rows (indices 0 .. i-1)
        if i < 30:
            # Fewer than 30 prior rows — leave flag unset (False)
            continue

        # Use the 30 rows immediately before row i (exclusive of row i)
        window = qty.iloc[i - 30: i]
        rolling_mean = window.mean()
        rolling_std = window.std(ddof=1)  # sample std, consistent with pandas default

        if qty.iloc[i] > rolling_mean + 3 * rolling_std:
            spike_flags.iloc[i] = True

    # Re-align with the original df index
    spike_flags.index = df.index
    return spike_flags


def _detect_price_anomalies(df: pd.DataFrame) -> pd.Series:
    """Flag rows where unit_price deviates more than 2.5 standard deviations
    from the product's median unit price.

    If the standard deviation of unit_price across all rows is zero (i.e.,
    all prices are identical), detection is skipped and all flags are False.

    Requirements: 3.3

    Args:
        df: DataFrame for a single product with at least the column:
            - ``unit_price``: daily mean unit price (numeric)

    Returns:
        A boolean Series aligned with ``df.index``. True indicates a price
        anomaly; False indicates no anomaly or zero-std skip.
    """
    prices = df["unit_price"]
    std = prices.std(ddof=1)  # sample std

    # If std is zero (or NaN due to a single row), skip detection
    if pd.isna(std) or std == 0.0:
        return pd.Series(False, index=df.index)

    median = prices.median()
    return (prices - median).abs() > 2.5 * std


def _detect_stockout_signals(df: pd.DataFrame) -> pd.Series:
    """Flag every day that is part of a run of 3 or more consecutive days
    with quantity equal to zero.

    Requirements: 3.4

    Args:
        df: DataFrame for a single product with at least the column:
            - ``quantity``: daily sales quantity (numeric), sorted chronologically.

    Returns:
        A boolean Series aligned with ``df.index``. True indicates the row
        is part of a stockout run (≥ 3 consecutive zero-quantity days).
    """
    qty = df["quantity"].reset_index(drop=True)
    n = len(qty)
    flags = [False] * n

    i = 0
    while i < n:
        if qty.iloc[i] == 0:
            # Find the length of this zero-run
            run_start = i
            while i < n and qty.iloc[i] == 0:
                i += 1
            run_end = i  # exclusive
            run_length = run_end - run_start

            if run_length >= 3:
                for j in range(run_start, run_end):
                    flags[j] = True
        else:
            i += 1

    result = pd.Series(flags, index=range(n))
    result.index = df.index
    return result


# ---------------------------------------------------------------------------
# Anomaly Scoring
# ---------------------------------------------------------------------------


def score_anomalies(product_id: str, history: pd.DataFrame) -> list:
    """Run Isolation Forest + all three rule-based detectors on the full history.

    For each row in ``history``, computes:
    - ``anomaly_score``: raw Isolation Forest score via ``model.score_samples()``
    - ``is_anomaly``: True if IF flags the row (predict == -1) OR any rule-based
      detector fires
    - ``reason``: label assigned using priority order:
        demand_spike > price_anomaly > stockout_signal > isolation_forest
      When no detector fires, ``is_anomaly`` is False and ``reason`` is None.

    The IF model is loaded via ``load_anomaly_model(product_id)``.
    IF input features are ``[quantity, unit_price]`` (2-column array).

    Requirements: 3.7

    Args:
        product_id: The StockCode string identifying the product.
        history: DataFrame with at least the columns ``stock_code``, ``date``,
            ``quantity``, ``unit_price`` (plus any feature columns). Must be
            sorted chronologically.

    Returns:
        List of dicts, one per row, with keys:
            - ``date`` (ISO 8601 string)
            - ``quantity`` (float)
            - ``unit_price`` (float)
            - ``anomaly_score`` (float)
            - ``is_anomaly`` (bool)
            - ``reason`` (str or None)

    Raises:
        ModelNotFoundError: If the Isolation Forest model file does not exist.
    """
    model = load_anomaly_model(product_id)

    df = history.copy()
    df = df.sort_values("date").reset_index(drop=True)

    # --- Isolation Forest scoring ---
    features = df[["quantity", "unit_price"]].values
    # score_samples returns negative values; more negative = more anomalous
    anomaly_scores = model.score_samples(features)
    # predict returns -1 for anomalies, 1 for inliers
    if_predictions = model.predict(features)
    if_flags = pd.Series(if_predictions == -1, index=df.index)

    # --- Rule-based detectors ---
    demand_spike_flags = _detect_demand_spikes(df)
    price_anomaly_flags = _detect_price_anomalies(df)
    stockout_flags = _detect_stockout_signals(df)

    # --- Assemble output ---
    results = []
    for i in range(len(df)):
        row = df.iloc[i]

        ds = bool(demand_spike_flags.iloc[i])
        pa = bool(price_anomaly_flags.iloc[i])
        so = bool(stockout_flags.iloc[i])
        iso = bool(if_flags.iloc[i])

        is_anomaly = ds or pa or so or iso

        # Priority: demand_spike > price_anomaly > stockout_signal > isolation_forest
        if ds:
            reason = "demand_spike"
        elif pa:
            reason = "price_anomaly"
        elif so:
            reason = "stockout_signal"
        elif iso:
            reason = "isolation_forest"
        else:
            reason = None

        # Serialize date to ISO string
        date_val = row["date"]
        if hasattr(date_val, "isoformat"):
            date_str = date_val.isoformat()
        else:
            date_str = str(date_val)

        results.append({
            "date": date_str,
            "quantity": float(row["quantity"]),
            "unit_price": float(row["unit_price"]),
            "anomaly_score": float(anomaly_scores[i]),
            "is_anomaly": is_anomaly,
            "reason": reason,
        })

    return results
