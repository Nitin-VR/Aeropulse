"""
VayuNet AI — Feature Engineering Module
Builds chronological lag features, temporal cyclical encodings, meteorological vectors,
and target variable (PM2.5 t+1) for Model A (Ground+Weather) and Model B (+Sentinel-5P Satellite).
"""

import math
import numpy as np
import pandas as pd
from typing import Tuple, List

# Feature Sets definition
FEATURES_MODEL_A = [
    "PM2.5", "PM10", "NO2",
    "PM2.5_lag1", "PM2.5_lag2", "PM2.5_lag3", "PM2.5_lag6",
    "PM2.5_roll_mean_3h", "PM2.5_roll_std_3h",
    "temperature", "humidity", "wind_speed", "wind_direction",
    "wind_u", "wind_v",
    "latitude", "longitude",
    "hour", "day_of_week", "month", "sin_hour", "cos_hour"
]

FEATURES_MODEL_B = FEATURES_MODEL_A + [
    "satellite_no2", "aerosol_index"
]

TARGET_COL = "target_pm25_next_hour"

def extract_features(df: pd.DataFrame, is_training: bool = False) -> pd.DataFrame:
    """
    Computes lag features, temporal encodings, and next-hour prediction targets.
    """
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(by=["station_id", "timestamp"]).reset_index(drop=True)
    
    # 1. Temporal encodings
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.month
    
    # Cyclical hour encoding
    df["sin_hour"] = np.sin(2 * np.pi * df["hour"] / 24.0)
    df["cos_hour"] = np.cos(2 * np.pi * df["hour"] / 24.0)
    
    # 2. Meteorological components (U and V wind vectors)
    rad = np.radians(df["wind_direction"].fillna(0))
    df["wind_u"] = -df["wind_speed"] * np.sin(rad) # E-W wind component
    df["wind_v"] = -df["wind_speed"] * np.cos(rad) # N-S wind component
    
    # 3. Station-wise Lag and Rolling Window Features
    df["PM2.5_lag1"] = df.groupby("station_id")["PM2.5"].shift(1)
    df["PM2.5_lag2"] = df.groupby("station_id")["PM2.5"].shift(2)
    df["PM2.5_lag3"] = df.groupby("station_id")["PM2.5"].shift(3)
    df["PM2.5_lag6"] = df.groupby("station_id")["PM2.5"].shift(6)
    
    df["PM2.5_roll_mean_3h"] = df.groupby("station_id")["PM2.5"].transform(lambda s: s.rolling(3, min_periods=1).mean())
    df["PM2.5_roll_std_3h"] = df.groupby("station_id")["PM2.5"].transform(lambda s: s.rolling(3, min_periods=1).std()).fillna(0.0)
    
    # 4. Target: PM2.5 at t+1 hour
    df[TARGET_COL] = df.groupby("station_id")["PM2.5"].shift(-1)
    
    if is_training:
        df_clean = df.dropna(subset=[TARGET_COL, "PM2.5_lag1", "PM2.5_lag2"]).reset_index(drop=True)
    else:
        df_clean = df.dropna(subset=["PM2.5"]).reset_index(drop=True)
        # Fill missing initial lags with current value if needed
        for c in ["PM2.5_lag1", "PM2.5_lag2", "PM2.5_lag3", "PM2.5_lag6"]:
            df_clean[c] = df_clean[c].fillna(df_clean["PM2.5"])
            
    # Fill remaining lag features
    df_clean["PM2.5_lag3"] = df_clean["PM2.5_lag3"].fillna(df_clean["PM2.5_lag2"])
    df_clean["PM2.5_lag6"] = df_clean["PM2.5_lag6"].fillna(df_clean["PM2.5_lag3"])
    
    return df_clean

def get_train_val_test_split(
    df_features: pd.DataFrame, 
    train_ratio: float = 0.70, 
    val_ratio: float = 0.15
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Strict Chronological Train / Validation / Test split.
    Guarantees no data leakage across time horizons.
    """
    timestamps = np.sort(df_features["timestamp"].unique())
    n_total = len(timestamps)
    
    train_idx = int(n_total * train_ratio)
    val_idx = int(n_total * (train_ratio + val_ratio))
    
    train_cutoff = timestamps[train_idx]
    val_cutoff = timestamps[val_idx]
    
    df_train = df_features[df_features["timestamp"] < train_cutoff].copy()
    df_val = df_features[(df_features["timestamp"] >= train_cutoff) & (df_features["timestamp"] < val_cutoff)].copy()
    df_test = df_features[df_features["timestamp"] >= val_cutoff].copy()
    
    return df_train, df_val, df_test
