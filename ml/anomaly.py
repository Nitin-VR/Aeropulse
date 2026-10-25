"""
VayuNet AI — Hotspot & Anomaly Detection Module
Uses Isolation Forest and Station-wise Rolling Z-scores to detect statistically anomalous
pollution surges. Extracts honest contributing signals (wind stagnation, recent PM2.5 delta,
elevated NO2, satellite column concentration) to explain the anomaly without claiming source attribution.
"""

import os
import joblib
import numpy as np
import pandas as pd
from typing import List, Dict, Any
from sklearn.ensemble import IsolationForest

MODEL_SAVE_PATH = "models/isolation_forest.pkl"

def train_anomaly_detector(df: pd.DataFrame, contamination: float = 0.05) -> IsolationForest:
    """
    Fits an Isolation Forest on multi-variate pollution and rate-of-change signals.
    """
    os.makedirs("models", exist_ok=True)
    df_features = df.copy()
    
    # Delta from 3h rolling mean
    if "PM2.5_roll_mean_3h" in df_features.columns:
        df_features["pm25_diff_3h"] = df_features["PM2.5"] - df_features["PM2.5_roll_mean_3h"]
    else:
        df_features["pm25_diff_3h"] = 0.0
        
    cols = ["PM2.5", "PM10", "NO2", "pm25_diff_3h"]
    X = df_features[cols].fillna(0.0)
    
    iso = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=42
    )
    iso.fit(X)
    
    joblib.dump(iso, MODEL_SAVE_PATH)
    return iso

def detect_hotspots(
    current_df: pd.DataFrame, 
    iso_model: IsolationForest = None,
    z_threshold: float = 2.0
) -> List[Dict[str, Any]]:
    """
    Evaluates current station readings for anomalous pollution hotspots.
    Combines Isolation Forest decision function with rolling Z-score.
    """
    if current_df.empty:
        return []
        
    if iso_model is None and os.path.exists(MODEL_SAVE_PATH):
        try:
            iso_model = joblib.load(MODEL_SAVE_PATH)
        except Exception:
            iso_model = None

    hotspots = []
    
    for _, row in current_df.iterrows():
        pm25 = float(row.get("PM2.5", 0.0))
        pm10 = float(row.get("PM10", 0.0))
        no2 = float(row.get("NO2", 0.0))
        ws = float(row.get("wind_speed", 2.0))
        sat_no2 = float(row.get("satellite_no2", 0.0))
        pm25_lag1 = float(row.get("PM2.5_lag1", pm25))
        pm25_roll_mean = float(row.get("PM2.5_roll_mean_3h", pm25))
        pm25_roll_std = max(1.0, float(row.get("PM2.5_roll_std_3h", 10.0)))
        
        # 1. Rolling Z-Score calculation
        z_score = (pm25 - pm25_roll_mean) / pm25_roll_std
        
        # 2. Isolation Forest score
        iso_score = 0.0
        is_iso_anomaly = False
        if iso_model is not None:
            pm25_diff = pm25 - pm25_roll_mean
            sample_df = pd.DataFrame([[pm25, pm10, no2, pm25_diff]], columns=["PM2.5", "PM10", "NO2", "pm25_diff_3h"])
            pred = iso_model.predict(sample_df)[0]
            raw_score = iso_model.decision_function(sample_df)[0]
            iso_score = round(float(np.clip((0.15 - raw_score) * 5.0, 0.0, 1.0)), 3)
            is_iso_anomaly = (pred == -1)
        else:
            # Fallback normalized score from z-score
            iso_score = round(float(np.clip(max(0.0, z_score) / 4.0, 0.0, 1.0)), 3)
            is_iso_anomaly = (z_score >= z_threshold)

        # Flag as hotspot if either Z-score is elevated, Isolation Forest flags it, or PM2.5 is high relative to baseline
        is_elevated_pm = (pm25 >= 95.0 and z_score >= 0.5) or pm25 >= 140.0
        if (z_score >= z_threshold or is_iso_anomaly or is_elevated_pm):
            contributing_signals = []
            
            # Ground truth factor analysis
            delta_pm = pm25 - pm25_lag1
            if delta_pm > 15:
                contributing_signals.append(f"Rapid recent PM2.5 surge (+{delta_pm:.1f} µg/m³ in past hour)")
            elif pm25 > 250:
                contributing_signals.append(f"Severe persistent PM2.5 concentration ({pm25:.1f} µg/m³)")
                
            if ws < 1.8:
                contributing_signals.append(f"Calm/stagnant surface wind ({ws:.1f} m/s) trapping pollutants")
            elif ws < 3.0:
                contributing_signals.append(f"Subdued wind speed ({ws:.1f} m/s)")
                
            if no2 > 65.0:
                contributing_signals.append(f"Elevated local combustion precursor NO2 ({no2:.1f} µg/m³)")
                
            if sat_no2 > 1.2e-4:
                contributing_signals.append(f"High tropospheric NO2 column density observed by Sentinel-5P ({sat_no2:.2e} mol/m²)")
            elif sat_no2 > 0:
                contributing_signals.append(f"Satellite Sentinel-5P column reading: {sat_no2:.2e} mol/m²")
                
            if not contributing_signals:
                contributing_signals.append(f"Multi-pollutant concentration above baseline (Z-score: {z_score:.2f})")

            hotspot_record = {
                "station_id": str(row.get("station_id", "")),
                "station_name": str(row.get("station_name", "Delhi Region")),
                "latitude": float(row.get("latitude", 28.6)),
                "longitude": float(row.get("longitude", 77.2)),
                "PM2.5": pm25,
                "PM10": pm10,
                "NO2": no2,
                "anomaly_score": max(iso_score, round(min(1.0, z_score / 3.5), 2)),
                "z_score": round(float(z_score), 2),
                "detection_time": str(row.get("timestamp", "")),
                "status_message": "Anomalous pollution hotspot detected.",
                "contributing_signals": contributing_signals
            }
            hotspots.append(hotspot_record)
            
    # Sort hotspots by severity / anomaly score descending
    hotspots.sort(key=lambda h: (h["anomaly_score"], h["PM2.5"]), reverse=True)
    return hotspots

def generate_alerts(
    current_df: pd.DataFrame, 
    forecasts: Dict[str, float] = None,
    hotspots: List[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Generates actionable prototype pollution alerts for the web dashboard.
    """
    alerts = []
    
    if hotspots:
        for h in hotspots[:4]: # top critical hotspots
            st_id = h["station_id"]
            predicted_pm = forecasts.get(st_id, h["PM2.5"] * 1.05) if forecasts else h["PM2.5"] * 1.05
            
            alert = {
                "id": f"ALT_{st_id}_{h['detection_time'][-5:].replace(':', '') if h['detection_time'] else '01'}",
                "location": f"{h['station_name']} (Delhi)",
                "station_id": st_id,
                "event": "Anomalous pollution hotspot & rapid rise detected",
                "severity": "CRITICAL" if h["PM2.5"] > 250 else "HIGH",
                "current_pm25": h["PM2.5"],
                "predicted_pm25": round(float(predicted_pm), 1),
                "timestamp": h["detection_time"],
                "contributing_signals": h["contributing_signals"],
                "disclaimer": "Prototype dashboard alert for intelligence visualization — not an official statutory warning."
            }
            alerts.append(alert)
            
    return alerts
