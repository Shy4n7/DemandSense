"""
api/inventory.py — Inventory Replenishment Serverless Function for DemandSense

GET /api/inventory?product_id=X&current_stock=Y&lead_time=Z&service_level=0.95

Validates all query parameters, calls lib/inventory.py calculate_inventory(),
and returns the replenishment metrics as JSON.

Follows the same pattern as the other api/ handlers (Flask, module-level
data cache, consistent error responses).
"""

import os
import sys
import logging

from flask import Flask, jsonify, request

# ---------------------------------------------------------------------------
# Path setup — add project root to sys.path so lib/ is importable
# ---------------------------------------------------------------------------

_API_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_API_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.inventory import calculate_inventory
from lib.predict_forecast import ModelNotFoundError, ModelLoadError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api.inventory")

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_VALID_SERVICE_LEVELS = {0.90, 0.95, 0.99}


def _parse_float(value: str, name: str, min_val: float = None, max_val: float = None):
    """Parse a string to float with optional range validation.

    Returns (float_value, error_string_or_None).
    """
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None, f"'{name}' must be a number, got: {value!r}"
    if min_val is not None and f < min_val:
        return None, f"'{name}' must be ≥ {min_val}, got: {f}"
    if max_val is not None and f > max_val:
        return None, f"'{name}' must be ≤ {max_val}, got: {f}"
    return f, None


def _parse_int(value: str, name: str, min_val: int = None, max_val: int = None):
    """Parse a string to int with optional range validation.

    Returns (int_value, error_string_or_None).
    """
    try:
        # Accept floats like "7.0" but reject "7.5"
        f = float(value)
        if f != int(f):
            raise ValueError("not an integer")
        i = int(f)
    except (TypeError, ValueError):
        return None, f"'{name}' must be an integer, got: {value!r}"
    if min_val is not None and i < min_val:
        return None, f"'{name}' must be ≥ {min_val}, got: {i}"
    if max_val is not None and i > max_val:
        return None, f"'{name}' must be ≤ {max_val}, got: {i}"
    return i, None


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@app.route("/api/inventory", methods=["GET"])
def get_inventory():
    """Return inventory replenishment metrics for a product.

    Query Parameters:
        product_id    (str, required)   — StockCode of the product
        current_stock (float, required) — Current on-hand inventory (≥ 0)
        lead_time     (int, required)   — Supplier lead time in days (1–90)
        service_level (float, optional) — Service level probability (default 0.95)
                                          Must be one of: 0.90, 0.95, 0.99

    Returns:
        200: {
            "product_id": str,
            "forecasted_demand": float,
            "safety_stock": float,
            "reorder_point": float,
            "current_stock": float,
            "suggested_order": float,
            "status": "SUFFICIENT" | "REORDER NOW" | "CRITICAL",
            "reorder_alert": bool
        }
        400: {"error": "..."} — missing or invalid parameters
        404: {"error": "..."} — product not found
        500: {"error": "..."} — model load failure or unexpected error
    """
    # --- product_id ---
    product_id = request.args.get("product_id", "").strip()
    if not product_id:
        return jsonify({"error": "Missing required query parameter: product_id"}), 400

    # --- current_stock ---
    raw_stock = request.args.get("current_stock")
    if raw_stock is None:
        return jsonify({"error": "Missing required query parameter: current_stock"}), 400
    current_stock, err = _parse_float(raw_stock, "current_stock", min_val=0.0)
    if err:
        return jsonify({"error": err}), 400

    # --- lead_time ---
    raw_lead = request.args.get("lead_time")
    if raw_lead is None:
        return jsonify({"error": "Missing required query parameter: lead_time"}), 400
    lead_time, err = _parse_int(raw_lead, "lead_time", min_val=1, max_val=90)
    if err:
        return jsonify({"error": err}), 400

    # --- service_level (optional, default 0.95) ---
    raw_sl = request.args.get("service_level", "0.95")
    service_level, err = _parse_float(raw_sl, "service_level", min_val=0.0, max_val=1.0)
    if err:
        return jsonify({"error": err}), 400
    # Round to 2 decimal places to handle floating-point representation (e.g. 0.9000000001)
    service_level = round(service_level, 10)
    if round(service_level, 2) not in _VALID_SERVICE_LEVELS:
        return jsonify({
            "error": (
                f"'service_level' must be one of {sorted(_VALID_SERVICE_LEVELS)}, "
                f"got: {service_level}"
            )
        }), 400

    # --- Call inventory calculation ---
    try:
        result = calculate_inventory(
            product_id=product_id,
            current_stock=current_stock,
            lead_time_days=lead_time,
            service_level=service_level,
        )
    except ModelNotFoundError:
        return jsonify({"error": f"Product '{product_id}' not found"}), 404
    except ModelLoadError as exc:
        logger.exception("Model load error for product '%s'", product_id)
        return jsonify({
            "error": f"Failed to load model for product '{product_id}': {exc.reason}"
        }), 500
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        logger.exception("Unexpected error calculating inventory for product '%s'", product_id)
        return jsonify({
            "error": f"Failed to calculate inventory for product '{product_id}': {exc}"
        }), 500

    return jsonify(result), 200
