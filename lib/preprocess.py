"""
lib/preprocess.py — Feature Engineering Utilities for DemandSense

Shared utilities used by both training scripts and serverless functions.
"""

import numpy as np
import pandas as pd


def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Remove cancelled invoices, non-positive quantity, and non-positive unit price rows.

    Applies the following filters (Requirements 1.1, 1.2, 1.3):
    - Removes records where InvoiceNo begins with 'C' (cancelled invoices)
    - Removes records where Quantity is <= 0
    - Removes records where UnitPrice is <= 0

    Args:
        df: Raw transaction DataFrame with at least InvoiceNo, Quantity, UnitPrice columns.

    Returns:
        Filtered DataFrame with invalid records removed.
    """
    # Requirement 1.1: Remove cancelled invoices (InvoiceNo starts with 'C')
    mask_not_cancelled = ~df["InvoiceNo"].astype(str).str.startswith("C")

    # Requirement 1.2: Remove non-positive Quantity
    mask_positive_quantity = df["Quantity"] > 0

    # Requirement 1.3: Remove non-positive UnitPrice
    mask_positive_price = df["UnitPrice"] > 0

    return df[mask_not_cancelled & mask_positive_quantity & mask_positive_price].copy()


def aggregate_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate cleaned transactions to daily totals per StockCode.

    Applies the following transformations (Requirements 1.4):
    - Parses/normalizes InvoiceDate to a date (not datetime)
    - Groups by (StockCode, date), summing Quantity and computing mean UnitPrice
    - Preserves Description by taking the first value per group

    Args:
        df: Cleaned transaction DataFrame with at least InvoiceDate, StockCode,
            Quantity, UnitPrice, and Description columns.

    Returns:
        Aggregated DataFrame with columns: stock_code, date, quantity,
        unit_price, description.
    """
    df = df.copy()

    # Normalize InvoiceDate to a plain date (drop time component)
    df["date"] = pd.to_datetime(df["InvoiceDate"]).dt.date

    # Group by (StockCode, date) and aggregate
    grouped = (
        df.groupby(["StockCode", "date"], sort=True)
        .agg(
            quantity=("Quantity", "sum"),
            unit_price=("UnitPrice", "mean"),
            description=("Description", "first"),
        )
        .reset_index()
    )

    # Rename columns to snake_case output schema
    grouped = grouped.rename(columns={"StockCode": "stock_code"})

    return grouped[["stock_code", "date", "quantity", "unit_price", "description"]]


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add all 10 engineered feature columns to the aggregated daily DataFrame.

    Features added (Requirements 1.5):
    - day_of_week: 0=Monday … 6=Sunday
    - month: 1–12
    - is_weekend: 1 if day_of_week >= 5, else 0
    - is_month_end: 1 if date is the last day of the month, else 0
    - rolling_7d_mean: 7-day rolling mean of quantity per StockCode (min_periods=1)
    - rolling_30d_mean: 30-day rolling mean of quantity per StockCode (min_periods=1)
    - rolling_7d_std: 7-day rolling std of quantity per StockCode (min_periods=1)
    - lag_1: quantity shifted by 1 day per StockCode
    - lag_7: quantity shifted by 7 days per StockCode
    - lag_14: quantity shifted by 14 days per StockCode

    All NaN values (from insufficient history) are filled with 0.

    Args:
        df: Aggregated daily DataFrame with columns: stock_code, date, quantity,
            unit_price, description.

    Returns:
        DataFrame with all original columns plus the 10 engineered feature columns.
    """
    df = df.copy()

    # Ensure date is a proper datetime for calendar feature extraction
    df["date"] = pd.to_datetime(df["date"])

    # Calendar features (vectorised — no groupby needed)
    df["day_of_week"] = df["date"].dt.dayofweek          # 0=Monday … 6=Sunday
    df["month"] = df["date"].dt.month                     # 1–12
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_month_end"] = df["date"].dt.is_month_end.astype(int)

    # Sort by (stock_code, date) so rolling/lag operations are chronologically ordered
    df = df.sort_values(["stock_code", "date"]).reset_index(drop=True)

    # Rolling and lag features — computed per StockCode group
    def _add_rolling_lag(group: pd.DataFrame) -> pd.DataFrame:
        q = group["quantity"]
        group = group.copy()
        group["rolling_7d_mean"] = q.rolling(window=7, min_periods=1).mean()
        group["rolling_30d_mean"] = q.rolling(window=30, min_periods=1).mean()
        group["rolling_7d_std"] = q.rolling(window=7, min_periods=1).std()
        group["lag_1"] = q.shift(1)
        group["lag_7"] = q.shift(7)
        group["lag_14"] = q.shift(14)
        return group

    df = df.groupby("stock_code", group_keys=False).apply(_add_rolling_lag)

    # Fill all NaN values (from insufficient history) with 0
    feature_cols = [
        "rolling_7d_mean", "rolling_30d_mean", "rolling_7d_std",
        "lag_1", "lag_7", "lag_14",
    ]
    df[feature_cols] = df[feature_cols].fillna(0)

    return df


def select_top_products(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Subset the DataFrame to the top N StockCodes by total sales volume.

    Ranks products by the sum of quantity across all dates. Ties are broken
    by lexicographic ascending stock_code (lower code wins).

    Requirements: 1.6

    Args:
        df: Aggregated (and optionally feature-engineered) DataFrame with at
            least stock_code and quantity columns.
        n:  Maximum number of products to retain. Defaults to 20.

    Returns:
        DataFrame containing only rows whose stock_code is among the top N
        products by total sales volume.
    """
    # Compute total sales volume per product; sort descending by volume then
    # ascending by stock_code to break ties lexicographically.
    totals = (
        df.groupby("stock_code")["quantity"]
        .sum()
        .reset_index()
        .rename(columns={"quantity": "_total_volume"})
        .sort_values(["_total_volume", "stock_code"], ascending=[False, True])
    )

    top_codes = totals.head(n)["stock_code"].tolist()

    return df[df["stock_code"].isin(top_codes)].copy()


