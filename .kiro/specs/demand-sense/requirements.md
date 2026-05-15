# Requirements Document

## Introduction

DemandSense is a production-deployed ML web application that forecasts retail demand and detects sales and pricing anomalies. It is built on the UCI Online Retail Dataset and exposes a React frontend backed by Python serverless functions on Vercel. The system enables non-technical retail users to select a product, view a demand forecast with confidence bounds for the next 7, 14, or 30 days, inspect flagged anomalies in sales volume and unit price, and understand which features drove the forecast — all within a single public URL.

---

## Glossary

- **System**: The DemandSense application as a whole.
- **Dashboard**: The React single-page application served at the root Vercel URL.
- **API**: The set of Vercel Python serverless functions under the `/api/` path.
- **Forecaster**: The XGBoost-based demand forecasting subsystem (point + quantile models).
- **Anomaly_Detector**: The Isolation Forest + rolling Z-score anomaly detection subsystem.
- **Preprocessor**: The data cleaning and feature engineering pipeline (`lib/preprocess.py`).
- **Model_Store**: The set of pre-trained `.pkl` files committed to the repository under `models/`.
- **Product**: One of the top 20 StockCode items by total sales volume in the UCI Online Retail Dataset.
- **Horizon**: The number of future days for which a forecast is requested — one of 7, 14, or 30.
- **Confidence_Band**: The range between the lower (q=0.1) and upper (q=0.9) quantile regression predictions for each forecast date.
- **Anomaly_Score**: The raw Isolation Forest contamination score for a given daily record.
- **MAPE**: Mean Absolute Percentage Error — the primary forecast accuracy metric.
- **RMSE**: Root Mean Squared Error — the secondary forecast accuracy metric.
- **F1**: The harmonic mean of precision and recall used to evaluate anomaly detection quality.
- **Cold_Start**: The first invocation of a serverless function after a period of inactivity, during which the runtime must load dependencies and models.
- **Skeleton_Loader**: A placeholder UI element displayed while an API response is pending.

---

## Requirements

### Requirement 1: Data Preprocessing

**User Story:** As a data scientist, I want the raw UCI Online Retail Dataset to be cleaned and feature-engineered into a consistent daily format, so that all ML models train and infer on high-quality, structured data.

#### Acceptance Criteria

1. THE Preprocessor SHALL remove all invoice records where InvoiceNo begins with the character `C`.
2. THE Preprocessor SHALL remove all records where Quantity is less than or equal to zero.
3. THE Preprocessor SHALL remove all records where UnitPrice is less than or equal to zero.
4. THE Preprocessor SHALL aggregate the cleaned transaction records to daily total sales quantity (sum of Quantity) per StockCode per calendar date.
5. THE Preprocessor SHALL engineer the following features for each daily record: `day_of_week`, `month`, `is_weekend`, `rolling_7d_mean`, `rolling_30d_mean`, `rolling_7d_std`, `lag_1`, `lag_7`, `lag_14`, `is_month_end`. WHEN a rolling or lag value cannot be computed due to insufficient preceding history, THE Preprocessor SHALL fill that value with 0.
6. THE Preprocessor SHALL subset the aggregated data to the top 20 StockCode products ranked by total sales volume (sum of Quantity across all dates). IF two products have equal total sales volume, THE Preprocessor SHALL break the tie by selecting the product with the lower StockCode value (lexicographic ascending order).
7. THE Preprocessor SHALL serialize the preprocessed dataset to `data/clean.json` as a flat JSON array of records, where each record contains all engineered feature fields and null for any field that could not be computed.
8. WHEN the Preprocessor encounters a StockCode with fewer than 30 days of history after cleaning, THE Preprocessor SHALL exclude that StockCode from the output dataset.
9. IF the input UCI dataset file is missing or unreadable, THEN THE Preprocessor SHALL exit with a non-zero status code and print an error message identifying the missing file path.

---

### Requirement 2: Demand Forecasting Model Training

**User Story:** As a data scientist, I want XGBoost point and quantile regression models trained per product, so that the system can generate accurate forecasts with confidence bounds.

#### Acceptance Criteria

