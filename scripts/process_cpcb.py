"""
VayuNet AI — CPCB Ground Air Quality Data Processor
Parses raw CPCB air quality files (CSV or Excel) into standardized schema:
timestamp, station_id, station_name, latitude, longitude, PM2.5, PM10, NO2, AQI
Handles date parsing, unit normalization, negative/invalid sensor value imputation/filtering.
"""

import os
import glob
import logging
import argparse
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Known CPCB Station Coordinates Reference in Delhi
STATION_METADATA = {
    "DL_ANAND_VIHAR": {"station_name": "Anand Vihar", "latitude": 28.6508, "longitude": 77.3153},
    "DL_PUNJABI_BAGH": {"station_name": "Punjabi Bagh", "latitude": 28.6700, "longitude": 77.1333},
    "DL_ITO": {"station_name": "ITO", "latitude": 28.6289, "longitude": 77.2410},
    "DL_RK_PURAM": {"station_name": "RK Puram", "latitude": 28.5631, "longitude": 77.1706},
    "DL_LODHI_ROAD": {"station_name": "Lodhi Road", "latitude": 28.5918, "longitude": 77.2272},
    "DL_JAHANGIRPURI": {"station_name": "Jahangirpuri", "latitude": 28.7325, "longitude": 77.1651},
    "DL_DWARKA_SEC8": {"station_name": "Dwarka Sector 8", "latitude": 28.5921, "longitude": 77.0689},
    "DL_ROHINI": {"station_name": "Rohini", "latitude": 28.7328, "longitude": 77.1158},
    "DL_IGI_AIRPORT": {"station_name": "IGI Airport T3", "latitude": 28.5583, "longitude": 77.0869},
    "DL_BAWANA": {"station_name": "Bawana", "latitude": 28.7762, "longitude": 77.0378},
    "DL_OKHLA_PH2": {"station_name": "Okhla Phase 2", "latitude": 28.5307, "longitude": 77.2713},
    "DL_MANDIR_MARG": {"station_name": "Mandir Marg", "latitude": 28.6364, "longitude": 77.1994},
    "DL_SHADIPUR": {"station_name": "Shadipur", "latitude": 28.6514, "longitude": 77.1578},
    "DL_DTU": {"station_name": "Delhi Tech Univ", "latitude": 28.7501, "longitude": 77.1190},
    "DL_VIVEK_VIHAR": {"station_name": "Vivek Vihar", "latitude": 28.6724, "longitude": 77.3150}
}

def calculate_approx_cpcb_aqi(pm25: float, pm10: float, no2: float) -> float:
    """
    Calculate approximate Indian National Air Quality Index (NAQI) sub-indices.
    Uses CPCB standard breakpoint linear formula.
    """
    if pd.isna(pm25) and pd.isna(pm10):
        return np.nan
    
    # PM2.5 breakpoints: (0-30: 0-50), (30-60: 51-100), (60-90: 101-200), (90-120: 201-300), (120-250: 301-400), (250+: 401-500)
    sub_pm25 = 0.0
    if not pd.isna(pm25):
        if pm25 <= 30:
            sub_pm25 = (50 / 30) * pm25
        elif pm25 <= 60:
            sub_pm25 = 50 + (50 / 30) * (pm25 - 30)
        elif pm25 <= 90:
            sub_pm25 = 100 + (100 / 30) * (pm25 - 60)
        elif pm25 <= 120:
            sub_pm25 = 200 + (100 / 30) * (pm25 - 90)
        elif pm25 <= 250:
            sub_pm25 = 300 + (100 / 130) * (pm25 - 120)
        else:
            sub_pm25 = min(500.0, 400 + (100 / 150) * (pm25 - 250))
            
    # PM10 breakpoints: (0-50: 0-50), (50-100: 51-100), (100-250: 101-200), (250-350: 201-300), (350-430: 301-400), (430+: 401-500)
    sub_pm10 = 0.0
    if not pd.isna(pm10):
        if pm10 <= 50:
            sub_pm10 = pm10
        elif pm10 <= 100:
            sub_pm10 = 50 + (50 / 50) * (pm10 - 50)
        elif pm10 <= 250:
            sub_pm10 = 100 + (100 / 150) * (pm10 - 100)
        elif pm10 <= 350:
            sub_pm10 = 200 + (100 / 100) * (pm10 - 250)
        elif pm10 <= 430:
            sub_pm10 = 300 + (100 / 80) * (pm10 - 350)
        else:
            sub_pm10 = min(500.0, 400 + (100 / 70) * (pm10 - 430))
            
    return max(sub_pm25, sub_pm10)

