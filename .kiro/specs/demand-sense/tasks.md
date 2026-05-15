# Implementation Plan: DemandSense — Demand Forecasting & Anomaly Detection System

## Overview

This plan builds DemandSense incrementally: data pipeline first, then ML training scripts, then Python serverless API functions, then the React frontend, and finally wiring and deployment configuration. Each step produces runnable, testable code before the next step begins. Property-based tests (Hypothesis) are placed immediately after the code they validate to catch regressions early.

---

## Tasks

- [x] 1. Project scaffold and shared configuration
  - Create the top-level directory structure: `api/`, `lib/`, `models/`, `data/`, `tests/`, `frontend/src/api/`, `frontend/src/components/`
  - Add `requirements.txt` with pinned versions for `pandas`, `numpy`, `xgboost`, `scikit-learn`, `joblib`, `hypothesis`, `pytest`, `flask` (or Vercel handler shim)
  - Add `vercel.json` routing `/api/*` to Python functions and all other paths to the React SPA fallback
  - Add `frontend/package.json` with pinned versions for `react`, `recharts`, `tailwindcss`, `jest`, `@testing-library/react`, `@testing-library/jest-dom`
  - _Requirements: 13.1, 13.2, 13.5_

- [x] 2. Data preprocessing pipeline (`lib/preprocess.py`)
  - [x] 2.1 Implement `clean_transactions(df)` — remove cancelled invoices (InvoiceNo starts with `C`), non-positive Quantity, and non-positive UnitPrice rows
    - _Requirements: 1.1, 1.2, 1.3_

  - [x]* 2.2 Write property test for `clean_transactions` (Property 1)
    - **Property 1: Data Cleaning Removes All Invalid Records**
    - **Validates: Requirements 1.1, 1.2, 1.3**
    - Use `st.dataframes()` with mixed valid/invalid rows; assert no cancelled, zero-quantity, or zero-price rows remain after cleaning
    - Tag: `# Feature: demand-sense, Property 1: Data cleaning removes invalid records`

  - [x] 2.3 Implement `aggregate_daily(df)` — group by (StockCode, date), sum Quantity, compute mean UnitPrice
    - _Requirements: 1.4_

  - [x]* 2.4 Write property test for `aggregate_daily` (Property 2)
    - **Property 2: Daily Aggregation Preserves Quantity Sum**
    - **Validates: Requirements 1.4**
    - Use `st.dataframes()` with known (StockCode, date) groups; assert output quantity equals sum of input quantities per group
    - Tag: `# Feature: demand-sense, Property 2: Aggregation preserves quantity sum`

  - [x] 2.5 Implement `engineer_features(df)` — add all 10 feature columns (`day_of_week`, `month`, `is_weekend`, `rolling_7d_mean`, `rolling_30d_mean`, `rolling_7d_std`, `lag_1`, `lag_7`, `lag_14`, `is_month_end`); fill NaN with 0
    - _Requirements: 1.5_

  - [x]* 2.6 Write property test for `engineer_features` (Property 3)
    - **Property 3: Feature Engineering Produces a Complete, Non-Null Feature Set**
    - **Validates: Requirements 1.5**
    - Use `st.dataframes()` with varying history lengths; assert all 10 feature columns present and no NaN values
    - Tag: `# Feature: demand-sense, Property 3: Feature engineering completeness`

  - [x] 2.7 Implement top-20 product selection — subset to top 20 StockCodes by total sales volume; break ties by lexicographic ascending StockCode
    - _Requirements: 1.6_

  - [x]* 2.8 Write property test for top-20 selection (Property 4)
    - **Property 4: Top-20 Selection Invariant**
    - **Validates: Requirements 1.6**
    - Use `st.lists()` of (StockCode, volume) pairs with > 20 distinct codes; assert output ≤ 20 codes and no excluded code has higher volume than any included code
    - Tag: `# Feature: demand-sense, Property 4: Top-20 selection invariant`

  - [x] 2.9 Implement short-history exclusion — exclude any StockCode with fewer than 30 days of history after cleaning
    - _Requirements: 1.8_

  - [x]* 2.10 Write property test for short-history exclusion (Property 6)
    - **Property 6: Short-History Products Are Excluded**
    - **Validates: Requirements 1.8**
    - Use `st.dataframes()` with some products having < 30 days; assert no StockCode in output has fewer than 30 records
    - Tag: `# Feature: demand-sense, Property 6: Short-history exclusion`

  - [x] 2.11 Implement `data/clean.json` serialization — write preprocessed DataFrame to `data/clean.json` as a flat JSON array; handle missing input file with non-zero exit and error message
    - _Requirements: 1.7, 1.9_

  - [x]* 2.12 Write property test for serialization round-trip (Property 5)
    - **Property 5: Preprocessed Data Serialization Round-Trip**
    - **Validates: Requirements 1.7**
    - Use `st.dataframes()` of preprocessed records; assert serialize → deserialize produces equivalent records within floating-point precision
    - Tag: `# Feature: demand-sense, Property 5: Serialization round-trip`

  - [x]* 2.13 Write unit test for missing input file exit behavior
    - Assert preprocessor exits with non-zero status and prints error message when input file is absent
    - _Requirements: 1.9_