1. THE Forecaster SHALL train one XGBoost point forecast model per Product using the following 10 features from the preprocessed dataset: `lag_1`, `lag_7`, `lag_14`, `rolling_7d_mean`, `rolling_30d_mean`, `rolling_7d_std`, `day_of_week`, `month`, `is_weekend`, `is_month_end`.
2. THE Forecaster SHALL train one lower-bound quantile regression model per Product with `objective=reg:quantileerror` and `alpha=0.1`.
3. THE Forecaster SHALL train one upper-bound quantile regression model per Product with `objective=reg:quantileerror` and `alpha=0.9`.
4. WHEN evaluated on a chronologically ordered 20% holdout test split (i.e., the last 20% of dates for each Product), THE Forecaster SHALL achieve a MAPE below 15% for each trained Product model.
5. WHEN evaluated on a chronologically ordered 20% holdout test split, THE Forecaster SHALL record the RMSE value and expose it in the `metrics.rmse` field of the `/api/forecast` response.
6. THE Forecaster SHALL serialize each trained model to the `models/` directory as a `.pkl` file using joblib, with filenames following the pattern `xgb_{product_id}.pkl`, `xgb_lower_{product_id}.pkl`, and `xgb_upper_{product_id}.pkl`.
7. WHEN all models for the top 20 Products are serialized, THE Model_Store SHALL not exceed 50 MB in total size.
8. IF a Product has fewer than 60 days of data after preprocessing, THEN THE Forecaster SHALL skip training for that Product, log a warning identifying the Product and its available day count, and continue training remaining Products.

---

### Requirement 3: Anomaly Detection Model Training

**User Story:** As a data scientist, I want Isolation Forest models trained per product alongside rolling Z-score thresholds, so that the system can flag demand spikes, price anomalies, and stockout signals.

#### Acceptance Criteria

1. THE Anomaly_Detector SHALL train one Isolation Forest model per Product on the multivariate feature space of daily quantity and unit price, using only Products with at least 30 days of historical data.
2. IF the daily quantity for a record exceeds 3 standard deviations above the 30-day rolling mean for that Product AND at least 30 days of prior history exist for that Product, THEN THE Anomaly_Detector SHALL flag that record as a demand spike. IF fewer than 30 days of prior history exist, THE Anomaly_Detector SHALL leave the demand spike flag unset for that record.
3. IF the unit price for a record deviates more than 2.5 standard deviations from the Product median unit price, THEN THE Anomaly_Detector SHALL flag that record as a price anomaly. IF the standard deviation of unit price for a Product is zero, THE Anomaly_Detector SHALL skip price anomaly detection for that Product.
4. IF 3 or more consecutive days of zero sales are recorded for a Product, THEN THE Anomaly_Detector SHALL flag each of those days as a stockout signal.
5. WHEN evaluated against synthetically injected anomalies (5 random rows selected with random seed 42, with quantity multiplied by 10), THE Anomaly_Detector SHALL achieve an F1 score above 0.75.
6. THE Anomaly_Detector SHALL serialize each trained Isolation Forest model to the `models/` directory as a `.pkl` file using joblib, with filenames following the pattern `iso_{product_id}.pkl`.
7. THE Anomaly_Detector SHALL assign each daily record an `anomaly_score` (raw Isolation Forest score), a binary `is_anomaly` flag (set to true if the Isolation Forest flags the record OR if any rule-based detector fires), and a `reason` label. WHEN multiple detectors fire for the same record, THE Anomaly_Detector SHALL assign the `reason` label using the following priority order: `demand_spike` > `price_anomaly` > `stockout_signal`. WHEN only the Isolation Forest fires and no rule-based detector matches, THE Anomaly_Detector SHALL assign the `reason` label `isolation_forest`.

---

### Requirement 4: Forecast API Endpoint

**User Story:** As a frontend developer, I want a `/api/forecast` endpoint that returns a dated forecast array with confidence bounds and model metrics, so that the Dashboard can render the forecast chart.

#### Acceptance Criteria