def clean_cpcb_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names and clean sensor outliers."""
    col_mapping = {}
    for col in df.columns:
        c_lower = col.strip().lower()
        if "time" in c_lower or "date" in c_lower:
            col_mapping[col] = "timestamp"
        elif "station" in c_lower and "id" in c_lower:
            col_mapping[col] = "station_id"
        elif "station" in c_lower:
            col_mapping[col] = "station_name"
        elif "pm2.5" in c_lower or "pm25" in c_lower:
            col_mapping[col] = "PM2.5"
        elif "pm10" in c_lower:
            col_mapping[col] = "PM10"
        elif "no2" in c_lower:
            col_mapping[col] = "NO2"
        elif "aqi" in c_lower:
            col_mapping[col] = "AQI"
        elif "lat" in c_lower:
            col_mapping[col] = "latitude"
        elif "lon" in c_lower:
            col_mapping[col] = "longitude"
            
    df = df.rename(columns=col_mapping)
    
    if "timestamp" not in df.columns:
        raise ValueError("Missing 'timestamp' column in CPCB data.")
        
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    
    # Filter/Clean invalid negative sensor values or physical extremes
    for pollutant, (min_val, max_val) in [("PM2.5", (1.0, 1000.0)), ("PM10", (1.0, 1500.0)), ("NO2", (0.1, 500.0))]:
        if pollutant in df.columns:
            df[pollutant] = pd.to_numeric(df[pollutant], errors="coerce")
            df.loc[(df[pollutant] < min_val) | (df[pollutant] > max_val), pollutant] = np.nan

    # Fill metadata if station_id is present
    if "station_id" in df.columns:
        for st_id, meta in STATION_METADATA.items():
            mask = df["station_id"] == st_id
            if "station_name" not in df.columns or df.loc[mask, "station_name"].isna().all():
                df.loc[mask, "station_name"] = meta["station_name"]
            if "latitude" not in df.columns or df.loc[mask, "latitude"].isna().all():
                df.loc[mask, "latitude"] = meta["latitude"]
            if "longitude" not in df.columns or df.loc[mask, "longitude"].isna().all():
                df.loc[mask, "longitude"] = meta["longitude"]

    # Calculate AQI if missing
    if "AQI" not in df.columns or df["AQI"].isna().all():
        df["AQI"] = df.apply(lambda row: calculate_approx_cpcb_aqi(row.get("PM2.5"), row.get("PM10"), row.get("NO2")), axis=1)

    return df

def process_cpcb_files(input_dir: str = "data/raw/cpcb/", output_path: str = "data/processed/cpcb_clean.csv"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    files = glob.glob(os.path.join(input_dir, "*.csv")) + glob.glob(os.path.join(input_dir, "*.xlsx"))
    
    if not files:
        logging.warning(f"No CPCB input files found in {input_dir}")
        return pd.DataFrame()
        
    dfs = []
    for f in files:
        try:
            if f.endswith(".csv"):
                d = pd.read_csv(f)
            else:
                d = pd.read_excel(f)
            dfs.append(clean_cpcb_dataframe(d))
        except Exception as e:
            logging.error(f"Failed to process {f}: {e}")
            
    if dfs:
        combined = pd.concat(dfs, ignore_index=True).drop_duplicates(subset=["station_id", "timestamp"])
        combined.sort_values(by=["station_id", "timestamp"], inplace=True)
        combined.to_csv(output_path, index=False)
        logging.info(f"Successfully processed {len(combined)} CPCB records -> {output_path}")
        return combined
    return pd.DataFrame()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean and process CPCB ground station data")
    parser.add_argument("--input", default="data/raw/cpcb/", help="Input directory")
    parser.add_argument("--out", default="data/processed/cpcb_clean.csv", help="Output CSV path")
    args = parser.parse_args()
    
    process_cpcb_files(args.input, args.out)
