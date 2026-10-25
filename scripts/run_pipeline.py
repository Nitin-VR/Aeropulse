"""
VayuNet AI — End-to-End Pipeline Orchestrator
Executes the full pipeline:
1. Generate / Verify Raw Datasets (CPCB, Weather, Sentinel-5P)
2. Preprocessing & Data Fusion -> delhi_master.csv
3. Feature Engineering & Chronological Train/Val/Test Split
4. Model Training (Model A & Model B XGBoost) & Anomaly Isolation Forest
5. Genuine Model Evaluation (MAE, RMSE, R²)
6. Grid Generation & IDW Spatial Interpolation
"""

import os
import sys
import logging

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def run_full_pipeline():
    logging.info(">>> STEP 1: Checking Raw Datasets...")
    cpcb_file = "data/raw/cpcb/delhi_cpcb_stations.csv"
    if not os.path.exists(cpcb_file):
        logging.info("Raw datasets not found. Generating realistic benchmark demo data...")
        from scripts.generate_sample_data import generate_realistic_delhi_dataset
        generate_realistic_delhi_dataset()
    else:
        logging.info(f"Found existing raw data in {cpcb_file}")
        
    logging.info(">>> STEP 2: Preprocessing & Merging Master Dataset...")
    from ml.preprocessing import merge_and_clean_datasets
    df_master = merge_and_clean_datasets("data/processed/delhi_master.csv")
    logging.info(f"Master dataset created with {len(df_master)} rows.")
    
    logging.info(">>> STEP 3: Training Forecasting Models (Model A vs Model B) & Anomaly Detector...")
    from ml.train import train_models
    train_models("data/processed/delhi_master.csv")
    
    logging.info(">>> STEP 4: Evaluating Models & Generating Honest Comparison Metrics...")
    from ml.evaluate import evaluate_models
    metrics = evaluate_models()
    
    logging.info(">>> STEP 5: Pre-calculating Delhi Spatial Grid & IDW Template...")
    from scripts.create_grid import generate_delhi_grid
    os.makedirs("data/grids", exist_ok=True)
    generate_delhi_grid()
    
    logging.info("=" * 60)
    logging.info("VAYUNET AI PHASE 1 PIPELINE COMPLETED SUCCESSFULLY!")
    logging.info("=" * 60)

if __name__ == "__main__":
    run_full_pipeline()
