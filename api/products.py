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

import pandas as pd
from lib.predict_anomaly import score_anomalies

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
_products_list_cache: list | None = None
_products_list_cache_source_id: int | None = None


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
    global _products_list_cache, _products_list_cache_source_id

    try:
        records = _load_data()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    if _products_list_cache is not None and _products_list_cache_source_id == id(records):
        return jsonify(_products_list_cache), 200

    # Compute total sales volume per product and collect description
    volume_map: dict[str, float] = {}
    description_map: dict[str, str] = {}
    price_map: dict[str, float] = {}

    for record in records:
        pid = record["stock_code"]
        qty = record.get("quantity", 0) or 0
        volume_map[pid] = volume_map.get(pid, 0.0) + float(qty)
        if pid not in description_map:
            description_map[pid] = record.get("description", "")
        price = record.get("unit_price")
        if price is not None:
            price_map[pid] = float(price)

    # Sort descending by total sales volume (Requirement 7.3)
    sorted_products = sorted(
        volume_map.keys(),
        key=lambda pid: volume_map[pid],
        reverse=True,
    )

    result = []
    for pid in sorted_products:
        product_records = [r for r in records if r.get("stock_code") == pid]
        
        # Calculate anomaly count and stockout warning (consecutive zeros in last 14 days)
        total_anoms = 0
        has_stockout_warning = False
        try:
            prod_df = pd.DataFrame(product_records)
            prod_df["date"] = pd.to_datetime(prod_df["date"])
            prod_df = prod_df.sort_values("date").reset_index(drop=True)
            
            anom_res = score_anomalies(pid, prod_df)
            cutoff = "2024-12-01"
            total_anoms = sum(1 for x in anom_res if x.get("is_anomaly") and x.get("date", "") >= cutoff)
            
            # Check last 14 days of history for stockout signals
            recent = anom_res[-14:] if len(anom_res) >= 14 else anom_res
            has_stockout_warning = any(x.get("reason") == "stockout_signal" for x in recent)
        except Exception as exc:
            logger.warning("Could not run full anomaly scoring for %s: %s", pid, exc)
            if len(product_records) >= 3:
                sorted_records = sorted(product_records, key=lambda x: x.get("date", ""))
                last_3 = sorted_records[-3:]
                has_stockout_warning = all(float(x.get("quantity", 0) or 0) == 0 for x in last_3)

        unit_price = price_map.get(pid, 0.0)
        vol = volume_map.get(pid, 0.0)
        
        result.append({
            "product_id": pid,
            "description": description_map.get(pid, ""),
            "unit_price": unit_price,
            "total_volume": vol,
            "total_revenue": vol * unit_price,
            "anomaly_count": total_anoms,
            "stockout_warning": has_stockout_warning,
        })

    _products_list_cache = result
    _products_list_cache_source_id = id(records)
    return jsonify(result), 200