- [x] 3. Checkpoint — Ensure all preprocessing tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Anomaly detection library (`lib/predict_anomaly.py`)
  - [x] 4.1 Implement `_detect_demand_spikes(df)` — rolling Z-score; flag rows where quantity > 3σ above 30-day rolling mean; leave flag unset when fewer than 30 days of prior history exist
    - _Requirements: 3.2_

  - [x]* 4.2 Write property test for demand spike detection (Property 7)
    - **Property 7: Demand Spike Detection Rule**
    - **Validates: Requirements 3.2**
    - Use `st.floats()` for quantity, mean, std; assert rows exceeding threshold are flagged and rows with insufficient history are not
    - Tag: `# Feature: demand-sense, Property 7: Demand spike detection rule`

  - [x] 4.3 Implement `_detect_price_anomalies(df)` — flag rows where unit_price deviates > 2.5σ from product median; skip detection when product price std is zero
    - _Requirements: 3.3_

  - [x]* 4.4 Write property test for price anomaly detection (Property 8)
    - **Property 8: Price Anomaly Detection Rule**
    - **Validates: Requirements 3.3**
    - Use `st.floats()` for price, median, std; assert rows exceeding threshold are flagged; assert zero-std products are skipped
    - Tag: `# Feature: demand-sense, Property 8: Price anomaly detection rule`

  - [x] 4.5 Implement `_detect_stockout_signals(df)` — flag every day in a run of 3+ consecutive zero-quantity days
    - _Requirements: 3.4_

  - [x]* 4.6 Write property test for stockout signal detection (Property 9)
    - **Property 9: Stockout Signal Detection Rule**
    - **Validates: Requirements 3.4**
    - Use `st.lists(st.integers(min_value=0))` for quantity sequences; assert every day in a run of ≥ 3 consecutive zeros is flagged
    - Tag: `# Feature: demand-sense, Property 9: Stockout signal detection rule`

  - [x] 4.7 Implement `load_anomaly_model(product_id)` — load `iso_{product_id}.pkl` with module-level `_iso_cache`; raise `ModelNotFoundError` on missing file
    - _Requirements: 3.1, 3.6_

  - [x] 4.8 Implement `score_anomalies(product_id, history)` — run Isolation Forest + all three rule-based detectors; assign `anomaly_score`, `is_anomaly`, and `reason` with priority order `demand_spike > price_anomaly > stockout_signal > isolation_forest`
    - _Requirements: 3.7_

  - [x]* 4.9 Write property test for anomaly output structure and priority ordering (Property 10)
    - **Property 10: Anomaly Output Structure and Priority Ordering**
    - **Validates: Requirements 3.7**
    - Use `st.dataframes()` with known detector triggers; assert every record has required fields and priority ordering is respected when multiple detectors fire
    - Tag: `# Feature: demand-sense, Property 10: Anomaly output structure and priority`

