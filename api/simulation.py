"""
api/simulation.py — Simulation Data Serverless Function for DemandSense

GET /api/simulation?product_id=X

Returns all historical daily records for a product sorted ascending by date,
for use by the frontend inventory simulation playback.

Response:
    {
        "product_id": "X",
        "data": [{ "date": "2023-01-01", "actual_quantity": 87 }, ...],
        "total_days": 365
    }

Follows the same pattern as existing api/ handlers.
"""

import os
import sys
import json
import logging

from flask import Flask, jsonify, request

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_API_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_API_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api.simulation")

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


@app.route("/api/simulation", methods=["GET"])
def get_simulation_data():
    """Return historical daily quantities for a product, sorted ascending by date.

    Query Parameters:
        product_id (str, required) — StockCode of the product

    Returns:
        200: {
            "product_id": str,
            "data": [{"date": str, "actual_quantity": float}, ...],
            "total_days": int
        }
        400: {"error": "..."} — missing product_id
        404: {"error": "..."} — product not found in dataset
        500: {"error": "..."} — data load failure
    """
    product_id = request.args.get("product_id", "").strip()
    if not product_id:
        return jsonify({"error": "Missing required query parameter: product_id"}), 400

    try:
        records = _load_data()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    # Filter to the requested product
    product_records = [r for r in records if r.get("stock_code") == product_id]

    if not product_records:
        return jsonify({"error": f"Product '{product_id}' not found"}), 404

    # Sort ascending by date and project to the required shape
    product_records.sort(key=lambda r: r["date"])

    data = [
        {
            "date": r["date"],
            "actual_quantity": float(r.get("quantity", 0) or 0),
        }
        for r in product_records
    ]

    return jsonify({
        "product_id": product_id,
        "data": data,
        "total_days": len(data),
    }), 200
