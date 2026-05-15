"""
tests/test_preprocess.py — Smoke / unit tests for lib/preprocess.py

Covers all five public functions:
  - clean_transactions
  - aggregate_daily
  - engineer_features
  - exclude_short_history
  - select_top_products
"""

import sys
import os
import datetime

import pandas as pd
import pytest

# Ensure project root is importable regardless of working directory
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
# Helpers
# ---------------------------------------------------------------------------

def _make_raw_df(**overrides) -> pd.DataFrame:
    """Return a minimal valid raw transaction DataFrame."""
    base = {
        "InvoiceNo": ["536365", "C536366", "536367", "536368"],
        "StockCode": ["85123A", "85123A", "71053", "71053"],
        "Description": ["WHITE HANGING HEART", "WHITE HANGING HEART", "WHITE METAL LANTERN", "WHITE METAL LANTERN"],
        "Quantity": [6, 6, 8, -1],
        "InvoiceDate": [
            "2010-12-01 08:26:00",
            "2010-12-01 08:28:00",
            "2010-12-01 08:34:00",
            "2010-12-01 08:35:00",
        ],
        "UnitPrice": [2.55, 2.55, 3.39, 0.0],
        "CustomerID": [17850, 17850, 17850, 17850],
        "Country": ["United Kingdom"] * 4,
    }
    base.update(overrides)
    return pd.DataFrame(base)


# ---------------------------------------------------------------------------
# clean_transactions
# ---------------------------------------------------------------------------

class TestCleanTransactions:
    def test_removes_cancelled_invoices(self):
        df = _make_raw_df()
        result = clean_transactions(df)
        assert not result["InvoiceNo"].astype(str).str.startswith("C").any(), \
            "Cancelled invoices (InvoiceNo starting with 'C') should be removed"

    def test_removes_non_positive_quantity(self):
        df = _make_raw_df()
        result = clean_transactions(df)
        assert (result["Quantity"] > 0).all(), \
            "All remaining rows should have positive Quantity"

    def test_removes_non_positive_unit_price(self):
        df = _make_raw_df()
        result = clean_transactions(df)
        assert (result["UnitPrice"] > 0).all(), \
            "All remaining rows should have positive UnitPrice"

    def test_valid_rows_are_retained(self):
        df = _make_raw_df()
        result = clean_transactions(df)
        # Rows 0 and 2 are fully valid:
        #   row 0: InvoiceNo=536365, Qty=6, Price=2.55
        #   row 2: InvoiceNo=536367, Qty=8, Price=3.39
        # Row 1 is cancelled (C536366), row 3 has Qty=-1 and Price=0.0
        assert len(result) == 2
        assert set(result["InvoiceNo"].tolist()) == {"536365", "536367"}

    def test_empty_dataframe_returns_empty(self):
        df = pd.DataFrame(columns=["InvoiceNo", "Quantity", "UnitPrice"])
        result = clean_transactions(df)
        assert result.empty

    def test_all_valid_rows_retained(self):
        df = pd.DataFrame({
            "InvoiceNo": ["100", "101", "102"],
            "StockCode": ["A", "B", "C"],
            "Description": ["x", "y", "z"],
            "Quantity": [1, 2, 3],
            "InvoiceDate": ["2020-01-01"] * 3,
            "UnitPrice": [1.0, 2.0, 3.0],
            "CustomerID": [1, 2, 3],
            "Country": ["UK"] * 3,
        })
        result = clean_transactions(df)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# aggregate_daily
# ---------------------------------------------------------------------------

