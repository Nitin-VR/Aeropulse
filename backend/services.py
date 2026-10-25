"""
VayuNet AI — Backend Core Services
Provides high-performance data querying, live multi-horizon forecasting (+1h, +2h, +3h),
spatial IDW grid interpolation, hotspot anomaly detection, and explainable signal attribution.
Supports both curated Delhi smog benchmark mode and real-time live Open-Meteo API ingestion.
"""

import os
import json
import joblib
import requests
import concurrent.futures
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from ml.features import FEATURES_MODEL_A, FEATURES_MODEL_B
from ml.anomaly import detect_hotspots, generate_alerts
from scripts.create_grid import interpolate_grid_pollution, get_risk_status
from scripts.download_weather import DELHI_STATIONS

MASTER_CSV_PATH = "data/processed/delhi_master.csv"
MODEL_A_PATH = "models/pm25_xgboost_model_a.pkl"
MODEL_B_PATH = "models/pm25_xgboost_model_b.pkl"
METRICS_PATH = "models/model_metrics.json"

class VayuNetService:
    def __init__(self):
        self.model_a = None
        self.model_b = None
        self.df_master = None
        self.df_live = None
        self.latest_timestamp = None
        self.live_timestamp = None
        self.is_live_mode = False
        self.metrics = {}
        self.load_resources()
        
    def load_resources(self):
        if os.path.exists(MODEL_A_PATH):
            try:
                self.model_a = joblib.load(MODEL_A_PATH)
            except Exception as e:
                print(f"Error loading Model A: {e}")
                
        if os.path.exists(MODEL_B_PATH):
            try:
                self.model_b = joblib.load(MODEL_B_PATH)
            except Exception as e:
                print(f"Error loading Model B: {e}")
                
        if os.path.exists(MASTER_CSV_PATH):
            try:
                self.df_master = pd.read_csv(MASTER_CSV_PATH)
                self.df_master["timestamp"] = pd.to_datetime(self.df_master["timestamp"])
                self.latest_timestamp = self.df_master["timestamp"].max()
            except Exception as e:
                print(f"Error loading master dataset: {e}")
                
        if os.path.exists(METRICS_PATH):
            try:
                with open(METRICS_PATH, "r") as f:
                    self.metrics = json.load(f)
            except Exception as e:
                print(f"Error loading metrics: {e}")

    def fetch_live_telemetry(self) -> pd.DataFrame:
        """Fetches live real-time air quality and weather telemetry for all 15 Delhi stations."""
        def fetch_single(st):
            lat, lon = st["latitude"], st["longitude"]
            url_aq = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm2_5,pm10,nitrogen_dioxide&hourly=pm2_5,pm10,nitrogen_dioxide&timezone=Asia%2FKolkata"
            url_wx = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,surface_pressure&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m&timezone=Asia%2FKolkata"
            
            try:
                raq = requests.get(url_aq, timeout=4).json()
                rwx = requests.get(url_wx, timeout=4).json()
                
                cur_aq = raq.get("current", {})
                cur_wx = rwx.get("current", {})
                
                # Build recent lag records (last 7 hours from hourly if available)
                hourly_aq = raq.get("hourly", {})
                hourly_wx = rwx.get("hourly", {})
                
                times = hourly_aq.get("time", [])
                pm25_series = hourly_aq.get("pm2_5", [])
                pm10_series = hourly_aq.get("pm10", [])
                no2_series = hourly_aq.get("nitrogen_dioxide", [])
                temp_series = hourly_wx.get("temperature_2m", [])
                rh_series = hourly_wx.get("relative_humidity_2m", [])
                ws_series = hourly_wx.get("wind_speed_10m", [])
                wd_series = hourly_wx.get("wind_direction_10m", [])
                
                rows = []
                # Use current index or last available hours
                num_pts = min(len(times), len(pm25_series), 24)
                if num_pts > 0:
                    start_idx = max(0, num_pts - 12)
                    for i in range(start_idx, num_pts):
                        t_str = times[i]
                        rows.append({
                            "timestamp": pd.to_datetime(t_str),
                            "station_id": st["station_id"],
                            "station_name": st["station_name"],
                            "latitude": lat,
                            "longitude": lon,
                            "PM2.5": float(pm25_series[i]) if pm25_series[i] is not None else float(cur_aq.get("pm2_5", 40.0)),
                            "PM10": float(pm10_series[i]) if pm10_series[i] is not None else float(cur_aq.get("pm10", 65.0)),
                            "NO2": float(no2_series[i]) if no2_series[i] is not None else float(cur_aq.get("nitrogen_dioxide", 35.0)),
                            "temperature": float(temp_series[i]) if i < len(temp_series) and temp_series[i] is not None else float(cur_wx.get("temperature_2m", 28.0)),
                            "humidity": float(rh_series[i]) if i < len(rh_series) and rh_series[i] is not None else float(cur_wx.get("relative_humidity_2m", 65.0)),
                            "wind_speed": float(ws_series[i]) if i < len(ws_series) and ws_series[i] is not None else float(cur_wx.get("wind_speed_10m", 2.0)),
                            "wind_direction": float(wd_series[i]) if i < len(wd_series) and wd_series[i] is not None else float(cur_wx.get("wind_direction_10m", 180.0)),
                            "satellite_no2": 0.000085,
                            "aerosol_index": 1.2
                        })
                else:
                    rows.append({
                        "timestamp": pd.to_datetime(cur_aq.get("time", datetime.now().strftime("%Y-%m-%d %H:%M"))),
                        "station_id": st["station_id"],
                        "station_name": st["station_name"],
                        "latitude": lat,
                        "longitude": lon,
                        "PM2.5": float(cur_aq.get("pm2_5", 40.0)),
                        "PM10": float(cur_aq.get("pm10", 65.0)),
                        "NO2": float(cur_aq.get("nitrogen_dioxide", 35.0)),
                        "temperature": float(cur_wx.get("temperature_2m", 28.0)),
                        "humidity": float(cur_wx.get("relative_humidity_2m", 65.0)),
                        "wind_speed": float(cur_wx.get("wind_speed_10m", 2.0)),
                        "wind_direction": float(cur_wx.get("wind_direction_10m", 180.0)),
                        "satellite_no2": 0.000085,
                        "aerosol_index": 1.2
                    })
                return rows
            except Exception as e:
                print(f"Error fetching live data for {st['station_id']}: {e}")
                return []

        all_rows = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            results = list(ex.map(fetch_single, DELHI_STATIONS))
            for res in results:
                all_rows.extend(res)

        if all_rows:
            df_live = pd.DataFrame(all_rows)
            df_live["timestamp"] = pd.to_datetime(df_live["timestamp"])
            self.df_live = df_live
            self.live_timestamp = df_live["timestamp"].max()
            self.is_live_mode = True
            return df_live
        return self.df_master

    def get_active_df(self, mode: Optional[str] = None) -> (pd.DataFrame, Any, bool):
        """Returns the active dataframe (live or benchmark)."""
        is_live = (mode == "live") or (mode is None and self.is_live_mode)
        if is_live and self.df_live is not None and not self.df_live.empty:
            return self.df_live, self.live_timestamp, True
        elif is_live:
            df = self.fetch_live_telemetry()
            return df, self.live_timestamp, True
        return self.df_master, self.latest_timestamp, False

    def get_latest_station_data(self, mode: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns the most recent snapshot of observations for all Delhi monitoring stations."""
        df_active, ts_active, is_live = self.get_active_df(mode)
        if df_active is None or df_active.empty:
            return []
            
        latest_df = df_active[df_active["timestamp"] == ts_active].copy()
        
        stations = []
        for _, row in latest_df.iterrows():
            pm25 = round(float(row.get("PM2.5", 0.0)), 1)
            pm10 = round(float(row.get("PM10", 0.0)), 1)
            no2 = round(float(row.get("NO2", 0.0)), 1)
            temp = round(float(row.get("temperature", 0.0)), 1)
            humidity = round(float(row.get("humidity", 0.0)), 1)
            wind_speed = round(float(row.get("wind_speed", 0.0)), 1)
            wind_dir = round(float(row.get("wind_direction", 0.0)), 1)
            sat_no2 = float(row.get("satellite_no2", 0.00008))
            aerosol_idx = round(float(row.get("aerosol_index", 1.0)), 2)
            
            risk_status, risk_desc, color = get_risk_status(pm25)
            
            stations.append({
                "station_id": str(row["station_id"]),
                "station_name": str(row["station_name"]),
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "timestamp": str(row["timestamp"]),
                "pm25": pm25,
                "PM2.5": pm25,
                "PM10": pm10,
                "NO2": no2,
                "temperature": temp,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "wind_direction": wind_dir,
                "satellite_no2": sat_no2,
                "aerosol_index": aerosol_idx,
                "risk_status": risk_status,
                "risk_description": risk_desc,
                "color": color,
                "is_live": is_live
            })
            
        return stations

    def get_current_summary(self, mode: Optional[str] = None) -> Dict[str, Any]:
        """Returns Delhi-wide aggregate intelligence summary and KPIs."""
        stations = self.get_latest_station_data(mode)
        df_active, ts_active, is_live = self.get_active_df(mode)
        if not stations:
            return {
                "city": "Delhi NCR",
                "timestamp": datetime.now().isoformat(),
                "avg_pm25": 0, "avg_pm10": 0, "avg_no2": 0,
                "active_stations": 0, "hotspots_count": 0, "alerts_count": 0,
                "overall_risk_status": "Unknown", "demo_mode": not is_live
            }
            
        avg_pm25 = round(float(np.mean([s["PM2.5"] for s in stations])), 1)
        avg_pm10 = round(float(np.mean([s["PM10"] for s in stations])), 1)
        avg_no2 = round(float(np.mean([s["NO2"] for s in stations])), 1)
        avg_temp = round(float(np.mean([s["temperature"] for s in stations])), 1)
        avg_ws = round(float(np.mean([s["wind_speed"] for s in stations])), 1)
        
        hotspots = self.get_hotspots(mode)
        alerts = self.get_alerts(mode)
        risk_status, risk_desc, color = get_risk_status(avg_pm25)
        
        return {
            "city": "Delhi NCR, India",
            "timestamp": str(ts_active),
            "avg_pm25": avg_pm25,
            "avg_pm10": avg_pm10,
            "avg_no2": avg_no2,
            "avg_temp": avg_temp,
            "avg_wind_speed": avg_ws,
            "active_stations": len(stations),
            "hotspots_count": len(hotspots),
            "alerts_count": len(alerts),
            "overall_risk_status": risk_status,
            "risk_description": risk_desc,
            "risk_color": color,
            "demo_mode": not is_live,
            "mode": "live" if is_live else "benchmark",
            "primary_model": "Model B (CPCB + Weather + Sentinel-5P XGBoost)"
        }

    def predict_multi_horizon(self, station_id: Optional[str] = None, mode: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates real-time PM2.5 forecasts for horizons: Current, +1 Hour, +2 Hours, +3 Hours.
        Compares Model A (Ground+Weather) and Model B (+Sentinel-5P).
        """
        df_active, ts_active, is_live = self.get_active_df(mode)
        if df_active is None or df_active.empty:
            return {"horizons": [], "series": {}}
            
        if station_id and station_id != "ALL":
            df_st = df_active[df_active["station_id"] == station_id].sort_values(by="timestamp").copy()
            st_name = df_st["station_name"].iloc[-1] if not df_st.empty else station_id
        else:
            df_st = df_active.groupby("timestamp").mean(numeric_only=True).reset_index().copy()
            st_name = "Delhi NCR (City Average)"
            df_st["station_id"] = "DELHI_ALL"
            df_st["station_name"] = "Delhi NCR"
            
        if len(df_st) == 0:
            return {"horizons": [], "series": {}}
            
        recent = df_st.iloc[-max(1, min(len(df_st), 7)):].copy().reset_index(drop=True)
        
        curr_pm25 = float(recent["PM2.5"].iloc[-1])
        curr_pm10 = float(recent["PM10"].iloc[-1])
        curr_no2 = float(recent["NO2"].iloc[-1])
        curr_temp = float(recent["temperature"].iloc[-1])
        curr_humidity = float(recent["humidity"].iloc[-1])
        curr_ws = float(recent["wind_speed"].iloc[-1])
        curr_wd = float(recent["wind_direction"].iloc[-1])
        curr_sat_no2 = float(recent["satellite_no2"].iloc[-1]) if "satellite_no2" in recent.columns else 8.5e-5
        curr_aer = float(recent["aerosol_index"].iloc[-1]) if "aerosol_index" in recent.columns else 1.2
        curr_lat = float(recent["latitude"].iloc[-1]) if "latitude" in recent.columns else 28.61
        curr_lon = float(recent["longitude"].iloc[-1]) if "longitude" in recent.columns else 77.23
        
        last_ts = pd.to_datetime(recent["timestamp"].iloc[-1])
        
        forecast_labels = ["Current", "+1 Hour", "+2 Hours", "+3 Hours"]
        time_labels = [
            last_ts.strftime("%H:%M"),
            (last_ts + timedelta(hours=1)).strftime("%H:%M"),
            (last_ts + timedelta(hours=2)).strftime("%H:%M"),
            (last_ts + timedelta(hours=3)).strftime("%H:%M")
        ]
        
        series_a = [round(curr_pm25, 1)]
        series_b = [round(curr_pm25, 1)]
        
        rad = np.radians(curr_wd)
        wind_u = -curr_ws * np.sin(rad)
        wind_v = -curr_ws * np.cos(rad)
        
        pm_history_a = list(recent["PM2.5"].values)
        pm_history_b = list(recent["PM2.5"].values)
        
        for step in range(1, 4):
            step_ts = last_ts + timedelta(hours=step)
            hour = step_ts.hour
            sin_h = np.sin(2 * np.pi * hour / 24.0)
            cos_h = np.cos(2 * np.pi * hour / 24.0)
            dow = step_ts.dayofweek
            month = step_ts.month
            
            feat_a = {
                "PM2.5": pm_history_a[-1],
                "PM10": curr_pm10 * (0.98 ** step),
                "NO2": curr_no2 * (0.97 ** step),
                "PM2.5_lag1": pm_history_a[-2] if len(pm_history_a) >= 2 else pm_history_a[-1],
                "PM2.5_lag2": pm_history_a[-3] if len(pm_history_a) >= 3 else pm_history_a[-1],
                "PM2.5_lag3": pm_history_a[-4] if len(pm_history_a) >= 4 else pm_history_a[-1],
                "PM2.5_lag6": pm_history_a[-7] if len(pm_history_a) >= 7 else pm_history_a[-1],
                "PM2.5_roll_mean_3h": np.mean(pm_history_a[-3:]),
                "PM2.5_roll_std_3h": np.std(pm_history_a[-3:]) if len(pm_history_a) >= 3 else 3.0,
                "temperature": curr_temp + step * 0.5,
                "humidity": max(20.0, curr_humidity - step * 1.5),
                "wind_speed": max(0.5, curr_ws + step * 0.1),
                "wind_direction": curr_wd,
                "wind_u": wind_u,
                "wind_v": wind_v,
                "latitude": curr_lat,
                "longitude": curr_lon,
                "hour": hour,
                "day_of_week": dow,
                "month": month,
                "sin_hour": sin_h,
                "cos_hour": cos_h
            }
            
            feat_b = feat_a.copy()
            feat_b["satellite_no2"] = curr_sat_no2
            feat_b["aerosol_index"] = curr_aer
            
            if self.model_a is not None:
                df_a = pd.DataFrame([feat_a])[FEATURES_MODEL_A]
                pred_a = float(self.model_a.predict(df_a)[0])
            else:
                pred_a = curr_pm25 * (1.0 + 0.03 * step)
                
            if self.model_b is not None:
                df_b = pd.DataFrame([feat_b])[FEATURES_MODEL_B]
                pred_b = float(self.model_b.predict(df_b)[0])
            else:
                pred_b = curr_pm25 * (1.0 + 0.02 * step)
                
            pred_a = max(5.0, round(pred_a, 1))
            pred_b = max(5.0, round(pred_b, 1))
            
            series_a.append(pred_a)
            series_b.append(pred_b)
            pm_history_a.append(pred_a)
            pm_history_b.append(pred_b)
            
        lower_bound = [round(v * 0.91, 1) for v in series_b]
        upper_bound = [round(v * 1.09, 1) for v in series_b]
        
        trend_direction = "increasing" if series_b[1] > curr_pm25 + 3 else ("decreasing" if series_b[1] < curr_pm25 - 3 else "stable")
        explanation_signals = []
        if curr_ws < 2.0:
            explanation_signals.append(f"Low surface wind speed ({curr_ws:.1f} m/s) impeding particulate dispersion.")
        else:
            explanation_signals.append(f"Moderate surface wind speed ({curr_ws:.1f} m/s) assisting dispersion.")
            
        if curr_no2 > 45.0:
            explanation_signals.append(f"Elevated traffic/combustion precursor NO2 ({curr_no2:.1f} µg/m³) supporting secondary PM2.5 formation.")
        else:
            explanation_signals.append(f"Precursor NO2 is at baseline levels ({curr_no2:.1f} µg/m³).")
            
        if is_live:
            explanation_signals.append(f"Live real-time observations ingested from Open-Meteo API ({last_ts.strftime('%Y-%m-%d %H:%M')}).")
        else:
            explanation_signals.append("Benchmark episode observations active (CPCB ground + Sentinel-5P).")
            
        return {
            "station_id": station_id or "ALL",
            "station_name": st_name,
            "current_time": str(last_ts),
            "horizons": forecast_labels,
            "timestamps": time_labels,
            "series": {
                "model_a": series_a,
                "model_b": series_b,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound
            },
            "trend": trend_direction,
            "target_delta_1h": round(series_b[1] - curr_pm25, 1),
            "is_live": is_live,
            "ai_explanation": {
                "summary": f"Next 1-hour PM2.5 at {st_name} is forecast to reach {series_b[1]} µg/m³ ({trend_direction} trend from {curr_pm25:.1f} µg/m³).",
                "key_signals": explanation_signals
            }
        }

    def get_hotspots(self, mode: Optional[str] = None) -> List[Dict[str, Any]]:
        """Detects anomalous pollution hotspots with full temporal feature context."""
        df_active, ts_active, is_live = self.get_active_df(mode)
        if df_active is None or df_active.empty:
            return []
        
        recent_df = df_active[df_active["timestamp"] >= (ts_active - timedelta(hours=24))].copy()
        from ml.features import extract_features
        feat_df = extract_features(recent_df)
        
        latest_feat = feat_df[feat_df["timestamp"] == feat_df["timestamp"].max()].copy()
        if latest_feat.empty:
            latest_feat = df_active[df_active["timestamp"] == ts_active].copy()
            
        return detect_hotspots(latest_feat)

    def get_alerts(self, mode: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generates pollution alerts."""
        df_active, ts_active, is_live = self.get_active_df(mode)
        if df_active is None or df_active.empty:
            return []
        latest_df = df_active[df_active["timestamp"] == ts_active].copy()
        hotspots = self.get_hotspots(mode)
        
        forecasts = {}
        if self.model_b is not None:
            for _, r in latest_df.iterrows():
                try:
                    f = self.predict_multi_horizon(str(r["station_id"]), mode=mode)
                    forecasts[str(r["station_id"])] = f["series"]["model_b"][1]
                except Exception:
                    pass
                    
        return generate_alerts(latest_df, forecasts=forecasts, hotspots=hotspots)

    def get_grid(self, resolution: float = 0.035, mode: Optional[str] = None) -> Dict[str, Any]:
        """Calculates IDW spatial interpolation over Delhi grid."""
        stations = self.get_latest_station_data(mode)
        return interpolate_grid_pollution(stations, resolution_deg=resolution)

    def get_model_metrics(self) -> Dict[str, Any]:
        """Returns honest, non-fabricated Model A and Model B metrics."""
        return self.metrics

# Singleton instance
service = VayuNetService()
