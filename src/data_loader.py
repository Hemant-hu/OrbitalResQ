"""
OrbitalResQ — Data Loader & Preprocessing
Extracts Sentinel-1 bands and fetches Ohsome API baseline data.
"""
import os
import glob
import zipfile
import xml.etree.ElementTree as ET
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_bounds
import requests
import geopandas as gpd
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

def extract_s1_bands(zip_path, extract_dir="data/processed", label="s1"):
    os.makedirs(extract_dir, exist_ok=True)
    extracted_files = {}
    with zipfile.ZipFile(zip_path, 'r') as z:
        for file in z.namelist():
            if 'measurement/s1d-iw-grd-vv' in file and file.endswith('.tiff'):
                target = os.path.join(extract_dir, f"{label}_vv.tiff")
                if not os.path.exists(target):
                    with open(target, 'wb') as f_out:
                        f_out.write(z.read(file))
                extracted_files['vv'] = target
            elif 'measurement/s1d-iw-grd-vh' in file and file.endswith('.tiff'):
                target = os.path.join(extract_dir, f"{label}_vh.tiff")
                if not os.path.exists(target):
                    with open(target, 'wb') as f_out:
                        f_out.write(z.read(file))
                extracted_files['vh'] = target
    return extracted_files

def get_s1_geolocation(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as z:
        xml_file = [f for f in z.namelist() if 'annotation/s1d-iw-grd-vv' in f and f.endswith('.xml')][0]
        xml_content = z.read(xml_file)
        
    root = ET.fromstring(xml_content)
    lats, lons = [], []
    for point in root.findall('.//geolocationGridPoint'):
        lats.append(float(point.find('latitude').text))
        lons.append(float(point.find('longitude').text))
        
    return min(lons), min(lats), max(lons), max(lats)

def fetch_osm_baseline(bbox, snapshot_date="2026-07-27"):
    """
    Fetch pre-flood buildings and roads from Ohsome API.
    Uses OHSOME_API_KEY from the environment if available.
    """
    url = "https://api.ohsome.org/v1/elements/geometry"
    
    api_key = os.getenv("OHSOME_API_KEY")
    headers = {
        "User-Agent": "OrbitalResQ-Bot/1.0 (Python/Requests)" # crucial to bypass WAF 403s!
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    def query_ohsome(filter_str):
        print(f"Querying ohsome API: {filter_str}...")
        data = {
            "bboxes": bbox,
            "time": snapshot_date,
            "filter": filter_str
        }
        resp = requests.post(url, data=data, headers=headers)
        if resp.status_code != 200:
            raise Exception(f"Ohsome API Error {resp.status_code}: {resp.text}")
            
        geojson = resp.json()
        if not geojson.get("features"):
            return gpd.GeoDataFrame(columns=['geometry'], crs="EPSG:4326")
            
        gdf = gpd.GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")
        return gdf

    buildings = query_ohsome("building=* and geometry:polygon")
    roads = query_ohsome("highway=* and geometry:line")
    
    return {"buildings": buildings, "roads": roads}

if __name__ == "__main__":
    pass
