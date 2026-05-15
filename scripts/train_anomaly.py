"""
scripts/train_anomaly.py — Anomaly Detection Model Training Script for DemandSense

Trains one Isolation Forest model per product on the multivariate feature
space of [quantity, unit_price].  Products with fewer than 30 days of
historical data are skipped with a logged warning.

Serializes each model to:
  models/iso_{product_id}.pkl

Requirements: 3.1, 3.5, 3.6
"""

import os
import sys
import json
import logging

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scripts.train_anomaly")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_PATH = os.path.join(_PROJECT_ROOT, "data", "clean.json")
_MODELS_DIR = os.path.join(_PROJECT_ROOT, "models")

MIN_DAYS_FOR_TRAINING = 30

# ---------------------------------------------------------------------------
# Core training function
# ---------------------------------------------------------------------------


def train_product(product_id: str, df: pd.DataFrame) -> None:
    """Train an Isolation Forest model for a single product.

    If the product has fewer than MIN_DAYS_FOR_TRAINING (30) days of data,
    logs a WARNING and returns without training.

    The model is trained on the 2-column feature matrix [quantity, unit_price].
    Uses IsolationForest(contamination=0.05, random_state=42).

    Args:
        product_id: The StockCode string identifying the product.
        df: Preprocessed DataFrame for this product with at least the columns
            'quantity' and 'unit_price'.  Must be sorted chronologically.

    Requirements: 3.1, 3.6
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

    logger.info("Training Isolation Forest for product '%s' (%d days).", product_id, n_days)

    # Sort chronologically and extract features
    df = df.sort_values("date").reset_index(drop=True)
    X = df[["quantity", "unit_price"]].values

    # Train Isolation Forest (Requirement 3.1)
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(X)

    # Serialize model (Requirement 3.6)
    os.makedirs(_MODELS_DIR, exist_ok=True)
    model_path = os.path.join(_MODELS_DIR, f"iso_{product_id}.pkl")
    joblib.dump(model, model_path)

    logger.info("Isolation Forest for product '%s' saved to %s.", product_id, model_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Load clean.json and train Isolation Forest models for all products."""
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

    logger.info("Anomaly model training complete.")


if __name__ == "__main__":
    main()
