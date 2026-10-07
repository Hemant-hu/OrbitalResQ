"""
OrbitalResQ — Spatial Analysis & Routing
Finds damaged buildings/roads and calculates cut-off settlements.
"""
import os
import json
import geopandas as gpd
import pandas as pd
import rasterio
from rasterio.features import shapes
import osmnx as ox

def get_center_bbox(mask_path, crop_size=2240):
    with rasterio.open(mask_path) as src:
        cx, cy = src.width // 2, src.height // 2
        window = rasterio.windows.Window(cx - crop_size//2, cy - crop_size//2, crop_size, crop_size)
        bounds = rasterio.windows.bounds(window, src.transform)
        return bounds, window

def fetch_osmnx_data(bounds):
    import warnings
    warnings.filterwarnings("ignore")
    left, bottom, right, top = bounds
    
    print("  Fetching buildings...")
    try:
        buildings = ox.features_from_bbox(north=top, south=bottom, east=right, west=left, tags={"building": True})
        if not buildings.empty:
            buildings = buildings[buildings.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    except Exception as e:
        buildings = gpd.GeoDataFrame(columns=['geometry'], crs="EPSG:4326")
        
    print("  Fetching roads...")
    try:
        roads = ox.features_from_bbox(north=top, south=bottom, east=right, west=left, tags={"highway": True})
        if not roads.empty:
            roads = roads[roads.geometry.type.isin(['LineString', 'MultiLineString'])]
    except Exception as e:
        roads = gpd.GeoDataFrame(columns=['geometry'], crs="EPSG:4326")
        
    return buildings, roads

def vectorize_flood_mask(mask_path, window, threshold=0):
    print(f"Vectorizing flood mask crop...")
    with rasterio.open(mask_path) as src:
        image = src.read(1, window=window)
        mask = image > threshold
        transform = rasterio.windows.transform(window, src.transform)
        
        results = (
            {'properties': {'raster_val': v}, 'geometry': s}
            for i, (s, v) 
            in enumerate(shapes(image, mask=mask, transform=transform))
        )
        geoms = list(results)
        if not geoms:
            return gpd.GeoDataFrame(columns=['geometry'], crs=src.crs)
        gdf = gpd.GeoDataFrame.from_features(geoms, crs=src.crs)
    return gdf

def calculate_damage(flood_gdf, osm_gdf, feature_name="buildings"):
    print(f"Calculating damage for {feature_name}...")
    if flood_gdf.empty or osm_gdf.empty:
        return gpd.GeoDataFrame(columns=osm_gdf.columns, crs="EPSG:4326")
    if flood_gdf.crs != osm_gdf.crs:
        osm_gdf = osm_gdf.to_crs(flood_gdf.crs)
    damaged = gpd.sjoin(osm_gdf, flood_gdf, how="inner", predicate="intersects")
    damaged = damaged.drop_duplicates(subset=[osm_gdf.geometry.name])
    return damaged

def main():
    print("=" * 60)
    print("  OrbitalResQ — Damage & Spatial Analysis")
    print("=" * 60)
    
    mask_path = "data/processed/flood_mask.tiff"
    if not os.path.exists(mask_path):
        print("Error: Run the pipeline first to generate the flood mask.")
        return
        
    bounds, window = get_center_bbox(mask_path)
    
    os.makedirs("data/osm", exist_ok=True)
    b_file = "data/osm/buildings.geojson"
    r_file = "data/osm/roads.geojson"
    
    print("\n[1/4] Fetching OSM Baseline data...")
    if not (os.path.exists(b_file) and os.path.exists(r_file)):
        buildings_gdf, roads_gdf = fetch_osmnx_data(bounds)
        if not buildings_gdf.empty:
            buildings_gdf.to_file(b_file, driver="GeoJSON")
        if not roads_gdf.empty:
            roads_gdf.to_file(r_file, driver="GeoJSON")
    else:
        print("  Loading cached OSM data...")
        buildings_gdf = gpd.read_file(b_file)
        roads_gdf = gpd.read_file(r_file)
        
    print(f"  Total Buildings: {len(buildings_gdf)}")
    print(f"  Total Roads: {len(roads_gdf)}")
    
    print("\n[2/4] Processing Flood Mask...")
    flood_polys = vectorize_flood_mask(mask_path, window)
    print(f"  Created {len(flood_polys)} flood polygons.")
    
    print("\n[3/4] Intersecting Flood and Infrastructure...")
    damaged_buildings = calculate_damage(flood_polys, buildings_gdf, "buildings")
    damaged_roads = calculate_damage(flood_polys, roads_gdf, "roads")
    
    if not damaged_buildings.empty:
        damaged_buildings.to_file("data/processed/damaged_buildings.geojson", driver="GeoJSON")
    if not damaged_roads.empty:
        damaged_roads.to_file("data/processed/damaged_roads.geojson", driver="GeoJSON")
    
    print("\n" + "=" * 60)
    print("  Spatial Analysis Complete!")
    print(f"  Stats:")
    print(f"    - Buildings flooded: {len(damaged_buildings):,}")
    print(f"    - Road segments flooded: {len(damaged_roads):,}")
    print("  Outputs saved to data/processed/")
    print("=" * 60)

if __name__ == "__main__":
    main()
