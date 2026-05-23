<div align="center">
  <h1>📈 DemandSense</h1>
  <p><strong>Enterprise-Grade Retail Demand Forecasting & Anomaly Detection System</strong></p>

  ![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
  ![React](https://img.shields.io/badge/React-18-blue.svg)
  ![XGBoost](https://img.shields.io/badge/XGBoost-Forecasting-green.svg)
  ![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-brightgreen.svg)
  ![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
</div>

<br />

DemandSense is an AI-powered retail intelligence platform that predicts future sales volume and automatically detects critical business events (such as out-of-stock risks and unseasonal demand spikes). Built to solve real-world retail inventory challenges, it combines a highly responsive React frontend with a scalable Python/Flask machine learning backend.

## ✨ Key Capabilities

* **🔮 Predictive Forecasting (XGBoost):** Leverages historical sales data, seasonal trends, and lagging indicators to predict future demand across 7, 14, and 30-day horizons with dynamic confidence intervals.
* **🚨 Automated Anomaly Detection (Isolation Forest):** Unsupervised learning algorithms actively monitor data to flag anomalous sales patterns, categorizing them into high-priority "Act Now" events (stockouts) and "Keep an Eye On" events (demand spikes).
* **💻 Retail-Optimized Dashboard:** A dark-mode, high-performance UI featuring interactive visualizations (via Recharts) tailored for quick decision-making rather than data overload.
* **⚙️ Automated CI/CD:** Fully integrated GitHub Actions pipeline ensuring backend unit tests (Pytest) and frontend component tests (Jest) pass before deployment.

---

## 🏗️ System Architecture

```mermaid
graph LR
    A[React/Vite Frontend] -->|REST API| B(Flask Backend)
    B --> C[(JSON/Data Lake)]
    B --> D[ML Inference Engine]
    
    subgraph Machine Learning Pipeline
    D --> E[XGBoost Forecasting]
    D --> F[Isolation Forest]
    end
```

### 💻 Technology Stack

**Frontend (Client)**
* **Core:** React 18, Vite, Node.js
* **Styling:** TailwindCSS 
* **Visualizations:** Recharts
* **Testing:** Jest, React Testing Library

**Backend & Data Science (Server)**
* **Core:** Python 3.11, Flask, Gunicorn
* **Data Processing:** Pandas, NumPy
* **Machine Learning:** Scikit-Learn (Isolation Forest), XGBoost
* **Testing:** Pytest, Hypothesis (Property-based testing)

---

## 🚀 Getting Started Locally

DemandSense is designed to be easily reproducible on local machines.

### 1. Backend Setup

```bash
# Clone the repository
git clone https://github.com/Shy4n7/DemandSense.git
cd DemandSense

# Install Python dependencies
pip install -r requirements.txt

# Start the Flask API server
python server.py
```
*The API will be available at `http://localhost:8000`.*

### 2. Frontend Setup

Open a new terminal window:
```bash
cd frontend

# Install Node dependencies
npm install

# Start the Vite development server
npm run dev
```
*The interactive dashboard will be available at `http://localhost:5173`.*

---

## 🧠 Machine Learning Retraining

The pre-trained models are included in the repository. However, if you wish to retrain the models from scratch using the underlying data engine:

```bash
# Execute the automated feature engineering and model training pipeline
python scripts/train_forecast.py

# Execute the unsupervised anomaly detection training pipeline
python scripts/train_anomaly.py
```

*Artifacts are automatically serialized and saved to the `/models` directory.*
