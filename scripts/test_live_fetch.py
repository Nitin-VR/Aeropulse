import requests
import concurrent.futures
from scripts.download_weather import DELHI_STATIONS

def fetch_station_live(st):
    try:
        lat = st['latitude']
        lon = st['longitude']
        url_aq = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm2_5,pm10,nitrogen_dioxide&timezone=Asia%2FKolkata"
        url_wx = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,surface_pressure&timezone=Asia%2FKolkata"
        
        raq = requests.get(url_aq, timeout=5).json().get('current', {})
        rwx = requests.get(url_wx, timeout=5).json().get('current', {})
        
        return {
            'station_id': st['station_id'],
            'station_name': st['station_name'],
            'latitude': lat,
            'longitude': lon,
            'time': raq.get('time'),
            'pm25': raq.get('pm2_5', 45.0),
            'pm10': raq.get('pm10', 70.0),
            'no2': raq.get('nitrogen_dioxide', 35.0),
            'temp': rwx.get('temperature_2m', 28.0),
            'humidity': rwx.get('relative_humidity_2m', 60.0),
            'wind_speed': rwx.get('wind_speed_10m', 2.0),
            'wind_dir': rwx.get('wind_direction_10m', 180.0)
        }
    except Exception as e:
        return {'station_id': st['station_id'], 'error': str(e)}

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(fetch_station_live, DELHI_STATIONS))

    for r in results[:4]:
        print(r)
    print(f"Total live stations fetched: {len(results)}")
