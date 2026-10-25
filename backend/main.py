"""
VayuNet AI — FastAPI Backend Application
Exposes REST APIs for Delhi air-quality intelligence, XGBoost PM2.5 forecasting,
IDW spatial grid interpolation, anomaly hotspot detection, and dashboard alerts.
Supports both Benchmark Smog Episode and Live Real-Time Open-Meteo ingestion.
"""

import os
import sys
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# Ensure root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.services import service

app = FastAPI(
    title="VayuNet AI — Delhi Hyper-Local Air Intelligence API",
    description="Phase 1 Prototype combining CPCB ground sensors, Open-Meteo weather, and Sentinel-5P satellite data for PM2.5 forecasting and hotspot anomaly detection.",
    version="1.0.0"
)

# Enable CORS for local development and web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- REST ENDPOINTS -----------------

@app.get("/api/current", summary="Get Delhi current air intelligence summary")
def get_current(mode: Optional[str] = Query(None, description="'live' for real-time or 'benchmark'")):
    """Returns Delhi-wide aggregate PM2.5, PM10, NO2, active stations, hotspot count, and active alerts."""
    return JSONResponse(content=service.get_current_summary(mode=mode))

@app.get("/api/stations", summary="Get all CPCB monitoring stations")
def get_stations(mode: Optional[str] = Query(None, description="'live' for real-time or 'benchmark'")):
    """Returns real-time/latest snapshot for all monitored ground stations across Delhi."""
    stations = service.get_latest_station_data(mode=mode)
    return JSONResponse(content={"count": len(stations), "stations": stations})

@app.get("/api/grid", summary="Get Delhi hyper-local spatial pollution grid")
def get_grid(
    res: float = Query(0.035, ge=0.01, le=0.1, description="Grid resolution in degrees"),
    mode: Optional[str] = Query(None, description="'live' for real-time or 'benchmark'")
):
    """Returns IDW interpolated spatial grid over Delhi in GeoJSON and cell format."""
    grid_data = service.get_grid(resolution=res, mode=mode)
    return JSONResponse(content=grid_data)

@app.get("/api/forecast", summary="Get short-term PM2.5 multi-horizon forecasts")
def get_forecast(
    station_id: Optional[str] = Query(None, description="CPCB station ID (e.g., DL_ANAND_VIHAR) or empty for city average"),
    mode: Optional[str] = Query(None, description="'live' for real-time or 'benchmark'")
):
    """Returns multi-horizon forecasts (Current, +1h, +2h, +3h) comparing Model A and Model B with AI explanation factors."""
    forecast = service.predict_multi_horizon(station_id=station_id, mode=mode)
    return JSONResponse(content=forecast)

@app.get("/api/hotspots", summary="Get detected abnormal pollution hotspots")
def get_hotspots(mode: Optional[str] = Query(None, description="'live' for real-time or 'benchmark'")):
    """Detects locations where pollution is unusually high compared to recent history using Isolation Forest and Rolling Z-Score."""
    hotspots = service.get_hotspots(mode=mode)
    return JSONResponse(content={"count": len(hotspots), "hotspots": hotspots})

@app.get("/api/alerts", summary="Get prototype dashboard pollution alerts")
def get_alerts(mode: Optional[str] = Query(None, description="'live' for real-time or 'benchmark'")):
    """Generates prototype dashboard alerts for rapid PM2.5 surges and anomalous hotspot triggers with contributing factors."""
    alerts = service.get_alerts(mode=mode)
    return JSONResponse(content={"count": len(alerts), "alerts": alerts})

@app.get("/api/live/sync", summary="Force refresh live Open-Meteo real-time telemetry")
def sync_live():
    """Immediately fetches live observations for all 15 Delhi stations from Open-Meteo API."""
    df = service.fetch_live_telemetry()
    return JSONResponse(content={
        "status": "success",
        "mode": "live",
        "stations_synced": len(df["station_id"].unique()) if df is not None else 0,
        "timestamp": str(service.live_timestamp)
    })

@app.get("/api/model-metrics", summary="Get genuine Model A vs Model B evaluation metrics")
def get_model_metrics():
    """Returns honest, non-fabricated test split metrics (MAE, RMSE, R²) and feature importances for Model A and Model B."""
    metrics = service.get_model_metrics()
    if not metrics:
        raise HTTPException(status_code=404, detail="Model metrics not found. Run ml/evaluate.py first.")
    return JSONResponse(content=metrics)

@app.get("/api/health", summary="Health check endpoint")
def health_check():
    return {
        "status": "healthy",
        "service": "VayuNet AI",
        "phase": "1.0",
        "is_live_mode": service.is_live_mode,
        "models_loaded": {
            "model_a": service.model_a is not None,
            "model_b": service.model_b is not None
        }
    }

# ----------------- STATIC FRONTEND MOUNTING -----------------
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/style.css")
    def serve_style_css():
        return FileResponse(os.path.join(FRONTEND_DIR, "style.css"), media_type="text/css")

    @app.get("/app.js")
    def serve_app_js():
        return FileResponse(os.path.join(FRONTEND_DIR, "app.js"), media_type="application/javascript")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"), media_type="text/html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
