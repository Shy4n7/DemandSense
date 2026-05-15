"""
api/importance.py — Feature Importance Serverless Function for DemandSense

GET /api/importance?product_id=<id>

Returns the ranked feature importances for a product's XGBoost point forecast
model.  Derives importances from the model's feature_importances_ attribute.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
"""

import os
import sys
import json
import logging

from flask import Flask, jsonify, request

# ---------------------------------------------------------------------------
# Path setup — add project root to sys.path so lib/ is importable
# ---------------------------------------------------------------------------

_API_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_API_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.predict_forecast import get_feature_importances, ModelNotFoundError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api.importance")

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


@app.route("/api/importance", methods=["GET"])
def get_importance():
    """Return feature importances for the requested product.

    Query Parameters:
        product_id (str): The StockCode of the product.

    Returns:
        200: {"product_id": str, "features": [{"name": str, "importance": float}]}
        400: {"error": "..."} if product_id is missing or empty
        404: {"error": "..."} if product not found in Model_Store

    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
    """
    product_id = request.args.get("product_id", "").strip()

    # Requirement 6.5: missing or empty product_id → 400
    if not product_id:
        return jsonify({"error": "Missing required query parameter: product_id"}), 400

    try:
        features = get_feature_importances(product_id)
    except ModelNotFoundError:
        # Requirement 6.4: product not found → 404
        return jsonify({"error": f"Product '{product_id}' not found"}), 404
    except Exception as exc:
        logger.exception("Unexpected error loading importance for product '%s'", product_id)
        return jsonify({"error": f"Failed to load model for product '{product_id}': {exc}"}), 500

    return jsonify({"product_id": product_id, "features": features}), 200
