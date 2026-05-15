# PRD: DemandSense — Demand Forecasting & Anomaly Detection System

**Version:** 2.0  
**Author:** Shyan  
**Build Window:** 2–3 weeks  

---

## 1. Purpose

Build a production-deployed ML web application that forecasts retail demand and detects sales/pricing anomalies. making it immediately legible as relevant work during outreach.

The deliverable is a **live Vercel URL** backed by a real ML pipeline, not a notebook or a GitHub repo.

---

## 2. Problem Statement

Retail businesses suffer from two compounding failures:

- **Overstocking / understocking** due to poor demand visibility, leading to waste or lost sales
- **Undetected anomalies** in sales or pricing data (fraud, data entry errors, supply shocks) that go unaddressed until they cause financial damage

Traditional rule-based systems fail at both. ML-powered forecasting and anomaly detection solves them.

---

## 3. Goals

| Goal | Metric |
|------|--------|
| Accurate demand forecast | MAPE < 15% on test split |
| Anomaly detection precision | F1 > 0.75 on labeled anomalies |
| Deployed and live | Accessible via public Vercel URL |
| Fast API response | Serverless function response < 10s |
| Clean UI | Non-technical user can interpret results |

---

## 4. Scope

### In Scope
- Demand forecasting for a selected product using historical sales data
- Anomaly detection on sales volume and unit price
- FastAPI backend as Vercel serverless functions
- Interactive frontend dashboard (React)
- Full deployment on Vercel (frontend + backend, single repo)
- Public GitHub repo

### Out of Scope
- Real-time data ingestion pipelines
- User authentication / multi-tenant support
- Mobile app
- Integration with actual ERP systems
- Docker / docker-compose (not needed for Vercel)

---

## 5. Dataset

**Primary:** UCI Online Retail Dataset  
- Source: https://archive.ics.uci.edu/ml/datasets/Online+Retail  
- ~541k transactions, UK-based retailer, 2010–2011  
- Features: InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country  

**Fallback:** Kaggle Rossmann Store Sales (if richer time-series needed)

**Preprocessing steps:**
- Remove cancelled invoices (InvoiceNo starting with 'C')
- Remove rows with negative Quantity or UnitPrice
- Aggregate to daily sales per StockCode
- Engineer features: day_of_week, month, is_weekend, rolling_7d_mean, rolling_30d_mean, lag_1, lag_7, lag_14
- Subset to top 20 products by total volume (keeps deployment size small)
- Serialize cleaned data as `data/clean.json` (committed to repo)

---

## 6. ML Architecture

### 6.1 Demand Forecasting

**Approach:** XGBoost with engineered lag + calendar features

| Feature Group | Features |
|---------------|----------|
| Lag features | lag_1, lag_7, lag_14 |
| Rolling stats | rolling_7d_mean, rolling_30d_mean, rolling_7d_std |
| Calendar | day_of_week, month, is_weekend, is_month_end |

**Why XGBoost only (no Prophet):**
- UCI dataset covers only 1 year — insufficient seasonal cycles for Prophet to add value over lag features
- XGBoost + scikit-learn fits within Vercel's 50MB serverless size limit; Prophet does not (~150MB)
- Lag + calendar features capture the same patterns with more transparency and control

**Confidence intervals:** XGBoost quantile regression — train two models with `objective=reg:quantileerror`, alpha=0.1 (lower bound) and alpha=0.9 (upper bound)

**Input:** Historical daily sales for a selected product  
**Output:** Forecast for next 7 / 14 / 30 days with lower/upper confidence bounds  
**Evaluation:** MAPE, RMSE on 20% holdout test set  

### 6.2 Anomaly Detection

**Approach:** Isolation Forest + Rolling Z-score

| Method | Use Case |
|--------|----------|
| Isolation Forest | Multivariate anomalies across quantity + price features |
| Rolling Z-score | Fast univariate spike detection on daily sales |

**Flagged anomaly types:**
- Demand spike (> 3σ above rolling 30d mean)
- Abnormal unit price (> 2.5σ from product median)
- Zero-sales streak (3+ consecutive days — potential stockout signal)

**Output:** Anomaly score per row + binary flag + reason label

### 6.3 Explainability

- XGBoost native `feature_importances_` exposed via `/api/importance` endpoint
- Rendered as horizontal bar chart in UI
- Shows which lag/calendar features drove the forecast
- Signals ML depth to Pirai's AI/ML Lead

---

## 7. System Architecture

