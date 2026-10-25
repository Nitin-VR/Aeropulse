"""
VayuNet AI — Data Preprocessing & Fusion Pipeline
Ingests and aligns CPCB Ground Sensors, Open-Meteo Weather, and Sentinel-5P Satellite datasets.
Handles deduplication, missing values, timestamp alignment, and creates `data/processed/delhi_master.csv`.
"""

import os
import glob
import logging
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def load_cpcb_data(path_pattern: str = "data/raw/cpcb/*.csv") -> pd.DataFrame:
    files = glob.glob(path_pattern)
    if not files:
        logging.warning("No CPCB CSV files found.")
        return pd.DataFrame()
        
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        df.columns = [c.strip() for c in df.columns]
        # Standardize column naming
        col_map = {}
        for c in df.columns:
            cl = c.lower()
            if "time" in cl or "date" in cl:
                col_map[c] = "timestamp"
            elif "station" in cl and "id" in cl:
                col_map[c] = "station_id"
            elif "station" in cl:
                col_map[c] = "station_name"
            elif "pm2.5" in cl or "pm25" in cl:
                col_map[c] = "PM2.5"
            elif "pm10" in cl:
                col_map[c] = "PM10"
            elif "no2" in cl:
                col_map[c] = "NO2"
            elif "aqi" in cl:
                col_map[c] = "AQI"
            elif "lat" in cl:
                col_map[c] = "latitude"
            elif "lon" in cl:
                col_map[c] = "longitude"
        df = df.rename(columns=col_map)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            dfs.append(df)
            
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)

def load_weather_data(path_pattern: str = "data/raw/weather/*.csv") -> pd.DataFrame:
    files = glob.glob(path_pattern)
    if not files:
        logging.warning("No Weather CSV files found.")
        return pd.DataFrame()
    
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        df.columns = [c.strip() for c in df.columns]
        col_map = {}
        for c in df.columns:
            cl = c.lower()
            if "time" in cl or "date" in cl:
                col_map[c] = "timestamp"
            elif "temp" in cl:
                col_map[c] = "temperature"
            elif "humid" in cl or "rh" in cl:
                col_map[c] = "humidity"
            elif "wind_spd" in cl or "wind_speed" in cl:
                col_map[c] = "wind_speed"
            elif "wind_dir" in cl or "wind_direction" in cl:
                col_map[c] = "wind_direction"
        df = df.rename(columns=col_map)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            dfs.append(df)
            
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)

def load_sentinel5p_data(path_pattern: str = "data/raw/sentinel5p/*.csv") -> pd.DataFrame:
    files = glob.glob(path_pattern)
    if not files:
        logging.warning("No Sentinel-5P CSV files found.")
        return pd.DataFrame()
        
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        df.columns = [c.strip() for c in df.columns]
        col_map = {}
        for c in df.columns:
            cl = c.lower()
            if "time" in cl or "date" in cl:
                col_map[c] = "timestamp"
            elif "tropospheric_no2" in cl or "mean" in cl or "no2" in cl:
                col_map[c] = "satellite_no2"
            elif "aerosol" in cl or "aer_ai" in cl:
                col_map[c] = "aerosol_index"
        df = df.rename(columns=col_map)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            dfs.append(df)
            
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)

def merge_and_clean_datasets(
    output_path: str = "data/processed/delhi_master.csv",
    save: bool = True
) -> pd.DataFrame:
    """
    Cleans, aligns, and merges CPCB, Weather, and Sentinel-5P observations.
    """
    df_cpcb = load_cpcb_data()
    df_weather = load_weather_data()
    df_sat = load_sentinel5p_data()
    
    if df_cpcb.empty:
        raise FileNotFoundError("CPCB ground data is required to construct the master dataset.")
        
    # Round timestamps to nearest hour
    df_cpcb["timestamp"] = df_cpcb["timestamp"].dt.round("h")
    df_cpcb = df_cpcb.drop_duplicates(subset=["station_id", "timestamp"])
    
    # Merge with Weather on station_id and timestamp, or timestamp + spatial nearest
    if not df_weather.empty:
        df_weather["timestamp"] = df_weather["timestamp"].dt.round("h")
        if "station_id" in df_weather.columns:
            df_weather = df_weather.drop_duplicates(subset=["station_id", "timestamp"])
            df_master = pd.merge(df_cpcb, df_weather[["station_id", "timestamp", "temperature", "humidity", "wind_speed", "wind_direction"]], on=["station_id", "timestamp"], how="left")
        else:
            df_weather = df_weather.drop_duplicates(subset=["timestamp"])
            df_master = pd.merge(df_cpcb, df_weather[["timestamp", "temperature", "humidity", "wind_speed", "wind_direction"]], on="timestamp", how="left")
    else:
        df_master = df_cpcb.copy()
        for col in ["temperature", "humidity", "wind_speed", "wind_direction"]:
            df_master[col] = np.nan

    # Merge with Sentinel-5P data
    if not df_sat.empty:
        df_sat["timestamp"] = df_sat["timestamp"].dt.round("h")
        sat_cols = [c for c in ["satellite_no2", "aerosol_index"] if c in df_sat.columns]
        if "station_id" in df_sat.columns:
            df_sat = df_sat.drop_duplicates(subset=["station_id", "timestamp"])
            df_master = pd.merge(df_master, df_sat[["station_id", "timestamp"] + sat_cols], on=["station_id", "timestamp"], how="left")
        else:
            df_sat = df_sat.drop_duplicates(subset=["timestamp"])
            df_master = pd.merge(df_master, df_sat[["timestamp"] + sat_cols], on="timestamp", how="left")
    else:
        df_master["satellite_no2"] = np.nan
        df_master["aerosol_index"] = np.nan

    # Ensure required core columns exist
    required_cols = [
        "timestamp", "station_id", "station_name", "latitude", "longitude",
        "PM2.5", "PM10", "NO2", "temperature", "humidity", "wind_speed",
        "wind_direction", "satellite_no2", "aerosol_index"
    ]
    for c in required_cols:
        if c not in df_master.columns:
            df_master[c] = np.nan
            
    df_master = df_master[required_cols].copy()
    
    # Sort chronologically by station
    df_master.sort_values(by=["station_id", "timestamp"], inplace=True)
    
    # Impute missing continuous sensor readings per station using forward/backward fill and rolling averages
    numeric_cols = ["PM2.5", "PM10", "NO2", "temperature", "humidity", "wind_speed", "wind_direction", "satellite_no2", "aerosol_index"]
    
    df_master[numeric_cols] = df_master.groupby("station_id")[numeric_cols].transform(lambda group: group.ffill().bfill())
    
    # Fallback global median imputation for any remaining NaNs
    df_master[numeric_cols] = df_master[numeric_cols].fillna(df_master[numeric_cols].median())
    
    if save:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df_master.to_csv(output_path, index=False)
        logging.info(f"Master dataset saved successfully: {len(df_master)} records -> {output_path}")
        
    return df_master

if __name__ == "__main__":
    merge_and_clean_datasets()