- [x] 5. Anomaly detection training script (`scripts/train_anomaly.py`)
  - Train one Isolation Forest model per product on (quantity, unit_price) feature space using products with ≥ 30 days of history
  - Serialize each model to `models/iso_{product_id}.pkl` using joblib
  - _Requirements: 3.1, 3.5, 3.6_

- [x] 6. Forecast library (`lib/predict_forecast.py`)
  - [x] 6.1 Implement `load_forecast_models(product_id)` — load `xgb_{product_id}.pkl`, `xgb_lower_{product_id}.pkl`, `xgb_upper_{product_id}.pkl` with module-level `_model_cache`; raise `ModelNotFoundError` / `ModelLoadError` on failure
    - _Requirements: 4.8_

  - [x] 6.2 Implement `build_future_features(last_known, horizon)` in `lib/preprocess.py` — construct feature matrix for next `horizon` days using last known history for lags and rolling stats
    - _Requirements: 4.1, 4.2_

  - [x] 6.3 Implement `generate_forecast(product_id, horizon_days, history)` — iterative multi-step forecast loop; clamp lower ≤ predicted ≤ upper at each step; return list of `{date, predicted, lower, upper}` dicts
    - _Requirements: 4.1, 4.2_

  - [x] 6.4 Implement `compute_metrics(product_id, history)` — compute MAPE and RMSE on chronologically ordered 20% holdout split; return `{mape, rmse}` with both values ≥ 0
    - _Requirements: 2.4, 2.5, 4.3_

  - [x] 6.5 Implement `get_feature_importances(product_id)` — return sorted list of `{name, importance}` from point model's `feature_importances_` attribute, descending by importance
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 7. Forecast model training script (`scripts/train_forecast.py`)
  - Train point, lower (α=0.1), and upper (α=0.9) XGBoost models per product on the 10 engineered features
  - Skip products with < 60 days of data with a logged warning
  - Serialize models to `models/xgb_{product_id}.pkl`, `models/xgb_lower_{product_id}.pkl`, `models/xgb_upper_{product_id}.pkl`
  - _Requirements: 2.1, 2.2, 2.3, 2.6, 2.7, 2.8_

- [x]* 7.1 Write unit test for short-data product skip behavior
  - Assert that a product with < 60 days of data is skipped with a warning and remaining products continue training
  - _Requirements: 2.8_

- [x] 8. Checkpoint — Ensure all ML library and training tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. API handlers — products and importance endpoints
  - [x] 9.1 Implement `api/products.py` — GET `/api/products`; load `data/clean.json` at module level; return products sorted descending by total sales volume with `product_id` and `description` fields; return 500 if data file cannot be loaded
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x]* 9.2 Write property test for products response completeness and structure (Property 19)
    - **Property 19: Products Response Completeness and Structure**
    - **Validates: Requirements 7.1, 7.2**
    - Assert response contains exactly the set of products in Model_Store and every entry has `product_id` and `description` fields
    - Tag: `# Feature: demand-sense, Property 19: Products completeness and structure`

  - [x]* 9.3 Write property test for products sorted by descending sales volume (Property 20)
    - **Property 20: Products Sorted by Descending Sales Volume**
    - **Validates: Requirements 7.3**
    - Assert response products are in descending order of total quantity sum from `data/clean.json`
    - Tag: `# Feature: demand-sense, Property 20: Products sorted by volume`

  - [x]* 9.4 Write unit test for missing `data/clean.json` returning 500
    - _Requirements: 7.4_

  - [x] 9.5 Implement `api/importance.py` — GET `/api/importance?product_id=`; validate `product_id` query param (400 if missing); return 404 for unknown product; return sorted `features` array from `get_feature_importances()`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x]* 9.6 Write property test for feature importance response structure and ordering (Property 18)
    - **Property 18: Feature Importance Response Structure and Ordering**
    - **Validates: Requirements 6.1, 6.2**
    - Use `st.sampled_from(valid_products)`; assert every entry has `name` and `importance` fields and array is sorted descending
    - Tag: `# Feature: demand-sense, Property 18: Importance structure and ordering`

  - [x]* 9.7 Write unit tests for importance endpoint error cases
    - Missing `product_id` query param → 400
    - Unknown `product_id` → 404
    - Feature importances match model's `feature_importances_` attribute
    - _Requirements: 6.3, 6.4, 6.5_