```
┌──────────────────────────────────────────────────┐
│              Vercel (Single Deployment)           │
│                                                   │
│  ┌───────────────────────────────────────────┐   │
│  │           React Frontend                   │   │
│  │  (Vercel Static Site — /frontend/build)   │   │
│  └─────────────────┬─────────────────────────┘   │
│                    │ fetch()                      │
│  ┌─────────────────▼─────────────────────────┐   │
│  │     Vercel Python Serverless Functions     │   │
│  │         (/api/ directory)                  │   │
│  │                                            │   │
│  │  /api/forecast.py   → forecast JSON       │   │
│  │  /api/anomalies.py  → flagged rows        │   │
│  │  /api/products.py   → product list        │   │
│  │  /api/importance.py → feature importance  │   │
│  └─────────────────┬─────────────────────────┘   │
│                    │                              │
│  ┌─────────────────▼─────────────────────────┐   │
│  │           ML + Data Layer                  │   │
│  │      (loaded at cold start)                │   │
│  │                                            │   │
│  │  lib/preprocess.py                         │   │
│  │  lib/predict_forecast.py                   │   │
│  │  lib/predict_anomaly.py                    │   │
│  │  models/xgb_{product_id}.pkl               │   │
│  │  models/xgb_lower_{product_id}.pkl         │   │
│  │  models/xgb_upper_{product_id}.pkl         │   │
│  │  models/iso_{product_id}.pkl               │   │
│  │  data/clean.json                           │   │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

**Key constraints:**
- Vercel serverless timeout: **10 seconds** — models must load and infer within this window
- Vercel function size limit: **50MB** — XGBoost + scikit-learn + pandas + numpy fits at ~45MB
- Models pre-trained locally, committed to repo as `.pkl` files (~500KB each)

---

## 8. File Structure

```
retailpulse/
├── api/                               # Vercel serverless functions (Python)
│   ├── forecast.py                    # POST /api/forecast
│   ├── anomalies.py                   # POST /api/anomalies
│   ├── products.py                    # GET /api/products
│   └── importance.py                  # GET /api/importance?product_id=
├── lib/                               # Shared ML logic (imported by api/)
│   ├── preprocess.py                  # Feature engineering utilities
│   ├── predict_forecast.py            # Load XGBoost, run inference
│   └── predict_anomaly.py             # Load Isolation Forest, score rows
├── models/                            # Pre-trained serialized models
│   ├── xgb_85123A.pkl                 # Point forecast model
│   ├── xgb_lower_85123A.pkl           # Lower bound (q=0.1)
│   ├── xgb_upper_85123A.pkl           # Upper bound (q=0.9)
│   ├── iso_85123A.pkl                 # Isolation Forest
│   └── ...                            # One set per top-20 product
├── data/
│   └── clean.json                     # Preprocessed dataset (top 20 products)
├── scripts/                           # Run locally only — never deployed
│   ├── train_forecast.py              # Trains + serializes XGBoost models
│   ├── train_anomaly.py               # Trains + serializes Isolation Forest
│   └── evaluate.py                    # Prints MAPE, RMSE, F1 per product
├── frontend/                          # React app
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── ForecastChart.jsx      # Recharts line + area chart
│   │   │   ├── AnomalyTable.jsx       # Flagged rows with filter chips
│   │   │   ├── MetricsCards.jsx       # MAPE, RMSE, anomaly count
│   │   │   ├── FeatureImportance.jsx  # Horizontal bar chart
│   │   │   └── ProductSelector.jsx    # Searchable dropdown
│   │   └── api/
│   │       └── client.js              # fetch() wrappers
│   ├── public/
│   └── package.json
├── requirements.txt                   # Lean — must stay under 50MB
├── vercel.json                        # Routing + build config
└── README.md
```

---

## 9. Vercel Configuration

**vercel.json:**
```json
{
  "builds": [
    { "src": "api/*.py", "use": "@vercel/python" },
    {
      "src": "frontend/package.json",
      "use": "@vercel/static-build",
      "config": { "distDir": "build" }
    }
  ],
  "routes": [
    { "src": "/api/(.*)", "dest": "/api/$1" },
    { "src": "/(.*)", "dest": "/frontend/$1" }
  ]
}
```

**requirements.txt** (pin versions — size matters):
```
xgboost==2.0.3
scikit-learn==1.4.0
pandas==2.1.4
numpy==1.26.3
joblib==1.3.2
```

---

## 10. API Contract

### POST /api/forecast
```json
Request:
{ "product_id": "85123A", "horizon_days": 14 }

Response:
{
  "product_id": "85123A",
  "forecast": [
    { "date": "2011-12-10", "predicted": 142.3, "lower": 118.0, "upper": 166.6 },
    { "date": "2011-12-11", "predicted": 138.7, "lower": 114.2, "upper": 163.1 }
  ],
  "metrics": { "mape": 11.4, "rmse": 23.1 }
}
```

### POST /api/anomalies
```json
Request:
{ "product_id": "85123A" }

