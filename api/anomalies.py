"""
api/anomalies.py — Anomaly Detection Serverless Function for DemandSense

POST /api/anomalies

Accepts a JSON body with product_id, runs Isolation Forest + rule-based
anomaly detection on the product's full history, and returns all flagged
anomaly records with a total count.

Requirements: 5.1, 5.2, 5.3, 5.5
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

from lib.predict_anomaly import score_anomalies, ModelNotFoundError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api.anomalies")

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


@app.route("/api/anomalies", methods=["POST"])
def post_anomalies():
    """Return anomaly detection results for the requested product.

    Request Body (JSON):
        product_id (str): Non-empty StockCode string.

    Returns:
        200: {
            "product_id": str,
            "anomalies": [...],
            "total_anomalies": int
        }
        400: {"error": "..."} if product_id is missing or empty/whitespace
        404: {"error": "..."} if product not found in Model_Store
        500: {"error": "..."} on unexpected errors

    Requirements: 5.1, 5.2, 5.3, 5.5
    """
    body = request.get_json(silent=True) or {}

    # --- Validate product_id (Requirement 5.5) ---
    product_id = body.get("product_id", "")
    if not isinstance(product_id, str) or not product_id.strip():
        return jsonify({"error": "Missing or empty required field: product_id"}), 400
    product_id = product_id.strip()

    # --- Load history for the product ---
    try:
        records = _load_data()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    product_records = [r for r in records if r.get("stock_code") == product_id]

    # --- Score anomalies ---
    try:
        history = pd.DataFrame(product_records)
        if not history.empty:
            history["date"] = pd.to_datetime(history["date"])
            history = history.sort_values("date").reset_index(drop=True)

        anomaly_results = score_anomalies(product_id, history)

    except ModelNotFoundError:
        # Requirement 5.3: product not found → 404
        return jsonify({"error": f"Product '{product_id}' not found"}), 404
    except Exception as exc:
        logger.exception("Unexpected error scoring anomalies for product '%s'", product_id)
        return jsonify({"error": f"Failed to score anomalies for product '{product_id}': {exc}"}), 500

    # Requirement 5.1: total_anomalies equals length of anomalies array
    return jsonify({
        "product_id": product_id,
        "anomalies": anomaly_results,
        "total_anomalies": len(anomaly_results),
    }), 200