1. WHEN a POST request is made to `/api/forecast` with a non-empty string `product_id` and a `horizon_days` value of 7, 14, or 30, THE API SHALL return a JSON response containing a `forecast` array of length equal to `horizon_days` and a `metrics` object.
2. WHEN the `forecast` array is returned, THE API SHALL include one entry per forecast date, each containing `date` (ISO 8601 format), `predicted` (float), `lower` (float), and `upper` (float) fields, where `lower ≤ predicted ≤ upper` for every entry.
3. WHEN the `metrics` object is returned, THE API SHALL include `mape` (a float ≥ 0 representing a percentage) and `rmse` (a float ≥ 0) values computed on the chronologically ordered 20% holdout test split for the requested Product.
4. IF a POST request is made to `/api/forecast` with a `product_id` that does not exist in the Model_Store, THEN THE API SHALL return an HTTP 404 response with an error message indicating the product was not found.
5. IF a POST request is made to `/api/forecast` with a `horizon_days` value other than 7, 14, or 30, THEN THE API SHALL return an HTTP 400 response with an error message indicating the valid horizon values.
6. WHEN a warm invocation of `/api/forecast` is processed (i.e., the function runtime is already loaded), THE API SHALL return a response without reloading models from disk, observable as a response time below 2 seconds for warm calls.
7. WHEN a valid warm request is processed, THE API SHALL return a response within 10 seconds.
8. IF the Model_Store files for the requested Product cannot be loaded (e.g., file corruption or missing file), THEN THE API SHALL return an HTTP 500 response with an error message indicating a model load failure.
9. WHEN a Cold_Start invocation occurs and the Vercel platform terminates the function before a response is returned, THE Dashboard SHALL handle the non-response gracefully by displaying an error message rather than hanging indefinitely.

---

### Requirement 5: Anomaly Detection API Endpoint

**User Story:** As a frontend developer, I want a `/api/anomalies` endpoint that returns all flagged anomaly records for a product, so that the Dashboard can render the anomaly table.

#### Acceptance Criteria

1. WHEN a POST request is made to `/api/anomalies` with a valid `product_id`, THE API SHALL return a JSON response containing an `anomalies` array and a `total_anomalies` count equal to the length of the `anomalies` array.
2. WHEN the `anomalies` array is returned, THE API SHALL include one entry per flagged daily record, each containing `date` (ISO 8601 string), `quantity` (numeric), `unit_price` (numeric), `anomaly_score` (numeric), `is_anomaly` (boolean), and `reason` (one of: `demand_spike`, `price_anomaly`, `stockout_signal`, `isolation_forest`) fields.
3. IF a POST request is made to `/api/anomalies` with a `product_id` that does not exist in the Model_Store, THEN THE API SHALL return an HTTP 404 response with an error message indicating the product was not found.
4. WHEN a valid request is processed, THE API SHALL return a response within 10 seconds, including Cold_Start model loading time.
5. IF a POST request is made to `/api/anomalies` with a missing or malformed `product_id` field, THEN THE API SHALL return an HTTP 400 response with an error message indicating the required field.

---

### Requirement 6: Feature Importance API Endpoint

**User Story:** As a frontend developer, I want a `/api/importance` endpoint that returns ranked feature importances for a product's forecast model, so that the Dashboard can render the feature importance chart.

#### Acceptance Criteria

1. WHEN a GET request is made to `/api/importance` with a valid `product_id` query parameter, THE API SHALL return a JSON response containing `product_id` and a `features` array.
2. THE `features` array SHALL contain one entry per feature, each with `name` (string) and `importance` (float, which may be negative) fields, sorted in descending order of importance value.
3. WHEN a GET request is made to `/api/importance` with a valid `product_id`, THE API SHALL derive feature importances from the XGBoost native `feature_importances_` attribute of the point forecast model for the requested Product.
4. IF a GET request is made to `/api/importance` with a `product_id` that does not exist in the Model_Store, THEN THE API SHALL return an HTTP 404 response with an error message indicating the product was not found.
5. IF a GET request is made to `/api/importance` without a `product_id` query parameter, THEN THE API SHALL return an HTTP 400 response with an error message indicating the required parameter.

---

### Requirement 7: Product List API Endpoint

**User Story:** As a frontend developer, I want a `/api/products` endpoint that returns the list of available products, so that the Dashboard can populate the product selector dropdown.

#### Acceptance Criteria

1. WHEN a GET request is made to `/api/products`, THE API SHALL return a JSON array of all Products available in the Model_Store.
2. WHEN the product list is successfully returned, THE API SHALL include exactly the `product_id` (StockCode string) and `description` (product name string from the UCI dataset) fields for each Product.
3. THE API SHALL return the product list in descending order of total sales volume, where total sales volume is defined as the sum of Quantity across all records in `data/clean.json` for that Product.
4. IF `data/clean.json` cannot be loaded, THEN THE API SHALL return an HTTP 500 response with an error message indicating a data load failure.