- [x] 10. API handlers — forecast and anomalies endpoints
  - [x] 10.1 Implement `api/forecast.py` — POST `/api/forecast`; validate `product_id` (non-empty string) and `horizon_days` ∈ {7, 14, 30}; return 400 for invalid horizon, 404 for unknown product, 500 for model load failure; call `generate_forecast()` and `compute_metrics()`; return `{product_id, forecast[], metrics}`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.8_

  - [x]* 10.2 Write property test for forecast array length equals horizon (Property 11)
    - **Property 11: Forecast Array Length Equals Horizon**
    - **Validates: Requirements 4.1**
    - Use `st.sampled_from(valid_products)`, `st.sampled_from([7, 14, 30])`; assert `len(forecast) == horizon_days`
    - Tag: `# Feature: demand-sense, Property 11: Forecast array length equals horizon`

  - [x]* 10.3 Write property test for confidence band ordering invariant (Property 12)
    - **Property 12: Confidence Band Ordering Invariant**
    - **Validates: Requirements 4.2**
    - Use `st.sampled_from(valid_products)`, `st.sampled_from([7, 14, 30])`; assert `lower ≤ predicted ≤ upper` for every entry
    - Tag: `# Feature: demand-sense, Property 12: Confidence band ordering invariant`

  - [x]* 10.4 Write property test for forecast metrics non-negative (Property 13)
    - **Property 13: Forecast Metrics Are Non-Negative**
    - **Validates: Requirements 2.5, 4.3**
    - Use `st.sampled_from(valid_products)`; assert `mape ≥ 0` and `rmse ≥ 0`
    - Tag: `# Feature: demand-sense, Property 13: Forecast metrics non-negative`

  - [x]* 10.5 Write property test for invalid horizon returning HTTP 400 (Property 14)
    - **Property 14: Invalid Horizon Returns HTTP 400**
    - **Validates: Requirements 4.5**
    - Use `st.integers().filter(lambda x: x not in {7, 14, 30})`; assert HTTP 400 response
    - Tag: `# Feature: demand-sense, Property 14: Invalid horizon returns 400`

  - [x]* 10.6 Write unit tests for forecast endpoint error cases
    - Unknown `product_id` → 404
    - Missing model file → 500
    - _Requirements: 4.4, 4.8_

  - [x] 10.7 Implement `api/anomalies.py` — POST `/api/anomalies`; validate `product_id` (non-empty, 400 if missing/empty); return 404 for unknown product; call `score_anomalies()`; return `{product_id, anomalies[], total_anomalies}`
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

  - [x]* 10.8 Write property test for anomaly count invariant (Property 15)
    - **Property 15: Anomaly Count Invariant**
    - **Validates: Requirements 5.1**
    - Use `st.sampled_from(valid_products)`; assert `total_anomalies == len(anomalies)`
    - Tag: `# Feature: demand-sense, Property 15: Anomaly count invariant`

  - [x]* 10.9 Write property test for anomaly record structure (Property 16)
    - **Property 16: Anomaly Record Structure**
    - **Validates: Requirements 5.2**
    - Use `st.sampled_from(valid_products)`; assert every entry has all required fields with correct types and valid reason strings
    - Tag: `# Feature: demand-sense, Property 16: Anomaly record structure`

  - [x]* 10.10 Write property test for missing product_id returning HTTP 400 (Property 17)
    - **Property 17: Missing or Malformed Product ID Returns HTTP 400**
    - **Validates: Requirements 5.5**
    - Use `st.one_of(st.none(), st.just(""), st.just("   "))`; assert HTTP 400 response
    - Tag: `# Feature: demand-sense, Property 17: Missing product_id returns 400`

  - [x]* 10.11 Write unit test for unknown product_id returning 404 on anomalies endpoint
    - _Requirements: 5.3_

