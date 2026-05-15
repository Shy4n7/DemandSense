"""
lib/inventory.py — Inventory Replenishment Calculations for DemandSense

Provides calculate_inventory() which uses the XGBoost demand forecast and
historical demand variability to compute safety stock, reorder point, and
suggested order quantity.

Formula:
    safety_stock    = Z × σ_demand × √lead_time
    reorder_point   = forecasted_demand_over_lead_time + safety_stock
    suggested_order = max(0, reorder_point - current_stock)

where:
    Z          = scipy.stats.norm.ppf(service_level)
    σ_demand   = std of daily quantity from clean.json for the product
    lead_time  = lead_time_days
"""

import os
import sys
import json
import math

import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# Path setup — ensure lib/ siblings are importable
# ---------------------------------------------------------------------------

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_LIB_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.predict_forecast import generate_forecast, ModelNotFoundError, ModelLoadError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DATA_PATH = os.path.join(_PROJECT_ROOT, "data", "clean.json")

# Module-level data cache (shared with api/ handlers)
_data_cache: list | None = None


def _load_data() -> list:
    """Load and cache data/clean.json at module level."""
    global _data_cache
    if _data_cache is not None:
        return _data_cache
    with open(_DATA_PATH, "r") as f:
        _data_cache = json.load(f)
    return _data_cache


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_inventory(
    product_id: str,
    current_stock: float,
    lead_time_days: int,
    service_level: float = 0.95,
) -> dict:
    """Calculate inventory replenishment metrics for a product.

    Loads the demand forecast for the given lead time horizon and computes
    safety stock, reorder point, and suggested order quantity using the
    standard safety stock formula.

    Args:
        product_id:     StockCode string identifying the product.
        current_stock:  Current on-hand inventory (units, ≥ 0).
        lead_time_days: Supplier lead time in days (1–90).
        service_level:  Desired service level as a probability (0 < sl < 1).
                        Defaults to 0.95 (95%).

    Returns:
        Dict with keys:
            product_id          (str)
            forecasted_demand   (float) — sum of predicted quantities over lead time
            safety_stock        (float) — Z × σ × √lead_time
            reorder_point       (float) — forecasted_demand + safety_stock
            current_stock       (float) — as supplied
            suggested_order     (float) — max(0, reorder_point - current_stock)
            status              (str)   — "CRITICAL" | "REORDER NOW" | "SUFFICIENT"
            reorder_alert       (bool)  — True when status != "SUFFICIENT"

    Raises:
        ModelNotFoundError: If the XGBoost model for product_id is missing.
        ModelLoadError:     If the model file cannot be loaded.
        ValueError:         If product_id has no history in clean.json.
    """
    # ------------------------------------------------------------------
    # 1. Load history for this product
    # ------------------------------------------------------------------
    records = _load_data()
    import pandas as pd
    all_df = pd.DataFrame(records)

    product_df = all_df[all_df["stock_code"] == product_id].copy() if "stock_code" in all_df.columns else pd.DataFrame()
    if product_df.empty:
        raise ValueError(f"No history found for product '{product_id}'")

    product_df["date"] = pd.to_datetime(product_df["date"])
    product_df = product_df.sort_values("date").reset_index(drop=True)

    # ------------------------------------------------------------------
    # 2. Generate forecast over the lead time horizon
    # ------------------------------------------------------------------
    forecast_entries = generate_forecast(product_id, lead_time_days, product_df)
    forecasted_demand = float(sum(e["predicted"] for e in forecast_entries))
    forecasted_demand = max(0.0, forecasted_demand)

    # ------------------------------------------------------------------
    # 3. Compute demand standard deviation from historical daily quantities
    # ------------------------------------------------------------------
    daily_quantities = product_df["quantity"].values.astype(float)
    if len(daily_quantities) >= 2:
        sigma_demand = float(np.std(daily_quantities, ddof=1))
    else:
        sigma_demand = 0.0

    # ------------------------------------------------------------------
    # 4. Safety stock: Z × σ × √lead_time
    # ------------------------------------------------------------------
    z_score = float(stats.norm.ppf(service_level))
    safety_stock = z_score * sigma_demand * math.sqrt(lead_time_days)
    safety_stock = max(0.0, safety_stock)

    # ------------------------------------------------------------------
    # 5. Reorder point and suggested order
    # ------------------------------------------------------------------
    reorder_point = forecasted_demand + safety_stock
    suggested_order = max(0.0, reorder_point - current_stock)

    # ------------------------------------------------------------------
    # 6. Status logic
    # ------------------------------------------------------------------
    if current_stock <= safety_stock:
        status = "CRITICAL"
    elif current_stock <= reorder_point:
        status = "REORDER NOW"
    else:
        status = "SUFFICIENT"

    reorder_alert = status != "SUFFICIENT"

    return {
        "product_id": product_id,
        "forecasted_demand": round(forecasted_demand, 2),
        "safety_stock": round(safety_stock, 2),
        "reorder_point": round(reorder_point, 2),
        "current_stock": float(current_stock),
        "suggested_order": round(suggested_order, 2),
        "status": status,
        "reorder_alert": reorder_alert,
    }
