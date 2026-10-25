"""
VayuNet AI — Synthetic / Demo Dataset Generator
Generates realistic, physically consistent synthetic data matching the exact schemas of:
1. CPCB Ground Stations (15 Delhi stations, hourly PM2.5, PM10, NO2, AQI)
2. Open-Meteo Hourly Weather (temperature, humidity, wind_speed, wind_direction)
3. Sentinel-5P TROPOMI Satellite Overpass (tropospheric NO2 column, aerosol index)

Features realistic Delhi diurnal cycles, temperature inversions, winter peak smog episodes,
and spatial variation across industrial (Anand Vihar, Bawana) and greener zones (Lodhi Road).
"""

import os
import math
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Delhi CPCB stations with spatial profiles
STATIONS = [
    {"id": "DL_ANAND_VIHAR", "name": "Anand Vihar", "lat": 28.6508, "lon": 77.3153, "zone": "Industrial/ISBT", "base_mult": 1.45},
    {"id": "DL_PUNJABI_BAGH", "name": "Punjabi Bagh", "lat": 28.6700, "lon": 77.1333, "zone": "Residential/Traffic", "base_mult": 1.15},
    {"id": "DL_ITO", "name": "ITO", "lat": 28.6289, "lon": 77.2410, "zone": "Commercial/High Traffic", "base_mult": 1.25},
    {"id": "DL_RK_PURAM", "name": "RK Puram", "lat": 28.5631, "lon": 77.1706, "zone": "Residential", "base_mult": 1.05},
    {"id": "DL_LODHI_ROAD", "name": "Lodhi Road", "lat": 28.5918, "lon": 77.2272, "zone": "Institutional/Green", "base_mult": 0.85},
    {"id": "DL_JAHANGIRPURI", "name": "Jahangirpuri", "lat": 28.7325, "lon": 77.1651, "zone": "Industrial/Dense", "base_mult": 1.40},
    {"id": "DL_DWARKA_SEC8", "name": "Dwarka Sector 8", "lat": 28.5921, "lon": 77.0689, "zone": "Residential Suburb", "base_mult": 0.95},
    {"id": "DL_ROHINI", "name": "Rohini", "lat": 28.7328, "lon": 77.1158, "zone": "Residential/Commercial", "base_mult": 1.20},
    {"id": "DL_IGI_AIRPORT", "name": "IGI Airport T3", "lat": 28.5583, "lon": 77.0869, "zone": "Aviation/Highway", "base_mult": 1.00},
    {"id": "DL_BAWANA", "name": "Bawana", "lat": 28.7762, "lon": 77.0378, "zone": "Heavy Industrial", "base_mult": 1.50},
    {"id": "DL_OKHLA_PH2", "name": "Okhla Phase 2", "lat": 28.5307, "lon": 77.2713, "zone": "Industrial Area", "base_mult": 1.35},
    {"id": "DL_MANDIR_MARG", "name": "Mandir Marg", "lat": 28.6364, "lon": 77.1994, "zone": "Central Ridge/Green", "base_mult": 0.88},
    {"id": "DL_SHADIPUR", "name": "Shadipur", "lat": 28.6514, "lon": 77.1578, "zone": "Dense Urban/Traffic", "base_mult": 1.18},
    {"id": "DL_DTU", "name": "Delhi Tech Univ", "lat": 28.7501, "lon": 77.1190, "zone": "Semi-Industrial North", "base_mult": 1.22},
    {"id": "DL_VIVEK_VIHAR", "name": "Vivek Vihar", "lat": 28.6724, "lon": 77.3150, "zone": "East Delhi Urban", "base_mult": 1.28}
]

