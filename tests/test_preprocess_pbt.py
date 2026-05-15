"""
tests/test_preprocess_pbt.py — Property-based tests for lib/preprocess.py

Uses Hypothesis to verify universal correctness properties across the
preprocessing pipeline.  All PBT tests run a minimum of 100 examples.

Tasks covered:
  2.2  — Property 1: Data cleaning removes invalid records
  2.4  — Property 2: Daily aggregation preserves quantity sum
  2.6  — Property 3: Feature engineering completeness
  2.8  — Property 4: Top-20 selection invariant
  2.10 — Property 6: Short-history exclusion
  2.12 — Property 5: Serialization round-trip
  2.13 — Unit test: missing input file exit behavior
"""

import sys
import os
import json
import math
import datetime
import subprocess

import pandas as pd
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Project root on path
# ---------------------------------------------------------------------------
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
# Shared strategies
# ---------------------------------------------------------------------------

# Stock codes: short alphanumeric strings, no leading 'C' (reserved for
# cancellations in InvoiceNo, not StockCode — but we keep them distinct anyway)
_stock_code_st = st.text(
    alphabet="ABDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    min_size=1,
    max_size=6,
)

# Positive floats suitable for prices / quantities (no NaN, no inf)
_pos_float_st = st.floats(min_value=0.01, max_value=10_000.0, allow_nan=False, allow_infinity=False)

# Positive integers for quantities
_pos_int_st = st.integers(min_value=1, max_value=10_000)

# ---------------------------------------------------------------------------
# Task 2.2 — Property 1: Data Cleaning Removes All Invalid Records
# Feature: demand-sense, Property 1: Data cleaning removes invalid records
# ---------------------------------------------------------------------------

def _invoice_no_st(cancelled: bool):
    """Generate an InvoiceNo that is or is not a cancellation."""
    if cancelled:
        # Must start with 'C'
        return st.text(
            alphabet="0123456789",
            min_size=1,
            max_size=6,
        ).map(lambda s: "C" + s)
    else:
        # Must NOT start with 'C'
        return st.text(
            alphabet="0123456789",
            min_size=1,
            max_size=6,
        ).map(lambda s: "N" + s)


@st.composite
def _raw_transaction_row_st(draw, force_invalid=None):
    """
    Draw a single raw transaction row dict.

    force_invalid: None (random), 'cancelled', 'qty', 'price'
    """
    if force_invalid == "cancelled":
        cancelled = True
        qty = draw(_pos_int_st)
        price = draw(_pos_float_st)
    elif force_invalid == "qty":
        cancelled = False
        qty = draw(st.integers(min_value=-1000, max_value=0))
        price = draw(_pos_float_st)
    elif force_invalid == "price":
        cancelled = False
        qty = draw(_pos_int_st)
        price = draw(st.floats(min_value=-100.0, max_value=0.0, allow_nan=False, allow_infinity=False))
    else:
        # Random: may be valid or invalid
        cancelled = draw(st.booleans())
        qty = draw(st.integers(min_value=-100, max_value=1000))
        price = draw(st.floats(min_value=-10.0, max_value=100.0, allow_nan=False, allow_infinity=False))

    invoice_no = draw(_invoice_no_st(cancelled))
    stock_code = draw(_stock_code_st)
    return {
        "InvoiceNo": invoice_no,
        "StockCode": stock_code,
        "Description": "Test Product",
        "Quantity": qty,
        "InvoiceDate": "2020-01-01 08:00:00",
        "UnitPrice": price,
        "CustomerID": 12345,
        "Country": "United Kingdom",
    }


@st.composite
def _mixed_raw_df_st(draw):
    """
    Draw a DataFrame with a mix of valid and invalid rows.
    Guarantees at least one invalid row of each type.
    """
    # At least one of each invalid type
    cancelled_row = draw(_raw_transaction_row_st(force_invalid="cancelled"))
    bad_qty_row = draw(_raw_transaction_row_st(force_invalid="qty"))
    bad_price_row = draw(_raw_transaction_row_st(force_invalid="price"))

    # Some random rows (may be valid or invalid)
    random_rows = draw(st.lists(_raw_transaction_row_st(), min_size=0, max_size=20))

    all_rows = [cancelled_row, bad_qty_row, bad_price_row] + random_rows
    return pd.DataFrame(all_rows)


