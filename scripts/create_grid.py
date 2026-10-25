"""
VayuNet AI — Delhi Spatial Grid & IDW Interpolation Engine
Generates configurable regular latitude-longitude grid bounding Delhi NCR.
Applies Inverse Distance Weighting (IDW) interpolation from CPCB/Sensor stations
to calculate hyper-local predicted PM2.5, PM10, NO2 and Air Quality Risk Status across all cells.
Exports to GeoJSON and JSON formats for Leaflet heatmap/polygon visualization.
"""

import os
import json
import math
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple

# Delhi NCR Bounding Box coordinates
# [min_lat, max_lat, min_lon, max_lon]
DELHI_BOUNDS = {
    "min_lat": 28.40,
    "max_lat": 28.88,
    "min_lon": 76.84,
    "max_lon": 77.35
}

def get_risk_status(pm25: float) -> Tuple[str, str, str]:
    """
    Categorize PM2.5 into NAQI Risk Status, description and hex color.
    """
    if pm25 <= 30:
        return "Good", "Minimal impact", "#00e400"
    elif pm25 <= 60:
        return "Satisfactory", "Minor breathing discomfort to sensitive people", "#92d050"
    elif pm25 <= 90:
        return "Moderate", "Breathing discomfort to the people with lungs, asthma and heart diseases", "#ffff00"
    elif pm25 <= 120:
        return "Poor", "Breathing discomfort to most people on prolonged exposure", "#ff7e00"
    elif pm25 <= 250:
        return "Very Poor", "Respiratory illness on prolonged exposure", "#ff0000"
    else:
        return "Severe", "Affects healthy people and seriously impacts those with existing diseases", "#7e0023"

def inverse_distance_weighting(
    grid_points: np.ndarray, 
    known_coords: np.ndarray, 
    known_values: np.ndarray, 
    power: float = 2.0
) -> np.ndarray:
    """
    IDW Spatial Interpolation algorithm.
    grid_points: (N, 2) [lat, lon]
    known_coords: (M, 2) [lat, lon]
    known_values: (M,)
    power: distance weighting exponent (default 2)
    """
    N = grid_points.shape[0]
    M = known_coords.shape[0]
    interpolated = np.zeros(N)
    
    for i in range(N):
        p = grid_points[i]
        # Euclidean degree distance (or Haversine approximation in small box)
        dists = np.hypot(known_coords[:, 0] - p[0], known_coords[:, 1] - p[1])
        
        # Check for exact station location match
        exact_match = np.where(dists < 1e-6)[0]
        if len(exact_match) > 0:
            interpolated[i] = known_values[exact_match[0]]
        else:
            weights = 1.0 / (dists ** power)
            interpolated[i] = np.sum(weights * known_values) / np.sum(weights)
            
    return interpolated

def generate_delhi_grid(
    resolution_deg: float = 0.035, # approx ~3.5km x 3.5km cells for rapid rendering
    bounds: Dict[str, float] = DELHI_BOUNDS
) -> List[Dict[str, Any]]:
    """
    Create structured grid cells with bounding polygons and centroids over Delhi.
    """
    lats = np.arange(bounds["min_lat"], bounds["max_lat"] + resolution_deg * 0.5, resolution_deg)
    lons = np.arange(bounds["min_lon"], bounds["max_lon"] + resolution_deg * 0.5, resolution_deg)
    
    cells = []
    cell_idx = 1
    half = resolution_deg / 2.0
    
    for lat in lats:
        for lon in lons:
            cell_id = f"GRID_DL_{cell_idx:04d}"
            # Define polygon bounding box [SW, NW, NE, SE, SW]
            polygon = [
                [lat - half, lon - half],
                [lat + half, lon - half],
                [lat + half, lon + half],
                [lat - half, lon + half],
                [lat - half, lon - half]
            ]
            cells.append({
                "grid_id": cell_id,
                "latitude": round(float(lat), 4),
                "longitude": round(float(lon), 4),
                "bbox": [round(lat - half, 4), round(lon - half, 4), round(lat + half, 4), round(lon + half, 4)],
                "polygon": polygon
            })
            cell_idx += 1
            
    return cells

def interpolate_grid_pollution(
    station_data: List[Dict[str, Any]], 
    resolution_deg: float = 0.035
) -> Dict[str, Any]:
    """
    Interpolates station ground data onto Delhi grid.
    Returns GeoJSON FeatureCollection and list of cell objects.
    """
    grid_cells = generate_delhi_grid(resolution_deg=resolution_deg)
    
    if not station_data:
        return {"type": "FeatureCollection", "features": [], "cells": []}
        
    known_coords = np.array([[s["latitude"], s["longitude"]] for s in station_data])
    known_pm25 = np.array([float(s.get("PM2.5", 100.0)) for s in station_data])
    known_pm10 = np.array([float(s.get("PM10", 180.0)) for s in station_data])
    known_no2 = np.array([float(s.get("NO2", 40.0)) for s in station_data])
    
    grid_points = np.array([[c["latitude"], c["longitude"]] for c in grid_cells])
    
    interp_pm25 = inverse_distance_weighting(grid_points, known_coords, known_pm25)
    interp_pm10 = inverse_distance_weighting(grid_points, known_coords, known_pm10)
    interp_no2 = inverse_distance_weighting(grid_points, known_coords, known_no2)
    
    features = []
    enriched_cells = []
    
    for i, cell in enumerate(grid_cells):
        val_pm25 = round(float(interp_pm25[i]), 1)
        val_pm10 = round(float(interp_pm10[i]), 1)
        val_no2 = round(float(interp_no2[i]), 1)
        
        risk, desc, color = get_risk_status(val_pm25)
        
        cell_record = {
            "grid_id": cell["grid_id"],
            "latitude": cell["latitude"],
            "longitude": cell["longitude"],
            "predicted_PM2.5": val_pm25,
            "predicted_PM10": val_pm10,
            "predicted_NO2": val_no2,
            "risk_status": risk,
            "risk_description": desc,
            "color": color,
            "polygon": cell["polygon"]
        }
        enriched_cells.append(cell_record)
        
        # GeoJSON Polygon format: coordinates are [longitude, latitude]
        geo_poly = [[p[1], p[0]] for p in cell["polygon"]]
        feature = {
            "type": "Feature",
            "properties": {
                "grid_id": cell["grid_id"],
                "latitude": cell["latitude"],
                "longitude": cell["longitude"],
                "predicted_PM2.5": val_pm25,
                "predicted_PM10": val_pm10,
                "predicted_NO2": val_no2,
                "risk_status": risk,
                "color": color
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [geo_poly]
            }
        }
        features.append(feature)
        
    return {
        "type": "FeatureCollection",
        "features": features,
        "cells": enriched_cells
    }

if __name__ == "__main__":
    os.makedirs("data/grids", exist_ok=True)
    cells = generate_delhi_grid()
    print(f"Generated {len(cells)} Delhi grid cells.")
    with open("data/grids/delhi_grid_template.json", "w") as f:
        json.dump(cells, f, indent=2)
    print("Saved grid template to data/grids/delhi_grid_template.json")