def generate_realistic_delhi_dataset(
    start_date: str = "2024-01-01 00:00:00",
    days: int = 45,
    seed: int = 42
):
    np.random.seed(seed)
    random.seed(seed)
    
    start_dt = pd.to_datetime(start_date)
    timestamps = [start_dt + timedelta(hours=i) for i in range(days * 24)]
    n_steps = len(timestamps)
    
    os.makedirs("data/raw/cpcb", exist_ok=True)
    os.makedirs("data/raw/weather", exist_ok=True)
    os.makedirs("data/raw/sentinel5p", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    
    cpcb_records = []
    weather_records = []
    satellite_records = []
    
    for st in STATIONS:
        # Base seasonal and diurnal weather for station
        for i, ts in enumerate(timestamps):
            hour = ts.hour
            doy = ts.dayofyear
            
            # Diurnal temperature cycle (min at 6am, max at 3pm)
            base_temp = 14.0 + 8.0 * math.sin((hour - 9) * math.pi / 12) + np.random.normal(0, 1.2)
            # Relative humidity is inverse of temp
            base_humidity = np.clip(75.0 - 25.0 * math.sin((hour - 9) * math.pi / 12) + np.random.normal(0, 4.0), 20.0, 98.0)
            # Wind speed: calmer at night (0.8 - 2.5 m/s), breezier in afternoon (2.5 - 6.0 m/s)
            wind_speed = np.clip(1.5 + 1.8 * math.sin((hour - 10) * math.pi / 12) + np.random.exponential(0.6), 0.3, 10.5)
            # Dominant NW winds in winter/spring Delhi (290 - 320 degrees)
            wind_dir = (305 + np.random.normal(0, 30)) % 360
            
            # Weather record
            weather_records.append({
                "timestamp": ts,
                "station_id": st["id"],
                "station_name": st["name"],
                "latitude": st["lat"],
                "longitude": st["lon"],
                "temperature": round(base_temp, 2),
                "humidity": round(base_humidity, 1),
                "wind_speed": round(wind_speed, 2),
                "wind_direction": round(wind_dir, 1)
            })
            
            # Pollution Physics Simulation:
            # 1. Nocturnal Boundary Layer Inversion (High at 00:00 - 08:00, Low at 13:00 - 17:00)
            diurnal_poll_factor = 1.0 + 0.55 * math.cos((hour - 2) * math.pi / 12)
            
            # 2. Wind dispersion factor (Higher wind speed -> lower ground concentration)
            wind_dispersion = 1.0 / (1.0 + 0.35 * wind_speed)
            
            # 3. Episodic smog / stagnation events (periodic high pollution multi-day waves)
            synoptic_event = 1.0 + 0.35 * math.sin(i / 36.0)
            
            # Base PM2.5 calculation
            base_pm25 = 110.0 * st["base_mult"] * diurnal_poll_factor * wind_dispersion * synoptic_event
            noise_pm25 = np.random.normal(0, 12.0)
            pm25_val = max(18.0, round(base_pm25 + noise_pm25, 1))
            
            # PM10 is correlated with PM2.5 + road dust / construction
            pm10_val = max(pm25_val * 1.3, round(pm25_val * (1.6 + 0.2 * np.random.rand()) + 25.0, 1))
            
            # NO2 from vehicular / combustion emissions (morning 8am & evening 8pm rush hour peaks)
            rush_hour_boost = 1.4 if hour in [8, 9, 10, 19, 20, 21] else 1.0
            no2_val = max(10.0, round((38.0 * st["base_mult"] * rush_hour_boost * wind_dispersion) + np.random.normal(0, 6.0), 1))
            
            # AQI estimation
            sub_pm25 = (100 + (100/130)*(pm25_val - 120)) if pm25_val > 120 else (pm25_val * 1.5)
            aqi_val = min(500.0, round(max(sub_pm25, pm10_val * 0.9), 0))
            
            cpcb_records.append({
                "timestamp": ts,
                "station_id": st["id"],
                "station_name": st["name"],
                "latitude": st["lat"],
                "longitude": st["lon"],
                "PM2.5": pm25_val,
                "PM10": pm10_val,
                "NO2": no2_val,
                "AQI": aqi_val
            })
            
            # Sentinel-5P TROPOMI Satellite Overpass (typically around 13:30 local solar time, interpolated daily)
            # Tropospheric NO2 Column Number Density (mol/m^2) approx range: 5e-5 to 2.5e-4
            # Aerosol Index (AER_AI) approx range: 0.5 to 3.5
            sat_no2_density = (no2_val * 2.2e-6) + np.random.normal(0, 0.15e-5)
            aerosol_idx = (pm25_val / 80.0) + np.random.normal(0, 0.15)
            
            satellite_records.append({
                "timestamp": ts,
                "station_id": st["id"],
                "station_name": st["name"],
                "latitude": st["lat"],
                "longitude": st["lon"],
                "tropospheric_NO2_column_number_density": round(max(1e-6, sat_no2_density), 8),
                "absorbing_aerosol_index": round(max(0.1, aerosol_idx), 4)
            })

    df_cpcb = pd.DataFrame(cpcb_records)
    df_weather = pd.DataFrame(weather_records)
    df_sat = pd.DataFrame(satellite_records)
    
    # Save Raw Datasets
    cpcb_path = "data/raw/cpcb/delhi_cpcb_stations.csv"
    weather_path = "data/raw/weather/delhi_weather.csv"
    sat_path = "data/raw/sentinel5p/sentinel5p_delhi_no2.csv"
    
    df_cpcb.to_csv(cpcb_path, index=False)
    df_weather.to_csv(weather_path, index=False)
    df_sat.to_csv(sat_path, index=False)
    
    print(f"Generated raw synthetic CPCB dataset: {len(df_cpcb)} records -> {cpcb_path}")
    print(f"Generated raw synthetic Weather dataset: {len(df_weather)} records -> {weather_path}")
    print(f"Generated raw synthetic Sentinel-5P dataset: {len(df_sat)} records -> {sat_path}")
    
    return df_cpcb, df_weather, df_sat

if __name__ == "__main__":
    generate_realistic_delhi_dataset()
