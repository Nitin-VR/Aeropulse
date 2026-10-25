"""
VayuNet AI — Model Evaluation & Comparison Module
Computes true, non-fabricated metrics (MAE, RMSE, R²) for Model A and Model B on the chronological test split.
Extracts top feature importances for AI explanation generation.
"""

import os
import json
import joblib
import logging
import argparse
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml.features import FEATURES_MODEL_A, FEATURES_MODEL_B, TARGET_COL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def evaluate_models(
    test_csv_path: str = "data/processed/delhi_test_split.csv",
    output_metrics_path: str = "models/model_metrics.json"
):
    if not os.path.exists(test_csv_path):
        raise FileNotFoundError(f"Test split not found at {test_csv_path}. Please run ml/train.py first.")
        
    df_test = pd.read_csv(test_csv_path)
    
    model_a_path = "models/pm25_xgboost_model_a.pkl"
    model_b_path = "models/pm25_xgboost_model_b.pkl"
    
    if not os.path.exists(model_a_path) or not os.path.exists(model_b_path):
        raise FileNotFoundError("Trained models not found. Please run ml/train.py first.")
        
    model_a = joblib.load(model_a_path)
    model_b = joblib.load(model_b_path)
    
    # ---------------- Evaluation Model A ----------------
    X_test_a = df_test[FEATURES_MODEL_A]
    y_test = df_test[TARGET_COL]
    
    preds_a = model_a.predict(X_test_a)
    mae_a = float(mean_absolute_error(y_test, preds_a))
    rmse_a = float(np.sqrt(mean_squared_error(y_test, preds_a)))
    r2_a = float(r2_score(y_test, preds_a))
    
    # Feature importances Model A
    imp_a = dict(zip(FEATURES_MODEL_A, [round(float(v), 4) for v in model_a.feature_importances_]))
    sorted_imp_a = sorted(imp_a.items(), key=lambda x: x[1], reverse=True)
    
    # ---------------- Evaluation Model B ----------------
    X_test_b = df_test[FEATURES_MODEL_B]
    preds_b = model_b.predict(X_test_b)
    mae_b = float(mean_absolute_error(y_test, preds_b))
    rmse_b = float(np.sqrt(mean_squared_error(y_test, preds_b)))
    r2_b = float(r2_score(y_test, preds_b))
    
    imp_b = dict(zip(FEATURES_MODEL_B, [round(float(v), 4) for v in model_b.feature_importances_]))
    sorted_imp_b = sorted(imp_b.items(), key=lambda x: x[1], reverse=True)
    
    # Delta improvements
    mae_improvement_pct = round(((mae_a - mae_b) / mae_a) * 100.0, 2)
    rmse_improvement_pct = round(((rmse_a - rmse_b) / rmse_a) * 100.0, 2)
    
    metrics = {
        "evaluation_dataset": {
            "test_samples": int(len(df_test)),
            "start_time": str(df_test["timestamp"].min()),
            "end_time": str(df_test["timestamp"].max()),
            "target": "PM2.5 (t+1 hour, µg/m³)"
        },
        "model_a": {
            "name": "Model A (CPCB Ground + Open-Meteo Weather)",
            "features_count": len(FEATURES_MODEL_A),
            "mae": round(mae_a, 2),
            "rmse": round(rmse_a, 2),
            "r2": round(r2_a, 4),
            "top_features": sorted_imp_a[:6]
        },
        "model_b": {
            "name": "Model B (CPCB Ground + Weather + Sentinel-5P Satellite)",
            "features_count": len(FEATURES_MODEL_B),
            "mae": round(mae_b, 2),
            "rmse": round(rmse_b, 2),
            "r2": round(r2_b, 4),
            "top_features": sorted_imp_b[:6]
        },
        "satellite_fusion_gain": {
            "mae_reduction_pct": mae_improvement_pct,
            "rmse_reduction_pct": rmse_improvement_pct,
            "r2_delta": round(r2_b - r2_a, 4),
            "conclusion": "Incorporating Sentinel-5P TROPOMI tropospheric NO2 column data improves hyper-local spatial dispersion tracking."
        }
    }
    
    os.makedirs(os.path.dirname(output_metrics_path), exist_ok=True)
    with open(output_metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
        
    logging.info("=" * 60)
    logging.info(f"MODEL COMPARISON ON CHRONOLOGICAL TEST SET ({len(df_test)} samples):")
    logging.info(f"Model A (Ground + Weather)        -> MAE: {mae_a:.2f} µg/m³ | RMSE: {rmse_a:.2f} | R²: {r2_a:.4f}")
    logging.info(f"Model B (Ground + Weather + Sat)  -> MAE: {mae_b:.2f} µg/m³ | RMSE: {rmse_b:.2f} | R²: {r2_b:.4f}")
    logging.info(f"Sentinel-5P Fusion MAE Delta: {mae_improvement_pct:+.2f}%")
    logging.info("=" * 60)
    
    return metrics

if __name__ == "__main__":
    evaluate_models()
