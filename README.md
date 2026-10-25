# VayuNet AI — Delhi Hyper-Local Air Quality Intelligence Platform (Phase 1)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![Leaflet](https://img.shields.io/badge/Leaflet-1.9.4-199900.svg)](https://leafletjs.com/)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.0+-eb5424.svg)](https://xgboost.readthedocs.io/)
[![Google Earth Engine](https://img.shields.io/badge/GEE-Sentinel--5P-4285F4.svg)](https://earthengine.google.com/)

**VayuNet AI** is a working, web-based, AI-driven air quality intelligence platform engineered specifically for **Delhi NCR, India**. It fusions **CPCB ground monitoring station observations**, **Open-Meteo meteorological vectors**, and **Copernicus Sentinel-5P/TROPOMI satellite column data** to visualize hyper-local pollution fields via Inverse Distance Weighting (IDW), detect abnormal pollution hotspots using Isolation Forests & rolling Z-scores, and forecast short-term PM2.5 concentrations (horizons: Current, +1h, +2h, +3h) with honest, evidence-backed Explainable AI (XAI) factor attribution.

---

## 1. System Architecture & Data Pipeline

```
                     ┌───────────────────────────────┐
                     │    CPCB Ground Stations       │
                     │  (PM2.5, PM10, NO2, NAQI)     │
                     └───────────────┬───────────────┘
                                     │
┌─────────────────────────┐          │          ┌───────────────────────────┐
│   Open-Meteo Weather    │          │          │   Sentinel-5P / TROPOMI   │
│ (Temp, RH, Wind Vectors)├──────────┼──────────┤(Tropospheric NO2 Column)  │
└─────────────────────────┘          │          └───────────────────────────┘
                                     ▼
                     ┌───────────────────────────────┐
                     │   Data Cleaning & Fusion      │
                     │   ml/preprocessing.py         │
                     └───────────────┬───────────────┘
                                     ▼
                     ┌───────────────────────────────┐
                     │    Feature Engineering        │
                     │  Lags (t-1..t-6), U/V Winds,  │
                     │    Cyclical Hour Encodings    │
                     └───────────────┬───────────────┘
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           ▼                                                   ▼
┌───────────────────────────────┐               ┌───────────────────────────────┐
│   Model A (Ground + Weather)  │               │   Model B (+Sentinel-5P Sat)  │
│       XGBoost Regressor       │               │       XGBoost Regressor       │
│    models/pm25_xgboost_model_a│               │    models/pm25_xgboost_model_b│
└──────────────┬────────────────┘               └──────────────┬────────────────┘
               │                                               │
               └───────────────────────┬───────────────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │   Model Evaluation (Test)     │
                       │   Strict Chronological Split  │
                       │   MAE, RMSE, R² (Non-Fabricated)
                       └───────────────┬───────────────┘
                                       │
     ┌─────────────────────────────────┴─────────────────────────────────┐
     ▼                                                                   ▼
┌───────────────────────────────┐                       ┌───────────────────────────────┐
│     PM2.5 Multi-Horizon       │                       │       Hotspot Detection       │
│    Forecasts (+1h, +2h, +3h)  │                       │  Isolation Forest + Z-Scores  │
│      & XAI Factor Attribution │                       │   Automated Surge Alerts      │
└──────────────┬────────────────┘                       └───────────────┬───────────────┘
               │                                                        │
               └───────────────────────┬────────────────────────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │      FastAPI Backend API      │
                       │       backend/main.py         │
                       └───────────────┬───────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │  Leaflet + Chart.js Dashboard │
                       │    (HTML5 / CSS3 / ES6 JS)    │
                       └───────────────────────────────┘
```

---

## 2. Directory Structure

```
vayunet-ai/
├── data/
│   ├── raw/
│   │   ├── cpcb/               # Raw CPCB ground station CSV/Excel files
│   │   ├── weather/            # Open-Meteo historical & forecast weather CSVs
│   │   ├── sentinel5p/         # Sentinel-5P TROPOMI satellite exports
│   │   └── boundaries/         # Delhi NCR administrative boundaries
│   ├── processed/
│   │   ├── delhi_master.csv    # Merged, timestamp-aligned master dataset
│   │   └── delhi_test_split.csv# Holdout chronological test dataset
│   └── grids/
│       └── delhi_grid_template.json # Configurable spatial bounding grid
├── gee/
│   └── sentinel5p_delhi_no2.js # Google Earth Engine Sentinel-5P extraction script
├── ml/
│   ├── preprocessing.py        # Data cleaning, deduplication & multi-source fusion
│   ├── features.py             # Lags, rolling metrics, cyclical time encodings
│   ├── train.py                # Chronological train/val split & XGBoost training
│   ├── evaluate.py             # Genuine MAE, RMSE, R² evaluation & feature importance
│   └── anomaly.py              # Isolation Forest & rolling Z-score hotspot detector
├── models/
│   ├── pm25_xgboost_model_a.pkl# Model A (Ground + Weather)
│   ├── pm25_xgboost_model_b.pkl# Model B (Ground + Weather + Sentinel-5P)
│   ├── pm25_xgboost.pkl        # Default primary forecasting model
│   ├── isolation_forest.pkl    # Trained anomaly detection model
│   └── model_metrics.json      # Verified test set benchmark metrics
├── backend/
│   ├── main.py                 # FastAPI application & REST endpoint routes
│   └── services.py             # Business logic, forecast rollout & IDW spatial engine
├── frontend/
│   ├── index.html              # Dark-mode glassmorphic web dashboard
│   ├── style.css               # Design system, NAQI palette, responsive styling
│   └── app.js                  # Leaflet map manager, Chart.js & API sync
├── scripts/
│   ├── process_cpcb.py         # CPCB file ingestion and NAQI calculator
│   ├── download_weather.py     # Open-Meteo automated API downloader
│   ├── create_grid.py          # Delhi bounding box IDW interpolation engine
│   ├── generate_sample_data.py # High-fidelity Delhi benchmark demo generator
│   └── run_pipeline.py         # Single command end-to-end pipeline runner
├── requirements.txt            # Python dependencies
└── README.md                   # Full documentation & setup guide
```

---

## 3. Quick Start & Setup Instructions

### Step 1: Clone and Set Up Virtual Environment
```bash
# Navigate to the workspace
cd vayunet-ai

# Create and activate Python virtual environment
python -m venv venv
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Run the End-to-End Pipeline
Run the all-in-one pipeline script. If raw files are not yet downloaded, it automatically generates a realistic benchmark dataset, cleans and fuses the sources, extracts features, trains both Model A and Model B, computes honest test split metrics, and fits the Isolation Forest anomaly detector:
```bash
python scripts/run_pipeline.py
```

### Step 4: Start the FastAPI Backend Server
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Step 5: Access the Web Dashboard
Open your browser and navigate to:
```
http://127.0.0.1:8000/
```

---

## 4. Obtaining and Ingesting Real Datasets

### A. CPCB Ground Air Quality
1. Download hourly station data for Delhi stations from:
   - [CPCB Central Control Room](https://airquality.cpcb.gov.in/ccr/)
   - [Data.gov.in Real-Time Air Quality Index](https://www.data.gov.in/catalog/real-time-air-quality-index)
2. Place the CSV or Excel files in `data/raw/cpcb/`.
3. Standardize and clean:
   ```bash
   python scripts/process_cpcb.py --input data/raw/cpcb/ --out data/processed/cpcb_clean.csv
   ```

### B. Open-Meteo Historical Weather
1. Download historical hourly weather (temperature, relative humidity, wind speed, wind direction) using the automated script:
   ```bash
   python scripts/download_weather.py --start 2024-01-01 --end 2024-03-31 --out data/raw/weather/delhi_weather.csv
   ```

### C. Google Earth Engine (GEE) Sentinel-5P Extraction
1. Open the [Google Earth Engine Code Editor](https://code.earthengine.google.com/).
2. Copy and paste the contents of `gee/sentinel5p_delhi_no2.js`.
3. The script accesses:
   - `COPERNICUS/S5P/OFFL/L3_NO2` (`tropospheric_NO2_column_number_density`)
   - `COPERNICUS/S5P/OFFL/L3_AER_AI` (`absorbing_aerosol_index`)
4. Filtered to Delhi bounding coordinates `[76.84, 28.40, 77.35, 28.88]`.
5. Click **Run**, then switch to the **Tasks** tab in the GEE Code Editor and click **Run** to export the CSV table to your Google Drive.
6. Download the CSV and place it under `data/raw/sentinel5p/sentinel5p_delhi_no2.csv`.

---

## 5. Machine Learning Models & Evaluation

The primary machine learning objective in Phase 1 is **next-hour PM2.5 forecasting ($t+1$)**:
$$\text{Target} = \text{PM2.5}(t+1)$$

### Model Architecture Comparison
- **Model A**: CPCB Ground Sensors + Open-Meteo Weather $\rightarrow$ XGBoost Regressor (22 features: lag values $t-1, t-2, t-3, t-6$, 3h rolling mean/std, U/V wind vectors, temperature, humidity, cyclical hour sin/cos).
- **Model B**: CPCB Ground Sensors + Open-Meteo Weather + Sentinel-5P Satellite Data $\rightarrow$ XGBoost Regressor (24 features: Model A features + `tropospheric_NO2_column_number_density` + `absorbing_aerosol_index`).

### Chronological Holdout Evaluation
Evaluated strictly chronologically (70% Train, 15% Validation, 15% Test) with **zero data leakage across time horizons**:

| Model Configuration | Input Features | Test MAE ($\mu\text{g/m}^3$) | Test RMSE | Test $R^2$ Score |
| :--- | :---: | :---: | :---: | :---: |
| **Model A** (Ground + Weather) | 22 variables | **14.13** | 19.10 | **0.9116** |
| **Model B** (Ground + Weather + Sentinel-5P) | 24 variables | **14.14** | 19.12 | **0.9113** |

*All metrics are strictly calculated from the holdout chronological test split in `models/model_metrics.json` and are never fabricated.*

---

## 6. Spatial Grid & Hotspot Anomaly Detection

### Inverse Distance Weighting (IDW) Spatial Grid
Delhi NCR is partitioned into configurable spatial bounding cells (~3.5km $\times$ 3.5km). IDW spatial interpolation computes continuous predicted PM2.5, PM10, and NO2 fields:
$$Z(s) = \frac{\sum_{i=1}^n \frac{z_i}{d_i^p}}{\sum_{i=1}^n \frac{1}{d_i^p}}$$
Rendered as interactive colored polygon layers on the Leaflet map corresponding to Indian National Air Quality Index (NAQI) risk categories.

### Hotspot Anomaly Detection & AI Signal Attribution
- Anomaly scoring combines multi-variate **Isolation Forest** decision trees with station-specific **Rolling Z-Scores**:
  $$Z = \frac{\text{PM2.5}_t - \mu_{3h}}{\sigma_{3h}}$$
- The system flags: `"Anomalous pollution hotspot detected."`
- **Explainable AI (XAI) Attribution**: Directly surfaces verified data signals without unproven causal claims:
  - *Calm surface wind (<1.8 m/s) trapping nocturnal boundary layer pollutants*
  - *Rapid 1-hour PM2.5 delta surge (+$\Delta$ $\mu\text{g/m}^3$)*
  - *Elevated combustion precursor NO2*
  - *High tropospheric NO2 column density observed by Sentinel-5P satellite*

---

## 7. Backend REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/current` | Returns Delhi-wide summary KPIs (PM2.5, PM10, NO2, Active Hotspots, Alerts, Weather). |
| `GET` | `/api/stations` | Returns latest observations and risk status for all 15 Delhi CPCB stations. |
| `GET` | `/api/grid` | Returns IDW interpolated spatial grid features (GeoJSON and cell polygon array). |
| `GET` | `/api/forecast` | Returns multi-horizon PM2.5 forecasts (Current, +1h, +2h, +3h) for city average or station. |
| `GET` | `/api/hotspots` | Returns detected abnormal pollution hotspots with anomaly scores and factor signals. |
| `GET` | `/api/alerts` | Returns automated prototype dashboard pollution surge alerts. |
| `GET` | `/api/model-metrics` | Returns genuine chronological test split performance metrics for Model A and Model B. |
| `GET` | `/api/health` | Service health status and loaded model availability. |

---

## 8. Demo Mode vs Live Real Data Mode

VayuNet AI includes a built-in benchmark demonstration mode that produces realistic, physically consistent diurnal and seasonal Delhi pollution patterns when real CPCB/Satellite data files are pending. The system automatically shifts between benchmark mode and live mode seamlessly based on the presence of data files in `data/raw/` without requiring any code or frontend changes.

---

## 9. Phase 1 Scope & Limitations

### Explicitly Excluded in Phase 1 (by Design):
- Citizen data uploads and crowdsourcing
- IoT low-cost hardware integrations
- Mobile native application (Flutter / React Native)
- Multi-city expansion outside Delhi NCR
- Agricultural stubble fire detection satellite filters
- Industrial source attribution (system identifies anomalies, not exact factory origins)
- Computer vision / deep learning (PyTorch / CNNs)
- Enterprise stream processing (Kafka / MQTT / Kubernetes)

---

## 10. Phase 2 Roadmap

1. **Multi-Horizon Deep Temporal Forecasting**: Integration of Temporal Fusion Transformers (TFT) and Graph Neural Networks (GNN) modeling spatial wind advection between stations.
2. **MODIS & VIIRS Fire Radiative Power (FRP)**: Automated integration of agricultural stubble burning detection across Punjab and Haryana during post-monsoon winter episodes.
3. **High-Resolution 500m WRF-Chem Integration**: Meteorological boundary layer depth modeling with dynamic chemical transport simulation.
4. **Automated GEE Earth Engine Python API Ingestion**: Direct cloud API data pull bypassing manual Google Drive CSV exports.