- [x] 11. Checkpoint — Ensure all API handler tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Frontend API client (`frontend/src/api/client.js`)
  - Implement `fetchProducts()`, `fetchForecast(productId, horizonDays)`, `fetchAnomalies(productId)`, `fetchImportance(productId)`
  - Each function uses `AbortController` with a 12-second timeout; throws a typed error on non-2xx responses
  - _Requirements: 4.9, 8.2, 13.2_

- [x] 13. Frontend shared components — SkeletonLoader and error display
  - Implement a reusable `SkeletonLoader` component (animated placeholder)
  - Implement a reusable `ErrorMessage` component with retry button
  - _Requirements: 14.1, 14.2, 14.3_

- [x] 14. `ProductSelector` component (`frontend/src/components/ProductSelector.jsx`)
  - [x] 14.1 Implement searchable dropdown that filters by both product name and product ID; renders skeleton while products are loading; shows error with "Refresh page" instruction if `/api/products` fails
    - _Requirements: 8.1, 8.5, 14.5_

  - [x]* 14.2 Write Jest unit tests for `ProductSelector`
    - Renders dropdown with products list
    - Filters correctly by product name
    - Filters correctly by product ID
    - Shows error state when products fail to load
    - _Requirements: 8.1_

- [x] 15. `MetricsCards` component (`frontend/src/components/MetricsCards.jsx`)
  - [x] 15.1 Implement three cards: MAPE, RMSE, Total Anomalies; show "N/A" when value unavailable; show skeleton while loading; show error indicator on failure
    - _Requirements: 10.1, 10.2, 10.3, 10.5_

  - [x]* 15.2 Write Jest unit tests for `MetricsCards`
    - Shows "N/A" when metric value is null/undefined
    - Renders skeleton loaders while fetching
    - Shows error indicator on failure
    - _Requirements: 10.1, 10.2, 10.5_

- [x] 16. `ForecastChart` component (`frontend/src/components/ForecastChart.jsx`)
  - [x] 16.1 Implement Recharts `ComposedChart` with solid line for historical actuals, dashed line for forecast predicted values, and shaded `Area` for confidence band (lower/upper); custom tooltip showing date + actual for historical points and date + predicted + lower + upper for forecast points; renders `SkeletonLoader` while loading; renders error message on failure
    - _Requirements: 9.1, 9.2, 9.5, 9.6_

  - [x]* 16.2 Write Jest unit tests for `ForecastChart`
    - Renders skeleton loader while `loading.forecast` is true
    - Renders error message when `errors.forecast` is set
    - Renders chart when data is available
    - _Requirements: 9.6, 14.1_

- [x] 17. `AnomalyTable` component (`frontend/src/components/AnomalyTable.jsx`)
  - [x] 17.1 Implement filterable table with columns: Date, Quantity, Unit Price, Anomaly Score, Reason, Flag; filter chips: All / Demand Spike / Price Anomaly / Stockout Signal; row highlighting red for `anomaly_score < -0.1`, amber for `-0.1 ≤ anomaly_score ≤ 0.0`; empty state message when no anomalies
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x]* 17.2 Write Jest unit tests for `AnomalyTable`
    - Filter chips correctly filter rows by reason (All, Demand Spike, Price Anomaly, Stockout Signal)
    - Rows highlighted red when `anomaly_score < -0.1`
    - Rows highlighted amber when `-0.1 ≤ anomaly_score ≤ 0.0`
    - Empty state message displayed when anomalies array is empty
    - _Requirements: 11.3, 11.4, 11.5_

