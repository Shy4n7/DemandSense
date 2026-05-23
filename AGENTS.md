# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Deployment Architecture (Non-Obvious)

- **Docker/Self-hosted (Oracle Cloud)**: Uses `server.py` which merges all `api/*.py` Flask apps into single app
- When modifying API handlers, ensure the Flask routes are compatible with `server.py`'s combined routing scheme.

## Critical Path Setup Pattern

Every `api/*.py` and `lib/*.py` file MUST include this path setup before imports:
```python
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
```
Without this, imports fail in serverless/Docker environments.

## Module-Level Data Caching

All API handlers use module-level variables for data caching:
- `_data_cache: list | None = None` - cached clean.json records
- `_load_error: str | None = None` - cached load error message
- Pattern prevents re-reading data/clean.json on every request

## Model File Naming Convention

Three XGBoost models per product (not one):
- `models/xgb_{product_id}.pkl` - point forecast
- `models/xgb_lower_{product_id}.pkl` - lower bound (alpha=0.1)
- `models/xgb_upper_{product_id}.pkl` - upper bound (alpha=0.9)
- Isolation Forest: `models/iso_{product_id}.pkl`

## Feature Order is Critical

XGBoost models require exact 11-feature order (defined in `lib/predict_forecast.py:FEATURE_COLS`):
```python
["lag_1", "lag_7", "lag_14", "rolling_7d_mean", "rolling_30d_mean", 
 "rolling_7d_std", "day_of_week", "month", "is_weekend", "is_month_end", "is_festival"]
```
Changing order breaks all trained models.

## Testing Requirements

- Run tests from project root: `pytest` (not `cd tests && pytest`)
- Frontend tests: `cd frontend && npm test`
- Tests use pytest + hypothesis for property-based testing
- All tests mock model loading (no real .pkl files needed)

## Frontend Build Output

Vite builds to `build/` directory (not standard `dist/`):
- Configured in `frontend/vite.config.js`: `outDir: 'build'`
- Docker copies from `frontend/build`
- Don't change this without updating Dockerfile

## Minimum Training Data

Products need 60+ days of history for training (not 30):
- Defined in `scripts/train_forecast.py:MIN_DAYS_FOR_TRAINING = 60`
- Products with <60 days are skipped with logged warning
- This is higher than typical ML projects due to lag features

## Commands

**Backend (from project root):**
- Run server: `python server.py` (dev) or `gunicorn server:app --bind 0.0.0.0:8000`
- Run tests: `pytest`
- Train models: `python scripts/train_forecast.py` and `python scripts/train_anomaly.py`

**Frontend (from frontend/):**
- Dev server: `npm run dev`
- Build: `npm run build`
- Test: `npm test`