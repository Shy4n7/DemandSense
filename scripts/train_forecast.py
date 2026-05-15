"""
scripts/train_forecast.py — Forecast Model Training Script for DemandSense

Trains point, lower-bound (alpha=0.1), and upper-bound (alpha=0.9) XGBoost
models per product on the 10 engineered features.  Products with fewer than
60 days of data are skipped with a logged warning.

Serializes models to:
  models/xgb_{product_id}.pkl
  models/xgb_lower_{product_id}.pkl
  models/xgb_upper_{product_id}.pkl

Requirements: 2.1, 2.2, 2.3, 2.6, 2.7, 2.8
"""

import os
import sys
import json
import logging

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scripts.train_forecast")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_PATH = os.path.join(_PROJECT_ROOT, "data", "clean.json")
_MODELS_DIR = os.path.join(_PROJECT_ROOT, "models")

MIN_DAYS_FOR_TRAINING = 60

FEATURE_COLS = [
    "lag_1", "lag_7", "lag_14",
    "rolling_7d_mean", "rolling_30d_mean", "rolling_7d_std",
    "day_of_week", "month", "is_weekend", "is_month_end",
]
TARGET_COL = "quantity"

# ---------------------------------------------------------------------------
# Core training function
# ---------------------------------------------------------------------------


def train_product(product_id: str, df: pd.DataFrame) -> None:
    """Train point, lower, and upper XGBoost models for a single product.

    If the product has fewer than MIN_DAYS_FOR_TRAINING (60) days of data,
    logs a WARNING and returns without training.

    Args:
        product_id: The StockCode string identifying the product.
        df: Preprocessed DataFrame for this product with all feature columns
            and the 'quantity' target column.  Must be sorted chronologically.

    Requirements: 2.1, 2.2, 2.3, 2.8
    """
    n_days = len(df)

    if n_days < MIN_DAYS_FOR_TRAINING:
        logger.warning(
            "Skipping product '%s': only %d days of data available "
            "(minimum required: %d).",
            product_id,
            n_days,
            MIN_DAYS_FOR_TRAINING,
        )
        return

    logger.info("Training models for product '%s' (%d days).", product_id, n_days)

    # Sort chronologically and extract features / target
    df = df.sort_values("date").reset_index(drop=True)
    X = df[FEATURE_COLS].values
    y = df[TARGET_COL].values

    # --- Point forecast model ---
    point_model = xgb.XGBRegressor(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
    )
    point_model.fit(X, y)

    # --- Lower-bound quantile model (alpha=0.1) ---
    lower_model = xgb.XGBRegressor(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:quantileerror",
        quantile_alpha=0.1,
        random_state=42,
    )
    lower_model.fit(X, y)

    # --- Upper-bound quantile model (alpha=0.9) ---
    upper_model = xgb.XGBRegressor(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:quantileerror",
        quantile_alpha=0.9,
        random_state=42,
    )
    upper_model.fit(X, y)

    # --- Serialize models ---
    os.makedirs(_MODELS_DIR, exist_ok=True)
    joblib.dump(point_model, os.path.join(_MODELS_DIR, f"xgb_{product_id}.pkl"))
    joblib.dump(lower_model, os.path.join(_MODELS_DIR, f"xgb_lower_{product_id}.pkl"))
    joblib.dump(upper_model, os.path.join(_MODELS_DIR, f"xgb_upper_{product_id}.pkl"))

    logger.info("Models for product '%s' saved to models/.", product_id)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Load clean.json and train models for all products."""
    if not os.path.exists(_DATA_PATH):
        logger.error("ERROR: data/clean.json not found at %s", _DATA_PATH)
        sys.exit(1)

    logger.info("Loading preprocessed data from %s", _DATA_PATH)
    with open(_DATA_PATH, "r") as f:
        records = json.load(f)

    df_all = pd.DataFrame(records)
    df_all["date"] = pd.to_datetime(df_all["date"])

    product_ids = df_all["stock_code"].unique()
    logger.info("Found %d products to train.", len(product_ids))

    for pid in sorted(product_ids):
        product_df = df_all[df_all["stock_code"] == pid].copy()
        train_product(pid, product_df)

    logger.info("Training complete.")


if __name__ == "__main__":
    main()
