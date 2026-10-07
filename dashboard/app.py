import os
import sys
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import folium
import streamlit as st
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

# Setup basic page config
st.set_page_config(page_title="OrbitalResQ Dashboard", page_icon="🌊", layout="wide")

# Correct paths relative to the dashboard directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "processed")

@st.cache_data
def load_damage_stats():
    """Load the calculated damage vectors."""
    b_file = os.path.join(DATA_DIR, "damaged_buildings.geojson")
    r_file = os.path.join(DATA_DIR, "damaged_roads.geojson")
    
    buildings = gpd.read_file(b_file) if os.path.exists(b_file) else gpd.GeoDataFrame()
    roads = gpd.read_file(r_file) if os.path.exists(r_file) else gpd.GeoDataFrame()
    return buildings, roads

@st.cache_data
def load_raster_bounds_and_image(mask_name="flood_class_mask.tiff"):
    """Load the raster mask and convert to RGBA for folium overlay."""
    mask_path = os.path.join(DATA_DIR, mask_name)
    if not os.path.exists(mask_path):
        return None, None
        
    with rasterio.open(mask_path) as src:
        bounds = src.bounds
        # Folium bounds are [[lat_min, lon_min], [lat_max, lon_max]]
        folium_bounds = [[bounds.bottom, bounds.left], [bounds.top, bounds.right]]
        
        # Read the mask
        data = src.read(1)
        
        # Create an RGBA image: 
        # 0 = dry (transparent), 1 = water (blue), 2 = debris (brown)
        rgba = np.zeros((data.shape[0], data.shape[1], 4), dtype=np.uint8)
        
        # Water: Blue with 60% opacity
        rgba[data == 1] = [30, 144, 255, 150]
        # Debris: Brown with 60% opacity
        rgba[data == 2] = [139, 69, 19, 150]
        
        # Fast downsample if the image is too large for the browser
        max_dim = 1500
        if rgba.shape[0] > max_dim or rgba.shape[1] > max_dim:
            import cv2
            scale = max_dim / max(rgba.shape[0], rgba.shape[1])
            new_shape = (int(rgba.shape[1]*scale), int(rgba.shape[0]*scale))
            rgba = cv2.resize(rgba, new_shape, interpolation=cv2.INTER_NEAREST)
            
        return rgba, folium_bounds

def main():
    st.title("🛰️ OrbitalResQ: AI Flood Damage Assessment")
    st.markdown("Automated Flood mapping using **Sentinel-1 SAR**, **FloodViT AI**, and **OpenStreetMap**.")
    
    st.sidebar.header("Navigation & Filters")
    layer_selection = st.sidebar.radio("Map View", ["Flood Mask", "Damaged Infrastructure"])
    
    # Load Data
    buildings, roads = load_damage_stats()
    rgba_img, map_bounds = load_raster_bounds_and_image("flood_class_mask.tiff")
    
    # ── KEY METRICS ──
    col1, col2, col3 = st.columns(3)
    col1.metric("Damaged Buildings", len(buildings))
    col2.metric("Flooded Road Segments", len(roads))
    
    if rgba_img is not None:
        water_px = np.sum((rgba_img[:,:,0] == 30) & (rgba_img[:,:,3] > 0))
        debris_px = np.sum((rgba_img[:,:,0] == 139) & (rgba_img[:,:,3] > 0))
        # Rough estimate based on 10m Sentinel resolution
        water_area_km2 = (water_px * 100) / 1e6
        col3.metric("Est. Flood Area (km²)", f"{water_area_km2:,.2f}")
    else:
        col3.metric("Est. Flood Area (km²)", "N/A")
    
    # ── MAP DISPLAY ──
    st.subheader("Interactive Map")
    
    # Initialize map centered on bounds
    if map_bounds:
        center_lat = (map_bounds[0][0] + map_bounds[1][0]) / 2
        center_lon = (map_bounds[0][1] + map_bounds[1][1]) / 2
        m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="CartoDB positron")
        
        # Fit bounds
        m.fit_bounds(map_bounds)
        
        if layer_selection == "Flood Mask" and rgba_img is not None:
            folium.raster_layers.ImageOverlay(
                image=rgba_img,
                bounds=map_bounds,
                opacity=0.7,
                name="AI Flood Prediction"
            ).add_to(m)
            
        elif layer_selection == "Damaged Infrastructure":
            # Add buildings
            if not buildings.empty:
                folium.GeoJson(
                    buildings,
                    name="Damaged Buildings",
                    style_function=lambda x: {'fillColor': 'red', 'color': 'red', 'weight': 1, 'fillOpacity': 0.7}
                ).add_to(m)
                
            # Add roads
            if not roads.empty:
                folium.GeoJson(
                    roads,
                    name="Flooded Roads",
                    style_function=lambda x: {'color': 'orange', 'weight': 3}
                ).add_to(m)
                
        folium.LayerControl().add_to(m)
        st_folium(m, width=1200, height=600)
    else:
        st.warning("Flood mask data not found. Please run the AI pipeline first.")

if __name__ == "__main__":
    main()
