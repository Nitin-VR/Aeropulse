/**
 * VayuNet AI — Sentinel-5P TROPOMI Delhi Data Extraction Script
 * Platform: Google Earth Engine (Code Editor: https://code.earthengine.google.com/)
 * 
 * Datasets:
 * 1. COPERNICUS/S5P/OFFL/L3_NO2 (Tropospheric NO2 Column Density - mol/m^2)
 * 2. COPERNICUS/S5P/OFFL/L3_AER_AI (UV Aerosol Index - absorbing_aerosol_index)
 * 
 * Purpose: Filter and extract daily/hourly aggregate satellite observations 
 * across Delhi NCR monitoring stations / grid points and export to CSV.
 */

// 1. Define Delhi Region of Interest (ROI) Bounding Box and Station Coordinates
var delhiBounds = ee.Geometry.Rectangle([76.84, 28.40, 77.35, 28.88]);

// Predefined prominent CPCB Station coordinates across Delhi
var cpcbStations = ee.FeatureCollection([
  ee.Feature(ee.Geometry.Point([77.3153, 28.6508]), {station_id: 'DL_ANAND_VIHAR', station_name: 'Anand Vihar'}),
  ee.Feature(ee.Geometry.Point([77.1333, 28.6700]), {station_id: 'DL_PUNJABI_BAGH', station_name: 'Punjabi Bagh'}),
  ee.Feature(ee.Geometry.Point([77.2410, 28.6289]), {station_id: 'DL_ITO', station_name: 'ITO'}),
  ee.Feature(ee.Geometry.Point([77.1706, 28.5631]), {station_id: 'DL_RK_PURAM', station_name: 'RK Puram'}),
  ee.Feature(ee.Geometry.Point([77.2272, 28.5918]), {station_id: 'DL_LODHI_ROAD', station_name: 'Lodhi Road'}),
  ee.Feature(ee.Geometry.Point([77.1651, 28.7325]), {station_id: 'DL_JAHANGIRPURI', station_name: 'Jahangirpuri'}),
  ee.Feature(ee.Geometry.Point([77.0689, 28.5921]), {station_id: 'DL_DWARKA_SEC8', station_name: 'Dwarka Sector 8'}),
  ee.Feature(ee.Geometry.Point([77.1158, 28.7328]), {station_id: 'DL_ROHINI', station_name: 'Rohini'}),
  ee.Feature(ee.Geometry.Point([77.0869, 28.5583]), {station_id: 'DL_IGI_AIRPORT', station_name: 'IGI Airport T3'}),
  ee.Feature(ee.Geometry.Point([77.0378, 28.7762]), {station_id: 'DL_BAWANA', station_name: 'Bawana'}),
  ee.Feature(ee.Geometry.Point([77.2713, 28.5307]), {station_id: 'DL_OKHLA_PH2', station_name: 'Okhla Phase 2'}),
  ee.Feature(ee.Geometry.Point([77.1994, 28.6364]), {station_id: 'DL_MANDIR_MARG', station_name: 'Mandir Marg'}),
  ee.Feature(ee.Geometry.Point([77.1578, 28.6514]), {station_id: 'DL_SHADIPUR', station_name: 'Shadipur'}),
  ee.Feature(ee.Geometry.Point([77.1190, 28.7501]), {station_id: 'DL_DTU', station_name: 'Delhi Tech Univ'}),
  ee.Feature(ee.Geometry.Point([77.3150, 28.6724]), {station_id: 'DL_VIVEK_VIHAR', station_name: 'Vivek Vihar'})
]);

// 2. Date Range Filter
var startDate = '2024-01-01';
var endDate = '2024-03-31';

// 3. Load Sentinel-5P Offline NO2 Collection
var no2Col = ee.ImageCollection('COPERNICUS/S5P/OFFL/L3_NO2')
  .filterBounds(delhiBounds)
  .filterDate(startDate, endDate)
  .select('tropospheric_NO2_column_number_density');

// 4. Load Sentinel-5P Offline UV Aerosol Index Collection
var aerCol = ee.ImageCollection('COPERNICUS/S5P/OFFL/L3_AER_AI')
  .filterBounds(delhiBounds)
  .filterDate(startDate, endDate)
  .select('absorbing_aerosol_index');

// 5. Visualizations on GEE Canvas
Map.centerObject(delhiBounds, 11);
var no2Vis = {
  min: 0,
  max: 0.0002,
  palette: ['black', 'blue', 'purple', 'cyan', 'green', 'yellow', 'red']
};
Map.addLayer(no2Col.mean().clip(delhiBounds), no2Vis, 'Sentinel-5P Mean NO2 (Delhi)');
Map.addLayer(cpcbStations, {color: 'FF0000'}, 'CPCB Monitoring Stations');

// 6. Extraction function: Sample Image at Station Locations with Timestamp
var sampleStations = function(image) {
  var dateStr = image.date().format('YYYY-MM-dd HH:mm:ss');
  return image.reduceRegions({
    collection: cpcbStations,
    reducer: ee.Reducer.mean(),
    scale: 1113 // Approximate TROPOMI spatial resolution (1.1 km)
  }).map(function(feat) {
    return feat.set('timestamp', dateStr);
  });
};

// Map over NO2 collection
var sampledNo2 = no2Col.map(sampleStations).flatten();

// 7. Export Extracted Satellite Data to Google Drive (Download and save to data/raw/sentinel5p/sentinel5p_delhi.csv)
Export.table.toDrive({
  collection: sampledNo2,
  description: 'Sentinel5P_Delhi_NO2_Export',
  folder: 'VayuNet_Data',
  fileNamePrefix: 'sentinel5p_delhi_no2',
  fileFormat: 'CSV',
  selectors: ['station_id', 'station_name', 'timestamp', 'mean', 'system:index']
});

print('GEE Sentinel-5P Delhi NO2 Extraction Task Initialized. Run tasks in Tasks Tab to export CSV.');