def exclude_short_history(df: pd.DataFrame, min_days: int = 30) -> pd.DataFrame:
    """Exclude any StockCode that has fewer than min_days days of history.

    A "day of history" is one distinct date entry for a given stock_code in
    the DataFrame. Products with fewer than min_days distinct dates are
    dropped entirely.

    Requirements: 1.8

    Args:
        df:        Aggregated daily DataFrame with at least stock_code and
                   date columns.
        min_days:  Minimum number of distinct calendar dates required to
                   retain a product. Defaults to 30.

    Returns:
        DataFrame with all rows for short-history products removed.
    """
    day_counts = df.groupby("stock_code")["date"].nunique()
    valid_codes = day_counts[day_counts >= min_days].index
    return df[df["stock_code"].isin(valid_codes)].copy()


def build_future_features(last_known: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Construct a feature matrix for the next ``horizon`` days.

    Uses the historical records in ``last_known`` (plus iteratively appended
    zero-quantity placeholders for future steps) to compute lag and rolling
    features for each future date.  Calendar features are derived from the
    target date.  The predicted quantity for all future steps is initialised
    to 0 — the caller (``generate_forecast``) is responsible for filling in
    real predictions iteratively.

    This function builds the FEATURE MATRIX only — it does NOT run any model.

    Feature columns produced (10 total):
        lag_1, lag_7, lag_14,
        rolling_7d_mean, rolling_30d_mean, rolling_7d_std,
        day_of_week, month, is_weekend, is_month_end

    Plus a ``date`` column (datetime) for each future step.

    Requirements: 4.1, 4.2

    Args:
        last_known: DataFrame of historical records for ONE product, sorted
            chronologically.  Must contain at least the columns ``date`` and
            ``quantity``.  All 10 feature columns should be present (they are
            used only as structural reference; the future rows are computed
            fresh).
        horizon: Number of future days to generate features for.  Typically
            7, 14, or 30.

    Returns:
        DataFrame with ``horizon`` rows, one per future date, containing the
        ``date`` column and all 10 feature columns.  Rows are ordered
        chronologically (earliest future date first).
    """
    # Work with a copy; ensure date is datetime and data is sorted
    history = last_known.copy()
    history["date"] = pd.to_datetime(history["date"])
    history = history.sort_values("date").reset_index(drop=True)

    # We only need the quantity series for lag/rolling computations.
    # Build a mutable list of quantities that grows as we add future steps.
    qty_history: list = history["quantity"].tolist()

    # Determine the last date in the known history
    last_date = history["date"].iloc[-1]

    future_rows = []

    for step in range(1, horizon + 1):
        target_date = last_date + pd.Timedelta(days=step)

        # --- Calendar features ---
        day_of_week = target_date.dayofweek          # 0=Monday … 6=Sunday
        month = target_date.month                     # 1–12
        is_weekend = int(day_of_week >= 5)
        is_month_end = int(target_date.is_month_end)

        # --- Lag features ---
        # qty_history currently has (len(history) + step - 1) entries because
        # we append the placeholder 0 at the end of each iteration.
        n = len(qty_history)

        lag_1 = qty_history[n - 1] if n >= 1 else 0
        lag_7 = qty_history[n - 7] if n >= 7 else 0
        lag_14 = qty_history[n - 14] if n >= 14 else 0

        # --- Rolling features ---
        # rolling_7d_mean / rolling_7d_std: last 7 values
        window_7 = qty_history[max(0, n - 7): n]
        rolling_7d_mean = float(np.mean(window_7)) if window_7 else 0.0
        rolling_7d_std_val = float(np.std(window_7, ddof=1)) if len(window_7) >= 2 else 0.0

        # rolling_30d_mean: last 30 values
        window_30 = qty_history[max(0, n - 30): n]
        rolling_30d_mean = float(np.mean(window_30)) if window_30 else 0.0

        future_rows.append({
            "date": target_date,
            "lag_1": lag_1,
            "lag_7": lag_7,
            "lag_14": lag_14,
            "rolling_7d_mean": rolling_7d_mean,
            "rolling_30d_mean": rolling_30d_mean,
            "rolling_7d_std": rolling_7d_std_val,
            "day_of_week": day_of_week,
            "month": month,
            "is_weekend": is_weekend,
            "is_month_end": is_month_end,
        })

        # Append placeholder quantity (0) so the next step can use it as a lag
        qty_history.append(0)

    return pd.DataFrame(future_rows)