@given(df=_mixed_raw_df_st())
@settings(max_examples=100)
def test_property1_clean_transactions_removes_invalid_records(df):
    # Feature: demand-sense, Property 1: Data cleaning removes invalid records
    result = clean_transactions(df)

    if result.empty:
        return  # Nothing to check

    # No cancelled invoices
    assert not result["InvoiceNo"].astype(str).str.startswith("C").any(), \
        "clean_transactions must remove all cancelled invoices (InvoiceNo starts with 'C')"

    # No non-positive Quantity
    assert (result["Quantity"] > 0).all(), \
        "clean_transactions must remove all rows with Quantity <= 0"

    # No non-positive UnitPrice
    assert (result["UnitPrice"] > 0).all(), \
        "clean_transactions must remove all rows with UnitPrice <= 0"


# ---------------------------------------------------------------------------
# Task 2.4 — Property 2: Daily Aggregation Preserves Quantity Sum
# Feature: demand-sense, Property 2: Aggregation preserves quantity sum
# ---------------------------------------------------------------------------

@st.composite
def _clean_transactions_df_st(draw):
    """
    Draw a cleaned transaction DataFrame (all rows valid).
    Groups share (StockCode, date) so we can verify quantity sums.
    """
    # Pick 1–5 distinct stock codes
    n_codes = draw(st.integers(min_value=1, max_value=5))
    codes = [f"SC{i:02d}" for i in range(n_codes)]

    # Pick 1–5 distinct dates
    n_dates = draw(st.integers(min_value=1, max_value=5))
    base = datetime.date(2020, 1, 1)
    dates = [str(base + datetime.timedelta(days=i)) + " 08:00:00" for i in range(n_dates)]

    rows = []
    for code in codes:
        for date_str in dates:
            # 1–4 transactions per (code, date)
            n_txns = draw(st.integers(min_value=1, max_value=4))
            for _ in range(n_txns):
                rows.append({
                    "InvoiceNo": draw(st.integers(min_value=100000, max_value=999999)).to_bytes(4, "big").hex(),
                    "StockCode": code,
                    "Description": f"Product {code}",
                    "Quantity": draw(_pos_int_st),
                    "InvoiceDate": date_str,
                    "UnitPrice": draw(_pos_float_st),
                    "CustomerID": 12345,
                    "Country": "United Kingdom",
                })

    return pd.DataFrame(rows)


@st.composite
def _clean_transactions_df_simple_st(draw):
    """Simpler strategy: list of row dicts with controlled (StockCode, date) groups."""
    n_codes = draw(st.integers(min_value=1, max_value=4))
    n_dates = draw(st.integers(min_value=1, max_value=4))

    codes = [f"P{i}" for i in range(n_codes)]
    base = datetime.date(2020, 6, 1)
    date_strs = [(base + datetime.timedelta(days=d)).strftime("%Y-%m-%d %H:%M:%S")
                 for d in range(n_dates)]

    rows = []
    for code in codes:
        for date_str in date_strs:
            n_txns = draw(st.integers(min_value=1, max_value=5))
            for _ in range(n_txns):
                rows.append({
                    "InvoiceNo": f"INV{len(rows):06d}",
                    "StockCode": code,
                    "Description": f"Desc {code}",
                    "Quantity": draw(_pos_int_st),
                    "InvoiceDate": date_str,
                    "UnitPrice": draw(_pos_float_st),
                    "CustomerID": 99999,
                    "Country": "UK",
                })

    return pd.DataFrame(rows)


@given(df=_clean_transactions_df_simple_st())
@settings(max_examples=100)
def test_property2_aggregate_daily_preserves_quantity_sum(df):
    # Feature: demand-sense, Property 2: Aggregation preserves quantity sum
    result = aggregate_daily(df)

    # For every (stock_code, date) group in the output, verify the quantity
    # equals the sum of all input Quantity values for that group.
    df["_date"] = pd.to_datetime(df["InvoiceDate"]).dt.date

    for _, row in result.iterrows():
        sc = row["stock_code"]
        d = row["date"]
        expected_qty = df[(df["StockCode"] == sc) & (df["_date"] == d)]["Quantity"].sum()
        assert row["quantity"] == expected_qty, (
            f"aggregate_daily quantity mismatch for ({sc}, {d}): "
            f"got {row['quantity']}, expected {expected_qty}"
        )


