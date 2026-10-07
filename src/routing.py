"""
OrbitalResQ — Network Routing & Cut-off Analysis
Identifies villages that have lost road connections to hospitals/towns due to flooding.
"""
import os
import json
import warnings
import geopandas as gpd
import networkx as nx
import osmnx as ox
import rasterio
from rasterio.features import shapes

warnings.filterwarnings("ignore")

def get_crop_bounds(mask_path):
    """Load the bounding box directly from the cropped TIFF to avoid downloading the whole country."""
    with rasterio.open(mask_path) as src:
        bounds = src.bounds
        return bounds.left, bounds.bottom, bounds.right, bounds.top

def vectorize_flood_mask(mask_path):
    print("Vectorizing flood mask...")
    with rasterio.open(mask_path) as src:
        image = src.read(1)
        mask = image > 0
        results = (
            {'properties': {'raster_val': v}, 'geometry': s}
            for i, (s, v) in enumerate(shapes(image, mask=mask, transform=src.transform))
        )
        geoms = list(results)
        if not geoms:
            return gpd.GeoDataFrame(columns=['geometry'], crs=src.crs)
        return gpd.GeoDataFrame.from_features(geoms, crs=src.crs)

def main():
    print("=" * 60)
    print("  OrbitalResQ — Network Routing Analysis")
    print("=" * 60)
    
    mask_path = "data/processed/flood_mask.tiff"
    if not os.path.exists(mask_path):
        print("Error: flood_mask.tiff not found.")
        return

    # Increase timeout for the OSM API and use correct formatting string
    ox.settings.timeout = 300
    ox.settings.overpass_settings = '[out:json][timeout:{timeout}][date:"2026-07-27T00:00:00Z"]'
    
    # Get bounds strictly for the small crop, not the whole image
    min_lon, min_lat, max_lon, max_lat = get_crop_bounds(mask_path)
    bbox = (min_lon, min_lat, max_lon, max_lat)
    
    print(f"\n[1/4] Fetching pre-flood road network for crop bounds: {bbox}...")
    try:
        G = ox.graph_from_bbox(bbox, network_type='drive')
    except Exception as e:
        print(f"  Warning: Could not fetch graph: {e}")
        G = nx.MultiDiGraph()
        
    print(f"  Fetched {len(G.nodes)} nodes and {len(G.edges)} edges.")

    print("\n[2/4] Fetching towns, villages, and hospitals...")
    tags = {'place': ['village', 'town', 'city'], 'amenity': ['hospital', 'clinic']}
    try:
        pois = ox.features_from_bbox(bbox, tags=tags)
        pois['geometry'] = pois['geometry'].centroid
    except Exception as e:
        print(f"  Warning: Could not fetch POIs: {e}")
        pois = gpd.GeoDataFrame(columns=['geometry', 'place', 'amenity', 'name'], crs="EPSG:4326")

    print(f"  Found {len(pois)} critical locations.")

    is_hub = pois['place'].isin(['town', 'city']) | pois['amenity'].isin(['hospital', 'clinic'])
    is_village = pois['place'] == 'village'
    
    hubs = pois[is_hub]
    villages = pois[is_village]
    
    print(f"  Identified {len(hubs)} hubs and {len(villages)} villages.")

    if len(G.nodes) == 0 or len(villages) == 0 or len(hubs) == 0:
        print("\n  [Skip] Not enough data in this bounding box.")
        gpd.GeoDataFrame(columns=['geometry']).to_file("data/processed/cutoff_villages.geojson", driver="GeoJSON")
        return

    print("\n[3/4] Intersecting network with flood mask...")
    flood_gdf = vectorize_flood_mask(mask_path)
    nodes, edges = ox.graph_to_gdfs(G)
    
    if flood_gdf.crs != edges.crs:
        flood_gdf = flood_gdf.to_crs(edges.crs)
        
    flooded_edges = gpd.sjoin(edges, flood_gdf, how="inner", predicate="intersects")
    flooded_edge_ids = flooded_edges.index.tolist()
    
    print(f"  Found {len(flooded_edge_ids)} road segments destroyed.")
    
    G_post = G.copy()
    for u, v, key in flooded_edge_ids:
        if G_post.has_edge(u, v, key):
            G_post.remove_edge(u, v, key)
            
    print("\n[4/4] Analyzing connectivity...")
    hub_nodes = ox.distance.nearest_nodes(G, X=hubs.geometry.x, Y=hubs.geometry.y)
    village_nodes = ox.distance.nearest_nodes(G, X=villages.geometry.x, Y=villages.geometry.y)
    
    G_undir = G_post.to_undirected()
    components = list(nx.connected_components(G_undir))
    
    safe_villages = []
    cutoff_villages = []
    
    for i, v_node in enumerate(village_nodes):
        village_geom = villages.iloc[i]
        village_comp = next((comp for comp in components if v_node in comp), None)
                
        is_safe = any(h_node in village_comp for h_node in hub_nodes) if village_comp else False
                    
        if is_safe: safe_villages.append(village_geom)
        else: cutoff_villages.append(village_geom)
            
    print(f"  Results: {len(safe_villages)} safe, {len(cutoff_villages)} CUT OFF.")
    
    if cutoff_villages:
        gpd.GeoDataFrame(cutoff_villages, crs=villages.crs).to_file("data/processed/cutoff_villages.geojson", driver="GeoJSON")
    else:
        gpd.GeoDataFrame(columns=['geometry']).to_file("data/processed/cutoff_villages.geojson", driver="GeoJSON")

    print("  Outputs saved to data/processed/cutoff_villages.geojson")

if __name__ == "__main__":
    main()
