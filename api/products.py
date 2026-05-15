"""
api/products.py — Product List Serverless Function for DemandSense

GET /api/products

Returns a JSON array of all products available in data/clean.json, sorted
descending by total sales volume (sum of quantity).  Each entry contains
product_id (StockCode string) and description (product name).

Requirements: 7.1, 7.2, 7.3, 7.4
"""

import os
import sys
import json
import logging

from flask import Flask, jsonify

# ---------------------------------------------------------------------------
# Path setup — add project root to sys.path so lib/ is importable
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
logger = logging.getLogger("api.products")

# ---------------------------------------------------------------------------
# Module-level data cache
# ---------------------------------------------------------------------------

_DATA_PATH = os.path.join(_PROJECT_ROOT, "data", "clean.json")

_data_cache: list | None = None
_load_error: str | None = None


def _load_data() -> list:
    """Load and cache data/clean.json at module level.

    Returns the cached list of records on subsequent calls.

    Raises:
        RuntimeError: If the file cannot be loaded.
    """
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
    pass  # Error will be surfaced per-request

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)


@app.route("/api/products", methods=["GET"])
def get_products():
    """Return all products sorted descending by total sales volume.

    Requirements: 7.1, 7.2, 7.3, 7.4
    """
    try:
        records = _load_data()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    # Compute total sales volume per product and collect description
    volume_map: dict[str, float] = {}
    description_map: dict[str, str] = {}

    for record in records:
        pid = record["stock_code"]
        qty = record.get("quantity", 0) or 0
        volume_map[pid] = volume_map.get(pid, 0.0) + float(qty)
        if pid not in description_map:
            description_map[pid] = record.get("description", "")

    # Sort descending by total sales volume (Requirement 7.3)
    sorted_products = sorted(
        volume_map.keys(),
        key=lambda pid: volume_map[pid],
        reverse=True,
    )

    result = [
        {
            "product_id": pid,
            "description": description_map.get(pid, ""),
        }
        for pid in sorted_products
    ]

    return jsonify(result), 200