# ---------------------------------------------------------------------------
# Task 2.6 — Property 3: Feature Engineering Produces a Complete, Non-Null Feature Set
# Feature: demand-sense, Property 3: Feature engineering completeness
# ---------------------------------------------------------------------------

FEATURE_COLS = [
    "day_of_week", "month", "is_weekend", "is_month_end",
    "rolling_7d_mean", "rolling_30d_mean", "rolling_7d_std",
    "lag_1", "lag_7", "lag_14",
]


@st.composite
def _aggregated_daily_df_st(draw):
    """
    Draw an aggregated daily DataFrame suitable for engineer_features().
    Columns: stock_code, date, quantity, unit_price, description.
    History length per product: 1–50 rows.
    """
    n_products = draw(st.integers(min_value=1, max_value=5))
    codes = [f"PROD{i:02d}" for i in range(n_products)]

    rows = []
    base = datetime.date(2020, 1, 1)
    for code in codes:
        n_days = draw(st.integers(min_value=1, max_value=50))
        for i in range(n_days):
            rows.append({
                "stock_code": code,
                "date": (base + datetime.timedelta(days=i)).strftime("%Y-%m-%d"),
                "quantity": draw(_pos_int_st),
                "unit_price": draw(_pos_float_st),
                "description": f"Product {code}",
            })

    df = pd.DataFrame(rows)
    # date column as date objects (matching aggregate_daily output)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


@given(df=_aggregated_daily_df_st())
@settings(max_examples=100)
def test_property3_engineer_features_completeness(df):
    # Feature: demand-sense, Property 3: Feature engineering completeness
    result = engineer_features(df)

    # All 10 feature columns must be present
    for col in FEATURE_COLS:
        assert col in result.columns, f"engineer_features missing column: {col}"

    # No NaN values in any feature column
    nan_counts = result[FEATURE_COLS].isnull().sum()
    assert nan_counts.sum() == 0, (
        f"engineer_features left NaN values in feature columns:\n{nan_counts[nan_counts > 0]}"
    )


# ---------------------------------------------------------------------------
# Task 2.8 — Property 4: Top-20 Selection Invariant
# Feature: demand-sense, Property 4: Top-20 selection invariant
# ---------------------------------------------------------------------------

@st.composite
def _volume_df_st(draw):
    """
    Draw a DataFrame with > 20 distinct stock codes and associated volumes.
    Each row is one (stock_code, quantity) entry (already aggregated).
    """
    # More than 20 distinct codes
    n_codes = draw(st.integers(min_value=21, max_value=50))
    codes = [f"CODE{i:03d}" for i in range(n_codes)]

    rows = []
    for code in codes:
        # Each code gets 1–5 rows with positive quantities
        n_rows = draw(st.integers(min_value=1, max_value=5))
        for _ in range(n_rows):
            rows.append({
                "stock_code": code,
                "quantity": draw(_pos_int_st),
            })

    return pd.DataFrame(rows)


@given(df=_volume_df_st())
@settings(max_examples=100)
def test_property4_top20_selection_invariant(df):
    # Feature: demand-sense, Property 4: Top-20 selection invariant
    result = select_top_products(df, n=20)

    included_codes = set(result["stock_code"].unique())
    all_codes = set(df["stock_code"].unique())
    excluded_codes = all_codes - included_codes

    # Output must contain at most 20 distinct codes
    assert len(included_codes) <= 20, (
        f"select_top_products returned {len(included_codes)} codes, expected <= 20"
    )

    # Compute total volume per code
    totals = df.groupby("stock_code")["quantity"].sum()

    # No excluded code should have a higher volume than any included code
    if excluded_codes and included_codes:
        min_included_vol = min(totals[c] for c in included_codes)
        for exc_code in excluded_codes:
            exc_vol = totals[exc_code]
            assert exc_vol <= min_included_vol, (
                f"Excluded code '{exc_code}' has volume {exc_vol} > "
                f"min included volume {min_included_vol}"
            )


