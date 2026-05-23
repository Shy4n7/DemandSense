"""
lib/predict_forecast.py — Forecast Inference for DemandSense

Loads XGBoost point and quantile models, generates iterative multi-step
forecasts, computes holdout metrics, and exposes feature importances.
Used by the /api/forecast and /api/importance serverless functions.
"""

import os
import math

import joblib
import numpy as np
import pandas as pd

from lib.preprocess import build_future_features

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Path to the models/ directory, relative to the project root.
# This file lives at lib/predict_forecast.py, so the project root is one level up.
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")

# The 10 feature columns used by all XGBoost models, in the correct order.
FEATURE_COLS = [
    "lag_1",
    "lag_7",
    "lag_14",
    "rolling_7d_mean",
    "rolling_30d_mean",
    "rolling_7d_std",
    "day_of_week",
    "month",
    "is_weekend",
    "is_month_end",
    "is_festival",
]

# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------


class ModelNotFoundError(FileNotFoundError):
    """Raised when a forecast model file cannot be found on disk.

    Attributes:
        product_id: The product ID for which the model was not found.
    """

    def __init__(self, product_id: str) -> None:
        self.product_id = product_id
        super().__init__(
            f"Forecast model not found for product '{product_id}'. "
            f"Expected files in: {MODELS_DIR}"
        )


class ModelLoadError(Exception):
    """Raised when a forecast model file exists but cannot be loaded.

    Attributes:
        product_id: The product ID for which loading failed.
        reason: A string describing the underlying error.
    """

    def __init__(self, product_id: str, reason: str) -> None:
        self.product_id = product_id
        self.reason = reason
        super().__init__(
            f"Failed to load forecast model for product '{product_id}': {reason}"
        )


# ---------------------------------------------------------------------------
# Module-level model cache
# ---------------------------------------------------------------------------

_model_cache: dict = {}

# ---------------------------------------------------------------------------
# Model Loading
# ---------------------------------------------------------------------------


def load_forecast_models(product_id: str):
    """Load point, lower, and upper XGBoost models for a given product.

    On the first call for a given product_id, loads all three models from
    the ``models/`` directory using joblib and stores them as a tuple in the
    module-level ``_model_cache``. Subsequent calls return the cached tuple
    without touching disk.

    Requirements: 4.8

    Args:
        product_id: The StockCode string identifying the product.

    Returns:
        Tuple of (point_model, lower_model, upper_model) XGBRegressor objects.

    Raises:
        ModelNotFoundError: If any of the three model files does not exist.
        ModelLoadError: If any model file exists but cannot be loaded.
    """
    if product_id not in _model_cache:
        _model_cache.clear()
        point_path = os.path.join(MODELS_DIR, f"xgb_{product_id}.pkl")
        lower_path = os.path.join(MODELS_DIR, f"xgb_lower_{product_id}.pkl")
        upper_path = os.path.join(MODELS_DIR, f"xgb_upper_{product_id}.pkl")

        try:
            point = joblib.load(point_path)
            lower = joblib.load(lower_path)
            upper = joblib.load(upper_path)
        except FileNotFoundError:
            raise ModelNotFoundError(product_id)
        except Exception as exc:
            raise ModelLoadError(product_id, str(exc))

        _model_cache[product_id] = (point, lower, upper)

    return _model_cache[product_id]


# ---------------------------------------------------------------------------
# Forecast Generation
# ---------------------------------------------------------------------------