- [x] 18. `FeatureImportance` component (`frontend/src/components/FeatureImportance.jsx`)
  - [x] 18.1 Implement Recharts horizontal `BarChart` sorted descending by importance; label each bar with feature name + importance to 3 decimal places; subtitle "What drove this forecast"; skeleton while loading; error message when features array is empty or request fails
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

  - [x]* 18.2 Write Jest unit tests for `FeatureImportance`
    - Bars sorted descending by importance
    - Each bar labeled with feature name and importance to 3 decimal places
    - Error message shown when features array is empty
    - _Requirements: 12.2, 12.3, 12.6_

- [x] 19. `App.jsx` — state management and data orchestration
  - [x] 19.1 Implement full `AppState` shape; on mount, fetch `/api/products` and auto-select first product; on product or horizon change, fire three parallel fetches (forecast, anomalies, importance) with per-region loading and error state; implement retry handlers; ensure at least one visible element is always rendered (skeleton, error, data, or "Select a product" prompt)
    - _Requirements: 8.2, 8.3, 8.4, 8.5, 9.3, 9.4, 10.4, 14.1, 14.2, 14.3, 14.4, 14.5_

  - [x]* 19.2 Write Jest unit tests for `App`
    - Auto-selects first product on initial load
    - Retains prior product data when a new request fails
    - Displays "Select a product" prompt before any product is selected
    - Displays skeleton loaders in all four regions while fetching
    - _Requirements: 8.5, 8.4, 14.3, 14.4_

- [x] 20. Checkpoint — Ensure all frontend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 21. Vercel deployment configuration and smoke tests
  - [x] 21.1 Finalize `vercel.json` — confirm `/api/*` routes to Python functions and SPA fallback for all other paths; verify each function bundle does not exceed 50 MB
    - _Requirements: 13.1, 13.2, 13.4_

  - [x] 21.2 Write smoke test script (`tests/smoke.py`) — assert all 4 endpoints return 200 for a known valid product; assert model files exist with correct naming pattern for all 20 products; assert total model store size ≤ 50 MB; assert `data/clean.json` is present and parseable
    - _Requirements: 2.7, 13.3, 13.4_

- [x] 22. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery
- Each task references specific requirements for full traceability
- Property-based tests use Hypothesis (`@settings(max_examples=100)`) and are tagged with `# Feature: demand-sense, Property N: <text>`
- Frontend tests use Jest + React Testing Library
- Checkpoints at tasks 3, 8, 11, 20, and 22 ensure incremental validation at each layer boundary
- Pre-trained `.pkl` models must exist in `models/` before API handler tests can run; training scripts (tasks 5 and 7) must be executed first
- The `data/clean.json` file must exist before any API handler or frontend integration test can run; the preprocessing pipeline (task 2) must be executed first

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1", "2.3", "2.5", "2.7", "2.9", "2.11"] },
    { "id": 1, "tasks": ["2.2", "2.4", "2.6", "2.8", "2.10", "2.12", "2.13"] },
    { "id": 2, "tasks": ["4.1", "4.3", "4.5", "4.7", "6.2"] },
    { "id": 3, "tasks": ["4.2", "4.4", "4.6", "4.8", "4.9", "6.1", "6.3", "6.4", "6.5", "7.1"] },
    { "id": 4, "tasks": ["9.1", "9.5", "10.1", "10.7"] },
    { "id": 5, "tasks": ["9.2", "9.3", "9.4", "9.6", "9.7", "10.2", "10.3", "10.4", "10.5", "10.6", "10.8", "10.9", "10.10", "10.11"] },
    { "id": 6, "tasks": ["14.1", "15.1", "16.1", "17.1", "18.1"] },
    { "id": 7, "tasks": ["14.2", "15.2", "16.2", "17.2", "18.2", "19.1"] },
    { "id": 8, "tasks": ["19.2", "21.1"] },
    { "id": 9, "tasks": ["21.2"] }
  ]
}
```