---

### Requirement 8: Dashboard Product Selection

**User Story:** As a retail analyst, I want to select a product from a searchable dropdown, so that all charts and metrics on the Dashboard update to reflect that product's data.

#### Acceptance Criteria

1. THE Dashboard SHALL display a searchable dropdown populated with all Products returned by `/api/products`, where the search filters by both product name and product ID.
2. WHEN a user selects a Product from the dropdown, THE Dashboard SHALL fetch updated forecast data (using the currently selected Horizon), anomaly data, and feature importance data for the selected Product.
3. WHILE data is being fetched after a product selection, THE Dashboard SHALL display Skeleton_Loaders in place of the ForecastChart, AnomalyTable, MetricsCards, and FeatureImportance components.
4. IF an API request fails after a product selection, THEN THE Dashboard SHALL display an error message identifying the failed operation and instructing the user to retry, and SHALL retain any previously loaded data for the prior product rather than displaying a blank screen.
5. WHEN the Dashboard first loads, THE Dashboard SHALL automatically select the first Product in the list returned by `/api/products` and fetch its data.

---

### Requirement 9: Forecast Chart

**User Story:** As a retail analyst, I want to view a forecast chart with historical sales, predicted values, and a confidence band, so that I can assess future demand and its uncertainty.

#### Acceptance Criteria

1. WHEN forecast data is loaded for the selected Product, THE Dashboard SHALL render a ComposedChart displaying historical daily sales as a solid line and forecast values as a dashed line.
2. WHEN forecast data is loaded for the selected Product, THE Dashboard SHALL render the Confidence_Band as a shaded area between the `lower` and `upper` forecast values for each forecast date.
3. THE Dashboard SHALL display a forecast horizon toggle with options for 7, 14, and 30 days.
4. WHEN a user selects a different Horizon from the toggle, THE Dashboard SHALL fetch a new forecast for the currently selected Product and re-render the chart.
5. WHEN a user hovers over a forecast data point on the chart, THE Dashboard SHALL display a tooltip showing the date, predicted quantity, lower bound, and upper bound. WHEN a user hovers over a historical data point, THE Dashboard SHALL display a tooltip showing the date and actual quantity only (no confidence range).
6. IF the forecast API request fails, THEN THE Dashboard SHALL display an error message in the ForecastChart region identifying the failure and instructing the user to retry, and SHALL NOT display a blank chart area.

---

### Requirement 10: Metrics Cards

**User Story:** As a retail analyst, I want to see key model performance metrics at a glance, so that I can quickly assess forecast quality and anomaly prevalence.

#### Acceptance Criteria

1. THE Dashboard SHALL display a MAPE metric card showing the MAPE value for the currently selected Product's forecast model. IF the MAPE value is unavailable, THE Dashboard SHALL display "N/A" in the card.
2. THE Dashboard SHALL display an RMSE metric card showing the RMSE value for the currently selected Product's forecast model. IF the RMSE value is unavailable, THE Dashboard SHALL display "N/A" in the card.
3. THE Dashboard SHALL display a Total Anomalies metric card showing the `total_anomalies` count returned by `/api/anomalies` for the currently selected Product.
4. WHEN a user selects a new Product from the dropdown, THE Dashboard SHALL immediately reset all metric cards to Skeleton_Loaders and fetch updated values for the newly selected Product.
5. IF any metric card API request fails, THEN THE Dashboard SHALL display an error indicator in the affected card identifying the failure.

---

### Requirement 11: Anomaly Table

**User Story:** As a retail analyst, I want to view a filterable table of detected anomalies, so that I can investigate specific demand spikes, price anomalies, and stockout signals.

#### Acceptance Criteria