Response:
{
  "product_id": "85123A",
  "anomalies": [
    {
      "date": "2011-09-14",
      "quantity": 2400,
      "unit_price": 1.25,
      "anomaly_score": -0.312,
      "is_anomaly": true,
      "reason": "demand_spike"
    }
  ],
  "total_anomalies": 3
}
```

### GET /api/importance?product_id=85123A
```json
Response:
{
  "product_id": "85123A",
  "features": [
    { "name": "lag_7",           "importance": 0.312 },
    { "name": "rolling_7d_mean", "importance": 0.287 },
    { "name": "lag_1",           "importance": 0.201 },
    { "name": "day_of_week",     "importance": 0.098 },
    { "name": "month",           "importance": 0.067 },
    { "name": "is_weekend",      "importance": 0.035 }
  ]
}
```

---

## 11. Frontend UI Screens

### Screen 1: Dashboard Home
- Header: "DemandSense — Demand Intelligence"
- Searchable product dropdown (top 20 products by volume)
- Forecast horizon toggle: 7d / 14d / 30d
- Metrics cards: MAPE | RMSE | Total Anomalies Detected

### Screen 2: Forecast View
- Recharts ComposedChart: AreaChart (confidence band) + LineChart (historical solid, forecast dashed)
- X-axis: dates | Y-axis: daily units sold
- Hover tooltip: date + actual/predicted + confidence range

### Screen 3: Anomaly View
- Table: Date | Quantity | Unit Price | Anomaly Score | Reason | Flag
- Filter chips: All | Demand Spike | Price Anomaly | Stockout Signal
- Anomalous rows highlighted red (high score) / amber (medium)

### Screen 4: Feature Importance
- Recharts horizontal BarChart, sorted descending
- Each bar labeled with feature name + importance value
- Subtitle: "What drove this forecast"

---

## 12. Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Recharts + Tailwind CSS |
| Backend | Vercel Python Serverless Functions |
| Forecasting | XGBoost 2.0 (point + quantile regression) |
| Anomaly Detection | scikit-learn Isolation Forest + rolling Z-score |
| Explainability | XGBoost native feature_importances_ |
| Serialization | joblib |
| Deployment | Vercel — single repo, frontend static + backend serverless |
| Version Control | GitHub (public repo) |

---

## 13. Build Plan (3 Weeks)

### Week 1 — Data + ML Core (local only)
| Day | Task |
|-----|------|
| 1 | Download UCI dataset, EDA in Jupyter — understand distributions, missing data |
| 2 | Write preprocess.py — clean, aggregate to daily, engineer all features, export clean.json |
| 3 | Write train_forecast.py — XGBoost point forecast, tune with cross-validation |
| 4 | Add quantile regression (lower/upper models), evaluate MAPE/RMSE per product |
| 5 | Write train_anomaly.py — Isolation Forest, tune contamination param |
| 6 | Write evaluate.py — inject synthetic anomalies, compute F1, print results table |
| 7 | Serialize all models to models/ with joblib, verify file sizes stay under budget |

### Week 2 — Backend + Frontend
| Day | Task |
|-----|------|
| 8  | Set up Vercel project, write vercel.json, test Python function locally with `vercel dev` |
| 9  | Write api/forecast.py — load model, generate forecast, return JSON |
| 10 | Write api/anomalies.py + api/importance.py |
| 11 | Scaffold React app, wire up ProductSelector + MetricsCards |
| 12 | Build ForecastChart — ComposedChart with confidence band |
| 13 | Build AnomalyTable with filter chips + FeatureImportance bar chart |
| 14 | Connect all components to API via fetch(), full end-to-end test locally |

### Week 3 — Deploy + Polish
| Day | Task |
|-----|------|
| 15 | Push to GitHub, connect to Vercel, first live deployment |
| 16 | Debug deployment issues (size, imports, cold start) |
| 17 | Test all 4 API endpoints on live URL across all 20 products |
| 18 | Add skeleton loaders + error states + empty states to all UI components |
| 19 | Write README — live link at top, architecture diagram, metrics table, screenshot |
| 20 | Final evaluate.py run, update README metrics with real numbers |
| 21 | Optional: 60-second Loom recording of live demo |

---

## 14. README Must-Haves

HR will forward this to the AI/ML Lead. Structure it for a technical reader.

```markdown
# DemandSense

> **Live demo:** https://demandsense.vercel.app

Demand forecasting and anomaly detection for retail data.
XGBoost (quantile regression) + Isolation Forest, deployed on Vercel.

## Model Performance
| Product | MAPE  | RMSE | Anomalies |
|---------|-------|------|-----------|
| 85123A  | 11.4% | 23.1 | 3         |

## Architecture
[diagram]

## Stack
Python · XGBoost · scikit-learn · React · Vercel

## Run Locally
pip install -r requirements.txt
vercel dev
```

---



## 15. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Vercel 10s timeout on cold start | Load models at module level (cached across warm invocations); keep inference lightweight |
| 50MB function size exceeded | Pin exact versions; if still over, drop pandas and use numpy-only data loading |
| XGBoost .pkl files bloat repo | Cap at top 20 products; each model ~500KB; total ~40MB across all models |
| UCI dataset quality issues | Aggressive preprocessing; document every cleaning decision in scripts/ |
| No ground truth anomaly labels | Inject synthetic anomalies (5 random rows × 10x quantity) for F1 evaluation |
| Cold start visible delay to reviewer | Add skeleton loaders + "Fetching forecast..." status in UI — never show a blank screen |