# ---------------------------------------------------------------------------
# Task 2.10 — Property 6: Short-History Products Are Excluded
# Feature: demand-sense, Property 6: Short-history exclusion
# ---------------------------------------------------------------------------

@st.composite
def _mixed_history_df_st(draw):
    """
    Draw a DataFrame where some products have < 30 days and some have >= 30 days.
    Guarantees at least one product of each kind.
    """
    base = datetime.date(2020, 1, 1)

    # At least one short-history product (< 30 days)
    n_short = draw(st.integers(min_value=1, max_value=5))
    # At least one long-history product (>= 30 days)
    n_long = draw(st.integers(min_value=1, max_value=5))

    rows = []

    for i in range(n_short):
        code = f"SHORT{i:02d}"
        n_days = draw(st.integers(min_value=1, max_value=29))
        for d in range(n_days):
            rows.append({
                "stock_code": code,
                "date": base + datetime.timedelta(days=d),
                "quantity": draw(_pos_int_st),
                "unit_price": draw(_pos_float_st),
                "description": f"Short product {i}",
            })

    for i in range(n_long):
        code = f"LONG{i:02d}"
        n_days = draw(st.integers(min_value=30, max_value=60))
        for d in range(n_days):
            rows.append({
                "stock_code": code,
                "date": base + datetime.timedelta(days=d),
                "quantity": draw(_pos_int_st),
                "unit_price": draw(_pos_float_st),
                "description": f"Long product {i}",
            })

    return pd.DataFrame(rows)


@given(df=_mixed_history_df_st())
@settings(max_examples=100)
def test_property6_short_history_exclusion(df):
    # Feature: demand-sense, Property 6: Short-history exclusion
    result = exclude_short_history(df, min_days=30)

    if result.empty:
        return  # All products were short — valid outcome

    # Every remaining stock_code must have >= 30 distinct dates
    day_counts = result.groupby("stock_code")["date"].nunique()
    violations = day_counts[day_counts < 30]
    assert violations.empty, (
        f"exclude_short_history left products with < 30 days:\n{violations}"
    )


# ---------------------------------------------------------------------------
# Task 2.12 — Property 5: Preprocessed Data Serialization Round-Trip
# Feature: demand-sense, Property 5: Serialization round-trip
# ---------------------------------------------------------------------------

@st.composite
def _preprocessed_df_st(draw):
    """
    Draw a DataFrame that resembles the output of the full preprocessing
    pipeline (i.e., what gets written to data/clean.json).

    Columns match the CleanRecord schema from the design doc.
    """
    n_rows = draw(st.integers(min_value=1, max_value=30))
    base = datetime.date(2020, 1, 1)

    rows = []
    for i in range(n_rows):
        date = base + datetime.timedelta(days=i)
        dow = date.weekday()
        rows.append({
            "stock_code": draw(st.sampled_from(["85123A", "71053", "84406B"])),
            "description": draw(st.sampled_from(["Widget A", "Widget B", "Widget C"])),
            "date": date.isoformat(),
            "quantity": draw(_pos_int_st),
            "unit_price": draw(_pos_float_st),
            "day_of_week": dow,
            "month": date.month,
            "is_weekend": int(dow >= 5),
            "is_month_end": int(
                (date + datetime.timedelta(days=1)).month != date.month
            ),
            "rolling_7d_mean": draw(st.floats(min_value=0.0, max_value=10_000.0,
                                               allow_nan=False, allow_infinity=False)),
            "rolling_30d_mean": draw(st.floats(min_value=0.0, max_value=10_000.0,
                                                allow_nan=False, allow_infinity=False)),
            "rolling_7d_std": draw(st.floats(min_value=0.0, max_value=5_000.0,
                                              allow_nan=False, allow_infinity=False)),
            "lag_1": draw(st.floats(min_value=0.0, max_value=10_000.0,
                                     allow_nan=False, allow_infinity=False)),
            "lag_7": draw(st.floats(min_value=0.0, max_value=10_000.0,
                                     allow_nan=False, allow_infinity=False)),
            "lag_14": draw(st.floats(min_value=0.0, max_value=10_000.0,
                                      allow_nan=False, allow_infinity=False)),
        })

    return pd.DataFrame(rows)


