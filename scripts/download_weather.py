"""
VayuNet AI — Weather Data Downloader (Open-Meteo API)
Downloads historical/current hourly weather data for Delhi NCR monitoring stations.
Variables: temperature_2m, relative_humidity_2m, wind_speed_10m, wind_direction_10m, surface_pressure
"""

import os
import sys
import json
import logging
import argparse
import requests
import pandas as pd
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Delhi representative CPCB station locations
DELHI_STATIONS = [
    {"station_id": "DL_ANAND_VIHAR", "station_name": "Anand Vihar", "latitude": 28.6508, "longitude": 77.3153},
    {"station_id": "DL_PUNJABI_BAGH", "station_name": "Punjabi Bagh", "latitude": 28.6700, "longitude": 77.1333},
    {"station_id": "DL_ITO", "station_name": "ITO", "latitude": 28.6289, "longitude": 77.2410},
    {"station_id": "DL_RK_PURAM", "station_name": "RK Puram", "latitude": 28.5631, "longitude": 77.1706},
    {"station_id": "DL_LODHI_ROAD", "station_name": "Lodhi Road", "latitude": 28.5918, "longitude": 77.2272},
    {"station_id": "DL_JAHANGIRPURI", "station_name": "Jahangirpuri", "latitude": 28.7325, "longitude": 77.1651},
    {"station_id": "DL_DWARKA_SEC8", "station_name": "Dwarka Sector 8", "latitude": 28.5921, "longitude": 77.0689},
    {"station_id": "DL_ROHINI", "station_name": "Rohini", "latitude": 28.7328, "longitude": 77.1158},
    {"station_id": "DL_IGI_AIRPORT", "station_name": "IGI Airport T3", "latitude": 28.5583, "longitude": 77.0869},
    {"station_id": "DL_BAWANA", "station_name": "Bawana", "latitude": 28.7762, "longitude": 77.0378},
    {"station_id": "DL_OKHLA_PH2", "station_name": "Okhla Phase 2", "latitude": 28.5307, "longitude": 77.2713},
    {"station_id": "DL_MANDIR_MARG", "station_name": "Mandir Marg", "latitude": 28.6364, "longitude": 77.1994},
    {"station_id": "DL_SHADIPUR", "station_name": "Shadipur", "latitude": 28.6514, "longitude": 77.1578},
    {"station_id": "DL_DTU", "station_name": "Delhi Tech Univ", "latitude": 28.7501, "longitude": 77.1190},
    {"station_id": "DL_VIVEK_VIHAR", "station_name": "Vivek Vihar", "latitude": 28.6724, "longitude": 77.3150}
]

def fetch_open_meteo_weather(lat: float, lon: float, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch hourly historical or archive weather data from Open-Meteo.
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ["temperature_2m", "relative_humidity_2m", "wind_speed_10m", "wind_direction_10m", "surface_pressure"],
        "timezone": "Asia/Kolkata"
    }
    
    try:
        logging.info(f"Querying Open-Meteo for ({lat}, {lon}) [{start_date} to {end_date}]...")
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            hourly = data.get("hourly", {})
            df = pd.DataFrame({
                "timestamp": hourly.get("time", []),
                "temperature": hourly.get("temperature_2m", []),
                "humidity": hourly.get("relative_humidity_2m", []),
                "wind_speed": hourly.get("wind_speed_10m", []),
                "wind_direction": hourly.get("wind_direction_10m", []),
                "pressure": hourly.get("surface_pressure", [])
            })
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            return df
        else:
            logging.warning(f"Open-Meteo archive returned status {resp.status_code}. Trying forecast API fallback...")
            fallback_url = "https://api.open-meteo.com/v1/forecast"
            params_fallback = {
                "latitude": lat,
                "longitude": lon,
                "hourly": ["temperature_2m", "relative_humidity_2m", "wind_speed_10m", "wind_direction_10m", "surface_pressure"],
                "past_days": 14,
                "forecast_days": 2,
                "timezone": "Asia/Kolkata"
            }
            resp_fallback = requests.get(fallback_url, params=params_fallback, timeout=15)
            if resp_fallback.status_code == 200:
                data = resp_fallback.json()
                hourly = data.get("hourly", {})
                df = pd.DataFrame({
                    "timestamp": hourly.get("time", []),
                    "temperature": hourly.get("temperature_2m", []),
                    "humidity": hourly.get("relative_humidity_2m", []),
                    "wind_speed": hourly.get("wind_speed_10m", []),
                    "wind_direction": hourly.get("wind_direction_10m", []),
                    "pressure": hourly.get("surface_pressure", [])
                })
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                return df
    except Exception as e:
        logging.error(f"Error fetching weather from Open-Meteo: {e}")
    
    return pd.DataFrame()

def download_delhi_weather(output_path: str = "data/raw/weather/delhi_weather.csv", start_date: str = "2024-01-01", end_date: str = "2024-02-28"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    all_station_weather = []
    
    for st in DELHI_STATIONS:
        df = fetch_open_meteo_weather(st["latitude"], st["longitude"], start_date, end_date)
        if not df.empty:
            df["station_id"] = st["station_id"]
            df["station_name"] = st["station_name"]
            df["latitude"] = st["latitude"]
            df["longitude"] = st["longitude"]
            all_station_weather.append(df)
            
    if all_station_weather:
        combined = pd.concat(all_station_weather, ignore_index=True)
        combined.to_csv(output_path, index=False)
        logging.info(f"Saved {len(combined)} weather records to {output_path}")
    else:
        logging.warning("No weather records downloaded from network.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download historical weather from Open-Meteo")
    parser.add_argument("--start", default="2024-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2024-02-15", help="End date (YYYY-MM-DD)")
    parser.add_argument("--out", default="data/raw/weather/delhi_weather.csv", help="Output file path")
    args = parser.parse_args()
    
    download_delhi_weather(output_path=args.out, start_date=args.start, end_date=args.end)
