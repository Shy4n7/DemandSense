"""
api/forecast.py — Forecast Serverless Function for DemandSense

POST /api/forecast

Accepts a JSON body with product_id and horizon_days, generates a multi-step
demand forecast with confidence bounds, and returns forecast data alongside
holdout metrics (MAPE, RMSE).

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.8
"""

import os
import sys
import json
import logging

import pandas as pd
from flask import Flask, jsonify, request

# ---------------------------------------------------------------------------
# Path setup — add project root to sys.path so lib/ is importable
# ---------------------------------------------------------------------------

_API_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_API_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.predict_forecast import (
    generate_forecast,
    compute_metrics,
    ModelNotFoundError,
    ModelLoadError,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api.forecast")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_HORIZONS = {7, 14, 30}

# ---------------------------------------------------------------------------
# Module-level data cache
# ---------------------------------------------------------------------------

_DATA_PATH = os.path.join(_PROJECT_ROOT, "data", "clean.json")

_data_cache: list | None = None
_load_error: str | None = None


def _load_data() -> list:
    """Load and cache data/clean.json at module level."""
    global _data_cache, _load_error

    if _data_cache is not None:
        return _data_cache

    if _load_error is not None:
        raise RuntimeError(_load_error)

    try:
        with open(_DATA_PATH, "r") as f:
            _data_cache = json.load(f)
        logger.info("Loaded %d records from %s", len(_data_cache), _DATA_PATH)
        return _data_cache
    except Exception as exc:
        _load_error = f"Failed to load product data: {exc}"
        logger.error(_load_error)
        raise RuntimeError(_load_error)


# Attempt to load at import time (warm invocation caching)
try:
    _load_data()
except RuntimeError:
    pass

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)


@app.route("/api/forecast", methods=["POST"])
def post_forecast():
    """Generate a demand forecast for the requested product and horizon.

    Request Body (JSON):
        product_id (str): Non-empty StockCode string.
        horizon_days (int): One of 7, 14, or 30.

    Returns:
        200: {
            "product_id": str,
            "forecast": [{"date": str, "predicted": float, "lower": float, "upper": float}],
            "metrics": {"mape": float, "rmse": float}
        }
        400: {"error": "..."} if product_id is missing/empty or horizon_days is invalid
        404: {"error": "..."} if product not found in Model_Store
        500: {"error": "..."} if model cannot be loaded

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.8
    """
    body = request.get_json(silent=True) or {}

    # --- Validate product_id ---
    product_id = body.get("product_id", "")
    if not isinstance(product_id, str) or not product_id.strip():
        return jsonify({"error": "Missing or empty required field: product_id"}), 400
    product_id = product_id.strip()

    # --- Validate horizon_days ---
    horizon_days = body.get("horizon_days")
    if horizon_days is None:
        return jsonify({"error": "Missing required field: horizon_days"}), 400
    try:
        horizon_days = int(horizon_days)
    except (TypeError, ValueError):
        return jsonify(
            {"error": f"Invalid horizon_days: must be one of {sorted(VALID_HORIZONS)}"}
        ), 400
    if horizon_days not in VALID_HORIZONS:
        return jsonify(
            {"error": f"Invalid horizon_days '{horizon_days}': must be one of {sorted(VALID_HORIZONS)}"}
        ), 400

    # --- Load history for the product ---
    try:
        records = _load_data()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    product_records = [r for r in records if r.get("stock_code") == product_id]

    # --- Generate forecast and metrics ---
    try:
        history = pd.DataFrame(product_records)
        if not history.empty:
            history["date"] = pd.to_datetime(history["date"])
            history = history.sort_values("date").reset_index(drop=True)

        forecast = generate_forecast(product_id, horizon_days, history)
        metrics = compute_metrics(product_id, history)

    except ModelNotFoundError:
        # Requirement 4.4: product not found → 404
        return jsonify({"error": f"Product '{product_id}' not found"}), 404
    except ModelLoadError as exc:
        # Requirement 4.8: model load failure → 500
        logger.exception("Model load error for product '%s'", product_id)
        return jsonify({"error": f"Failed to load model for product '{product_id}': {exc.reason}"}), 500
    except Exception as exc:
        logger.exception("Unexpected error generating forecast for product '%s'", product_id)
        return jsonify({"error": f"Failed to generate forecast for product '{product_id}': {exc}"}), 500

    return jsonify({
        "product_id": product_id,
        "forecast": forecast,
        "metrics": metrics,
    }), 200