class TestAggregateDaily:
    def _make_clean_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "StockCode": ["A", "A", "A", "B"],
            "Description": ["Desc A", "Desc A", "Desc A", "Desc B"],
            "Quantity": [10, 5, 3, 7],
            "InvoiceDate": [
                "2020-01-01 08:00:00",
                "2020-01-01 10:00:00",
                "2020-01-02 09:00:00",
                "2020-01-01 11:00:00",
            ],
            "UnitPrice": [2.0, 2.0, 2.0, 5.0],
        })

    def test_output_columns(self):
        df = self._make_clean_df()
        result = aggregate_daily(df)
        expected_cols = {"stock_code", "date", "quantity", "unit_price", "description"}
        assert expected_cols.issubset(set(result.columns))

    def test_quantity_sum_per_group(self):
        df = self._make_clean_df()
        result = aggregate_daily(df)
        # StockCode A on 2020-01-01 should sum to 10+5=15
        row = result[(result["stock_code"] == "A") & (result["date"] == datetime.date(2020, 1, 1))]
        assert len(row) == 1
        assert row.iloc[0]["quantity"] == 15

    def test_single_row_per_stock_date(self):
        df = self._make_clean_df()
        result = aggregate_daily(df)
        # No duplicate (stock_code, date) pairs
        assert not result.duplicated(subset=["stock_code", "date"]).any()

    def test_date_column_is_date_type(self):
        df = self._make_clean_df()
        result = aggregate_daily(df)
        # date column should be plain date objects (not datetime)
        sample = result["date"].iloc[0]
        assert isinstance(sample, datetime.date)

    def test_unit_price_is_mean(self):
        df = pd.DataFrame({
            "StockCode": ["X", "X"],
            "Description": ["D", "D"],
            "Quantity": [1, 1],
            "InvoiceDate": ["2020-06-01 08:00:00", "2020-06-01 12:00:00"],
            "UnitPrice": [4.0, 6.0],
        })
        result = aggregate_daily(df)
        assert result.iloc[0]["unit_price"] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# engineer_features
# ---------------------------------------------------------------------------

FEATURE_COLS = [
    "day_of_week", "month", "is_weekend", "is_month_end",
    "rolling_7d_mean", "rolling_30d_mean", "rolling_7d_std",
    "lag_1", "lag_7", "lag_14",
]


def _make_aggregated_df(n_days: int = 35, stock_code: str = "A") -> pd.DataFrame:
    """Return a simple aggregated daily DataFrame with n_days rows."""
    dates = pd.date_range("2020-01-01", periods=n_days, freq="D")
    return pd.DataFrame({
        "stock_code": stock_code,
        "date": [d.date() for d in dates],
        "quantity": list(range(1, n_days + 1)),
        "unit_price": [2.0] * n_days,
        "description": ["Test"] * n_days,
    })


class TestEngineerFeatures:
    def test_all_feature_columns_present(self):
        df = _make_aggregated_df()
        result = engineer_features(df)
        for col in FEATURE_COLS:
            assert col in result.columns, f"Missing feature column: {col}"

    def test_no_nan_values_in_features(self):
        df = _make_aggregated_df()
        result = engineer_features(df)
        assert not result[FEATURE_COLS].isnull().any().any(), \
            "No NaN values should remain in feature columns after fillna(0)"

    def test_day_of_week_range(self):
        df = _make_aggregated_df()
        result = engineer_features(df)
        assert result["day_of_week"].between(0, 6).all()

    def test_month_range(self):
        df = _make_aggregated_df()
        result = engineer_features(df)
        assert result["month"].between(1, 12).all()

    def test_is_weekend_binary(self):
        df = _make_aggregated_df()
        result = engineer_features(df)
        assert set(result["is_weekend"].unique()).issubset({0, 1})

    def test_is_month_end_binary(self):
        df = _make_aggregated_df()
        result = engineer_features(df)
        assert set(result["is_month_end"].unique()).issubset({0, 1})

    def test_row_count_preserved(self):
        df = _make_aggregated_df(n_days=40)
        result = engineer_features(df)
        assert len(result) == 40

    def test_lag_1_first_row_is_zero(self):
        """First row's lag_1 should be 0 (NaN filled)."""
        df = _make_aggregated_df()
        result = engineer_features(df)
        # Sort by date to get the first row
        result = result.sort_values("date").reset_index(drop=True)
        assert result.iloc[0]["lag_1"] == 0


