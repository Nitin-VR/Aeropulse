"""
VayuNet AI — Model Training Module
Trains XGBoost Regressors for:
- Model A: CPCB Ground Sensors + Open-Meteo Weather
- Model B: CPCB Ground Sensors + Open-Meteo Weather + Sentinel-5P Satellite Data
Utilizes chronological train/val split with early stopping.
"""

import os
import json
import joblib
import logging
import argparse
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml.preprocessing import merge_and_clean_datasets
from ml.features import extract_features, get_train_val_test_split, FEATURES_MODEL_A, FEATURES_MODEL_B, TARGET_COL
from ml.anomaly import train_anomaly_detector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def train_models(master_csv_path: str = "data/processed/delhi_master.csv"):
    os.makedirs("models", exist_ok=True)
    
    if not os.path.exists(master_csv_path):
        logging.info("Master CSV not found. Running merge_and_clean_datasets()...")
        df_master = merge_and_clean_datasets(master_csv_path)
    else:
        df_master = pd.read_csv(master_csv_path)
        
    logging.info(f"Extracting features from master dataset ({len(df_master)} rows)...")
    df_feat = extract_features(df_master, is_training=True)
    
    # Train anomaly detector
    logging.info("Training Isolation Forest anomaly detector...")
    train_anomaly_detector(df_feat)
    
    # Split chronologically
    df_train, df_val, df_test = get_train_val_test_split(df_feat, train_ratio=0.70, val_ratio=0.15)
    logging.info(f"Dataset split: Train={len(df_train)}, Val={len(df_val)}, Test={len(df_test)}")
    
    # ------------------ MODEL A (CPCB + Weather) ------------------
    logging.info("Training Model A (CPCB + Weather)...")
    X_train_a = df_train[FEATURES_MODEL_A]
    y_train_a = df_train[TARGET_COL]
    X_val_a = df_val[FEATURES_MODEL_A]
    y_val_a = df_val[TARGET_COL]
    
    model_a = XGBRegressor(
        n_estimators=300,
        learning_rate=0.04,
        max_depth=6,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        early_stopping_rounds=25
    )
    model_a.fit(
        X_train_a, y_train_a,
        eval_set=[(X_val_a, y_val_a)],
        verbose=False
    )
    
    joblib.dump(model_a, "models/pm25_xgboost_model_a.pkl")
    logging.info("Model A trained and saved to models/pm25_xgboost_model_a.pkl")
    
    # ------------------ MODEL B (CPCB + Weather + Sentinel-5P) ------------------
    logging.info("Training Model B (CPCB + Weather + Sentinel-5P)...")
    X_train_b = df_train[FEATURES_MODEL_B]
    y_train_b = df_train[TARGET_COL]
    X_val_b = df_val[FEATURES_MODEL_B]
    y_val_b = df_val[TARGET_COL]
    
    model_b = XGBRegressor(
        n_estimators=300,
        learning_rate=0.04,
        max_depth=6,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        early_stopping_rounds=25
    )
    model_b.fit(
        X_train_b, y_train_b,
        eval_set=[(X_val_b, y_val_b)],
        verbose=False
    )
    
    joblib.dump(model_b, "models/pm25_xgboost_model_b.pkl")
    # Save default primary model
    joblib.dump(model_b, "models/pm25_xgboost.pkl")
    logging.info("Model B trained and saved to models/pm25_xgboost_model_b.pkl and models/pm25_xgboost.pkl")
    
    # Save test dataset for independent evaluation
    df_test.to_csv("data/processed/delhi_test_split.csv", index=False)
    
    return model_a, model_b, df_test

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train VayuNet AI PM2.5 forecasting models")
    parser.add_argument("--data", default="data/processed/delhi_master.csv", help="Master dataset path")
    args = parser.parse_args()
    
    train_models(args.data)