@given(df=_preprocessed_df_st())
@settings(max_examples=100)
def test_property5_serialization_round_trip(df):
    # Feature: demand-sense, Property 5: Serialization round-trip
    # Serialize to JSON string (same method used by scripts/preprocess.py)
    json_str = df.to_json(orient="records", date_format="iso")

    # Deserialize back
    records = json.loads(json_str)
    df2 = pd.DataFrame(records)

    assert len(df2) == len(df), "Round-trip changed the number of records"

    numeric_cols = [
        "quantity", "unit_price", "day_of_week", "month",
        "is_weekend", "is_month_end",
        "rolling_7d_mean", "rolling_30d_mean", "rolling_7d_std",
        "lag_1", "lag_7", "lag_14",
    ]
    string_cols = ["stock_code", "description", "date"]

    for col in string_cols:
        if col in df.columns and col in df2.columns:
            for orig, restored in zip(df[col].tolist(), df2[col].tolist()):
                assert str(orig) == str(restored), (
                    f"String column '{col}' mismatch: {orig!r} != {restored!r}"
                )

    for col in numeric_cols:
        if col in df.columns and col in df2.columns:
            for orig, restored in zip(df[col].tolist(), df2[col].tolist()):
                orig_f = float(orig)
                rest_f = float(restored)
                assert math.isclose(orig_f, rest_f, rel_tol=1e-9, abs_tol=1e-9), (
                    f"Numeric column '{col}' mismatch after round-trip: "
                    f"{orig_f} != {rest_f}"
                )


# ---------------------------------------------------------------------------
# Task 2.13 — Unit test: missing input file exit behavior
# Feature: demand-sense, Unit test: missing input file exit
# ---------------------------------------------------------------------------

class TestMissingInputFileExit:
    """
    Verify that scripts/preprocess.py exits with a non-zero status code and
    prints an error message when neither input file (xlsx nor csv) is present.
    """

    def test_missing_input_file_exits_nonzero(self, tmp_path, monkeypatch):
        # Feature: demand-sense, Unit test: missing input file exit
        # Point DATA_DIR to an empty temp directory so no input files exist
        script_path = os.path.join(_PROJECT_ROOT, "scripts", "preprocess.py")

        # Run the script with a patched data directory via environment variable
        # We override the data path by monkey-patching the module constants via
        # subprocess with a modified environment that makes the data dir empty.
        # The simplest approach: run the script in a subprocess and check exit code.
        env = os.environ.copy()
        # We'll use a temp directory as the project root so no data files exist
        env["DEMANDSENSE_DATA_DIR"] = str(tmp_path)

        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )

        assert result.returncode != 0, (
            "preprocess.py should exit with non-zero status when input file is missing, "
            f"but exited with {result.returncode}"
        )

    def test_missing_input_file_prints_error_message(self, tmp_path):
        # Feature: demand-sense, Unit test: missing input file exit
        script_path = os.path.join(_PROJECT_ROOT, "scripts", "preprocess.py")

        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )

        # The script should print an error to stderr
        combined_output = result.stdout + result.stderr
        assert "ERROR" in combined_output.upper() or "error" in combined_output.lower(), (
            "preprocess.py should print an error message when input file is missing. "
            f"Got stdout: {result.stdout!r}, stderr: {result.stderr!r}"
        )

    def test_load_input_exits_when_no_files(self, tmp_path, monkeypatch):
        # Feature: demand-sense, Unit test: missing input file exit
        # Test _load_input directly by patching the path constants
        import importlib
        import scripts.preprocess as preprocess_script

        # Patch the path constants to point to non-existent files
        monkeypatch.setattr(preprocess_script, "_XLSX_PATH", str(tmp_path / "missing.xlsx"))
        monkeypatch.setattr(preprocess_script, "_CSV_PATH", str(tmp_path / "missing.csv"))

        with pytest.raises(SystemExit) as exc_info:
            preprocess_script._load_input()

        assert exc_info.value.code != 0, (
            f"_load_input should sys.exit with non-zero code, got {exc_info.value.code}"
        )