1. THE Dashboard SHALL render a table of all anomaly records returned by `/api/anomalies` for the currently selected Product, with columns for Date, Quantity, Unit Price, Anomaly Score, Reason, and Flag (a visual indicator derived from the boolean `is_anomaly` field).
2. THE Dashboard SHALL display filter chips labeled All, Demand Spike, Price Anomaly, and Stockout Signal above the anomaly table.
3. WHEN a user selects the "All" filter chip, THE Dashboard SHALL display all anomaly rows regardless of `reason`. WHEN a user selects the "Demand Spike" chip, THE Dashboard SHALL display only rows where `reason` is `demand_spike`. WHEN a user selects the "Price Anomaly" chip, THE Dashboard SHALL display only rows where `reason` is `price_anomaly`. WHEN a user selects the "Stockout Signal" chip, THE Dashboard SHALL display only rows where `reason` is `stockout_signal`.
4. IF a row has an `anomaly_score` below −0.1 (high severity), THEN THE Dashboard SHALL highlight that row in red. IF a row has an `anomaly_score` between −0.1 and 0.0 inclusive (medium severity), THEN THE Dashboard SHALL highlight that row in amber.
5. WHEN the `anomalies` array is empty for the selected Product, THE Dashboard SHALL display a message indicating no anomalies were detected and SHALL NOT display a blank table.

---

### Requirement 12: Feature Importance Chart

**User Story:** As a retail analyst, I want to see which features drove the demand forecast, so that I can understand the model's reasoning.

#### Acceptance Criteria

1. WHEN feature importance data is loaded for the selected Product, THE Dashboard SHALL render a horizontal bar chart of feature importances returned by `/api/importance`.
2. THE Dashboard SHALL sort the bars in descending order of importance value.
3. THE Dashboard SHALL label each bar with the feature name and its importance value formatted to 3 decimal places.
4. THE Dashboard SHALL display the subtitle "What drove this forecast" above the feature importance chart.
5. WHILE feature importance data is being fetched, THE Dashboard SHALL display a Skeleton_Loader in the FeatureImportance component region.
6. IF the feature importance API request fails or returns an empty `features` array, THEN THE Dashboard SHALL display an error message in the FeatureImportance region and SHALL NOT render a blank or empty chart.

---

### Requirement 13: Deployment and Infrastructure

**User Story:** As a developer, I want the full application deployed as a single Vercel project, so that the live URL is publicly accessible without any additional infrastructure.

#### Acceptance Criteria

1. THE System SHALL be deployable as a single Vercel project containing both the React static frontend and the Python serverless API functions.
2. THE System SHALL route all requests matching `/api/*` to the Python serverless functions and all other requests to the React static build, including a SPA fallback so that unmatched non-API routes serve the React `index.html`.
3. THE System SHALL be accessible via a public Vercel URL without authentication.
4. WHEN the Python serverless functions are packaged for deployment, each individual serverless function SHALL not exceed the 50 MB Vercel per-function size limit.
5. THE System SHALL pin all Python dependencies to exact versions in `requirements.txt` to ensure reproducible builds.
6. WHEN a serverless function experiences a Cold_Start in a single isolated invocation with no concurrent cold starts, THE System SHALL complete model loading and return a valid API response within 10 seconds; the expected minimum response time due to model loading is 2 to 3 seconds, which is an acceptable lower bound.

---

### Requirement 14: UI Resilience and Loading States

**User Story:** As a retail analyst, I want the Dashboard to always show meaningful feedback during loading and on errors, so that I never encounter a blank or broken screen.

#### Acceptance Criteria

1. WHILE any API request is in flight, THE Dashboard SHALL display Skeleton_Loaders in the affected regions: ForecastChart, AnomalyTable, MetricsCards, and FeatureImportance. WHEN a retry is initiated for a failed request, THE Dashboard SHALL display Skeleton_Loaders in the affected region, replacing any stale error message.
2. IF any API request returns an error response, THEN THE Dashboard SHALL display an error message in the affected region that identifies the failed operation (e.g., "Failed to load forecast data") and instructs the user to retry.
3. THE Dashboard SHALL never display a completely blank screen under any application state, including initial load, data fetching, and error conditions; at least one visible UI element (Skeleton_Loader, error message, or prompt) SHALL be present at all times.
4. WHEN the application first loads before a Product is selected, THE Dashboard SHALL display a prompt with the text "Select a product to view demand forecasts and anomalies"; this prompt SHALL remain visible regardless of whether error messages or loading indicators are also displayed.
5. IF the `/api/products` request fails on initial load, THEN THE Dashboard SHALL display an error message in the product selector region identifying the failure and instructing the user to refresh the page, so that the user is never stuck with no way to select a product.