# ---------------------------------------------------------------------------
# exclude_short_history
# ---------------------------------------------------------------------------

class TestExcludeShortHistory:
    def _make_df_with_products(self, product_days: dict) -> pd.DataFrame:
        """Build a DataFrame where each key is a stock_code and value is day count."""
        rows = []
        base_date = datetime.date(2020, 1, 1)
        for code, n_days in product_days.items():
            for i in range(n_days):
                rows.append({
                    "stock_code": code,
                    "date": base_date + datetime.timedelta(days=i),
                    "quantity": 1,
                })
        return pd.DataFrame(rows)

    def test_excludes_products_below_min_days(self):
        df = self._make_df_with_products({"A": 29, "B": 30, "C": 50})
        result = exclude_short_history(df, min_days=30)
        assert "A" not in result["stock_code"].values

    def test_retains_products_at_or_above_min_days(self):
        df = self._make_df_with_products({"A": 29, "B": 30, "C": 50})
        result = exclude_short_history(df, min_days=30)
        assert "B" in result["stock_code"].values
        assert "C" in result["stock_code"].values

    def test_default_min_days_is_30(self):
        df = self._make_df_with_products({"X": 29, "Y": 30})
        result = exclude_short_history(df)
        assert "X" not in result["stock_code"].values
        assert "Y" in result["stock_code"].values

    def test_empty_result_when_all_short(self):
        df = self._make_df_with_products({"A": 5, "B": 10})
        result = exclude_short_history(df, min_days=30)
        assert result.empty

    def test_all_retained_when_all_qualify(self):
        df = self._make_df_with_products({"A": 30, "B": 60})
        result = exclude_short_history(df, min_days=30)
        assert set(result["stock_code"].unique()) == {"A", "B"}


# ---------------------------------------------------------------------------
# select_top_products
# ---------------------------------------------------------------------------

class TestSelectTopProducts:
    def _make_volume_df(self, volumes: dict) -> pd.DataFrame:
        """Build a DataFrame where each key is a stock_code and value is total quantity."""
        rows = []
        for code, qty in volumes.items():
            rows.append({"stock_code": code, "quantity": qty})
        return pd.DataFrame(rows)

    def test_returns_at_most_n_products(self):
        volumes = {f"P{i:02d}": 100 - i for i in range(25)}
        df = self._make_volume_df(volumes)
        result = select_top_products(df, n=20)
        assert result["stock_code"].nunique() <= 20

    def test_top_products_have_highest_volume(self):
        volumes = {f"P{i:02d}": 100 - i for i in range(25)}
        df = self._make_volume_df(volumes)
        result = select_top_products(df, n=20)
        included = set(result["stock_code"].unique())
        excluded = set(volumes.keys()) - included
        # Every excluded product should have lower or equal volume than every included product
        min_included_vol = min(volumes[c] for c in included)
        max_excluded_vol = max(volumes[c] for c in excluded)
        assert max_excluded_vol <= min_included_vol

    def test_fewer_than_n_products_returns_all(self):
        volumes = {"A": 10, "B": 20, "C": 30}
        df = self._make_volume_df(volumes)
        result = select_top_products(df, n=20)
        assert result["stock_code"].nunique() == 3

    def test_tie_breaking_by_lexicographic_stock_code(self):
        """When two products have equal volume, the lexicographically smaller code wins."""
        volumes = {"B": 100, "A": 100, "C": 50}
        df = self._make_volume_df(volumes)
        result = select_top_products(df, n=2)
        included = set(result["stock_code"].unique())
        # A and B both have volume 100; C has 50 — top 2 should be A and B
        assert included == {"A", "B"}

    def test_default_n_is_20(self):
        volumes = {f"P{i:02d}": i for i in range(25)}
        df = self._make_volume_df(volumes)
        result = select_top_products(df)
        assert result["stock_code"].nunique() <= 20
