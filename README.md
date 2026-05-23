# DemandSense 📈

An AI-powered retail and store management dashboard designed to help retailers forecast future demand and detect unusual sales anomalies (like unexpected spikes or stockouts).

## 🚀 Key Features

* **Demand Forecasting:** Predicts future sales for the next 7, 14, or 30 days using historical data.
* **Anomaly Detection:** Automatically flags "Act Now" events (like unexpected stockouts) and "Keep an Eye On" events (like sudden demand spikes) using machine learning.
* **Retailer-Friendly UI:** A clean, dark-mode dashboard that focuses on recent activity and actionable insights rather than overwhelming the user with raw data.
* **Interactive Charts:** Smooth visualizations to compare past actual sales with future predicted sales.

## 🛠️ Tech Stack

* **Frontend:** React, Vite, TailwindCSS, Recharts
* **Backend:** Python, Flask, Pandas, NumPy
* **Machine Learning:** 
  * **XGBoost** for Demand Forecasting (predicts point estimates as well as upper/lower confidence bounds).
  * **Isolation Forest** for Anomaly Detection (identifies statistical outliers in sales volume).

## 📊 Dataset Note

This repository includes a curated dataset (`clean.json`) built specifically for a clean presentation and internship showcase. 
* Background noise and erratic price fluctuations have been smoothed out to reflect realistic inflation curves.
* Clear, undeniable anomalies (one demand spike and one stockout per key product) have been seeded in the most recent period (December 2024) to perfectly demonstrate the AI's detection capabilities without clutter.

## 💻 How to Run Locally

### 1. Clone the repository
```bash
git clone https://github.com/Shy4n7/DemandSense.git
cd DemandSense
```

### 2. Start the Backend (Python)
Ensure you have Python 3.10+ installed.
```bash
pip install -r requirements.txt
python server.py
```
The Flask API will run on `http://localhost:8000`.

### 3. Start the Frontend (Node/React)
Open a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
The dashboard will open at `http://localhost:5173`.

## 🧠 ML Training (Optional)
If you wish to retrain the models from scratch on the dataset:
```bash
# Train the XGBoost forecasting models
python scripts/train_forecast.py

# Train the Isolation Forest anomaly models
python scripts/train_anomaly.py
```
Models are saved as `.pkl` files in the `models/` directory.