def generate_forecast(product_id: str, horizon_days: int, history: pd.DataFrame) -> list:
    """Run an iterative multi-step forecast for the given product.

    Calls ``load_forecast_models`` to obtain the (point, lower, upper) models,
    then calls ``build_future_features`` to get the initial feature matrix.
    The feature matrix uses placeholder 0 quantities for future steps; this
    function replaces those placeholders iteratively using the predicted values
    from the point model so that lag and rolling features are accurate for
    each subsequent step.

    At each step:
    1. Extract the feature row for step t.
    2. Run point model → predicted.
    3. Run lower model → lower_val.
    4. Run upper model → upper_val.
    5. Clamp: lower_val = min(lower_val, predicted),
              upper_val = max(upper_val, predicted).
    6. Append {date, predicted, lower, upper} to output.
    7. Update the feature matrix for subsequent steps using the predicted value.

    Requirements: 4.1, 4.2

    Args:
        product_id: The StockCode string identifying the product.
        horizon_days: Number of future days to forecast (typically 7, 14, or 30).
        history: DataFrame of historical records for the product, sorted
            chronologically. Must contain at least ``date`` and ``quantity``
            columns plus all 10 FEATURE_COLS.

    Returns:
        List of dicts with keys:
            - ``date`` (ISO 8601 string)
            - ``predicted`` (float)
            - ``lower`` (float)
            - ``upper`` (float)
        Length equals ``horizon_days``.

    Raises:
        ModelNotFoundError: If any model file is missing.
        ModelLoadError: If any model file cannot be loaded.
    """
    point_model, lower_model, upper_model = load_forecast_models(product_id)

    # Build the initial feature matrix (placeholder 0 quantities for future steps)
    feature_df = build_future_features(history, horizon_days)

    # We need a mutable quantity history to update lag/rolling features iteratively.
    hist = history.copy()
    hist["date"] = pd.to_datetime(hist["date"])
    hist = hist.sort_values("date").reset_index(drop=True)
    qty_history: list = hist["quantity"].tolist()

    results = []

    for t in range(horizon_days):
        # Dynamically recompute lag and rolling features for the current step t
        # using the accumulated qty_history (which includes previous predictions).
        n = len(qty_history)
        
        lag_1 = qty_history[n - 1] if n >= 1 else 0
        lag_7 = qty_history[n - 7] if n >= 7 else 0
        lag_14 = qty_history[n - 14] if n >= 14 else 0
        
        window_7 = qty_history[max(0, n - 7): n]
        rolling_7d_mean = float(np.mean(window_7)) if window_7 else 0.0
        rolling_7d_std_val = float(np.std(window_7, ddof=1)) if len(window_7) >= 2 else 0.0
        
        window_30 = qty_history[max(0, n - 30): n]
        rolling_30d_mean = float(np.mean(window_30)) if window_30 else 0.0
        
        feature_df.at[feature_df.index[t], "lag_1"] = lag_1
        feature_df.at[feature_df.index[t], "lag_7"] = lag_7
        feature_df.at[feature_df.index[t], "lag_14"] = lag_14
        feature_df.at[feature_df.index[t], "rolling_7d_mean"] = rolling_7d_mean
        feature_df.at[feature_df.index[t], "rolling_7d_std"] = rolling_7d_std_val
        feature_df.at[feature_df.index[t], "rolling_30d_mean"] = rolling_30d_mean

        # Extract the feature row for step t
        row = feature_df.iloc[t]
        X = np.array([[row[col] for col in FEATURE_COLS]])

        # Run all three models
        predicted_base = float(point_model.predict(X)[0])
        lower_val = float(lower_model.predict(X)[0])
        upper_val = float(upper_model.predict(X)[0])

        # Clamp: lower ≤ predicted ≤ upper
        lower_val = min(lower_val, predicted_base)
        upper_val = max(upper_val, predicted_base)

        predicted = predicted_base
        if row["is_festival"] == 1:
            predicted = predicted_base * 4.5
            lower_val *= 4.5
            upper_val *= 4.5

        # Serialize date to YYYY-MM-DD string
        date_val = row["date"]
        if hasattr(date_val, "strftime"):
            date_str = date_val.strftime("%Y-%m-%d")
        elif hasattr(date_val, "isoformat"):
            date_str = date_val.isoformat().split("T")[0]
        else:
            date_str = str(date_val).split(" ")[0]

        results.append({
            "date": date_str,
            "predicted": predicted,
            "lower": lower_val,
            "upper": upper_val,
        })

        # Update qty_history with the baseline predicted value so subsequent steps
        # don't suffer from exponential compounding feedback loops.
        qty_history.append(predicted_base)

    return results


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def compute_metrics(product_id: str, history: pd.DataFrame) -> dict:
    """Compute MAPE and RMSE on the chronologically ordered 20% holdout split.

    Takes the last 20% of rows (by chronological order) as the holdout test
    set, runs the point model on the 10 FEATURE_COLS, and computes:
    - MAPE = mean(|actual - predicted| / max(actual, 1)) * 100
    - RMSE = sqrt(mean((actual - predicted)^2))

    Both values are guaranteed to be ≥ 0.

    Requirements: 2.4, 2.5, 4.3

    Args:
        product_id: The StockCode string identifying the product.
        history: DataFrame of historical records for the product, sorted
            chronologically. Must contain ``quantity`` and all 10 FEATURE_COLS.

    Returns:
        Dict with keys ``mape`` (float ≥ 0) and ``rmse`` (float ≥ 0).

    Raises:
        ModelNotFoundError: If any model file is missing.
        ModelLoadError: If any model file cannot be loaded.
    """
    point_model, _, _ = load_forecast_models(product_id)

    df = history.copy()
    df = df.sort_values("date").reset_index(drop=True)

    # Chronologically ordered 20% holdout split
    n = len(df)
    split_idx = int(n * 0.8)
    test_df = df.iloc[split_idx:]

    X_test = test_df[FEATURE_COLS].values
    y_actual = test_df["quantity"].values.astype(float)
    y_pred = point_model.predict(X_test).astype(float)

    # MAPE: avoid division by zero using max(actual, 1)
    mape = float(np.mean(np.abs(y_actual - y_pred) / np.maximum(y_actual, 1.0)) * 100.0)

    # RMSE
    rmse = float(math.sqrt(np.mean((y_actual - y_pred) ** 2)))

    # Guarantee non-negative (floating-point safety)
    mape = max(0.0, mape)
    rmse = max(0.0, rmse)

    return {"mape": mape, "rmse": rmse}


# ---------------------------------------------------------------------------
# Feature Importances
# ---------------------------------------------------------------------------


def get_feature_importances(product_id: str) -> list:
    """Return sorted feature importances from the point forecast model.

    Loads the point model via ``load_forecast_models`` and reads its
    ``feature_importances_`` attribute (a numpy array aligned with
    FEATURE_COLS). Returns the importances sorted in descending order.

    Requirements: 6.1, 6.2, 6.3

    Args:
        product_id: The StockCode string identifying the product.

    Returns:
        List of dicts sorted descending by importance, each with keys:
            - ``name`` (str): feature name from FEATURE_COLS
            - ``importance`` (float): importance value (may be negative)

    Raises:
        ModelNotFoundError: If any model file is missing.
        ModelLoadError: If any model file cannot be loaded.
    """
    point_model, _, _ = load_forecast_models(product_id)

    importances = point_model.feature_importances_

    paired = [
        {"name": name, "importance": float(imp)}
        for name, imp in zip(FEATURE_COLS, importances)
    ]

    # Sort descending by importance
    paired.sort(key=lambda x: x["importance"], reverse=True)

    return paired
