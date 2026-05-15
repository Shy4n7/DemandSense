"""
scripts/preprocess.py — Main preprocessing script for DemandSense.

Reads the UCI Online Retail Dataset, runs the full preprocessing pipeline,
and serializes the result to data/clean.json.

Pipeline order (Requirements 1.7, 1.9):
    1. clean_transactions
    2. aggregate_daily
    3. engineer_features
    4. exclude_short_history  (removes products with < 30 days of history)
    5. select_top_products    (keeps top 20 by total sales volume)
    6. Serialize to data/clean.json as a flat JSON array (orient='records')

Usage:
    python scripts/preprocess.py

Exit codes:
    0 — success
    1 — input file missing or unreadable
"""

import sys
import os
import pandas as pd

# Ensure the project root is on the path so lib/ is importable regardless of
# the working directory from which this script is invoked.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.preprocess import (
    clean_transactions,
    aggregate_daily,
    engineer_features,
    exclude_short_history,
    select_top_products,
)

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
_XLSX_PATH = os.path.join(_PROJECT_ROOT, "data", "online_retail.xlsx")
_XLSX_PATH_ALT = os.path.join(_PROJECT_ROOT, "data", "Online Retail.xlsx")
_CSV_PATH = os.path.join(_PROJECT_ROOT, "data", "online_retail.csv")
_OUTPUT_PATH = os.path.join(_PROJECT_ROOT, "data", "clean.json")


def _load_input() -> pd.DataFrame:
    """Load the UCI dataset from xlsx (preferred) or csv fallback.

    Returns the raw DataFrame on success.
    Prints an error and calls sys.exit(1) if neither file is found or readable.
    """
    # Try xlsx first (both naming conventions), then csv
    for path in (_XLSX_PATH, _XLSX_PATH_ALT, _CSV_PATH):
        if os.path.exists(path):
            try:
                if path.endswith(".xlsx"):
                    df = pd.read_excel(path, dtype={"StockCode": str, "InvoiceNo": str})
                else:
                    df = pd.read_csv(path, dtype={"StockCode": str, "InvoiceNo": str})
                return df
            except Exception as exc:
                print(
                    f"ERROR: Could not read input file '{path}': {exc}",
                    file=sys.stderr,
                )
                sys.exit(1)

    # Neither file exists
    print(
        f"ERROR: Input file not found. Looked for:\n"
        f"  {_XLSX_PATH}\n"
        f"  {_XLSX_PATH_ALT}\n"
        f"  {_CSV_PATH}\n"
        "Please place the UCI Online Retail Dataset in the data/ directory.",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    """Run the full preprocessing pipeline and write data/clean.json."""
    # 1. Load raw data
    raw_df = _load_input()

    # 2. Clean transactions (remove cancellations, non-positive qty/price)
    df = clean_transactions(raw_df)

    # 3. Aggregate to daily totals per StockCode
    df = aggregate_daily(df)

    # 4. Engineer all 10 model features
    df = engineer_features(df)

    # 5. Exclude products with fewer than 30 days of history
    df = exclude_short_history(df, min_days=30)

    # 6. Subset to top 20 products by total sales volume
    df = select_top_products(df, n=20)

    # 7. Serialize to data/clean.json as a flat JSON array
    os.makedirs(os.path.dirname(_OUTPUT_PATH), exist_ok=True)
    df.to_json(_OUTPUT_PATH, orient="records", date_format="iso", indent=2)

    print(f"Preprocessing complete. {len(df)} records written to {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
