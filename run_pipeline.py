"""
OrbitalResQ — Master Pipeline Runner
Runs the entire system end-to-end: AI Inference -> Spatial Damage -> Network Routing.
Usage: python run_pipeline.py
"""
import sys
import os
import json
import numpy as np
import subprocess
import rasterio
from rasterio.windows import Window
from rasterio.transform import from_bounds
from rasterio.crs import CRS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kurosiwo_deps'))

from src.data_loader import extract_s1_bands, get_s1_geolocation
from src.segmentation import load_model, normalize_band, save_flood_mask

def load_band_crop(path, window):
    """Load only a specific window/crop of the raster to save RAM."""
    with rasterio.open(path) as ds:
        data = ds.read(1, window=window).astype(np.float32)
        profile = ds.profile.copy()
        # Update transform for the cropped window
        profile.update(
            width=window.width,
            height=window.height,
            transform=rasterio.windows.transform(window, ds.transform)
        )
        return data, profile

def run_ai_inference():
    print("=" * 60)
    print("  PHASE 1: AI FLOOD DETECTION (Optimized)")
    print("=" * 60)

    print("\n[1/5] Extracting Sentinel-1 bands...")
    s1_pre = extract_s1_bands("data/raw/s1_pre.zip", label="s1_pre")
    s1_post = extract_s1_bands("data/raw/s1_post.zip", label="s1_post")

    print("\n[2/5] Extracting geolocation metadata...")
    bbox_pre = get_s1_geolocation("data/raw/s1_pre.zip")
    bbox_post = get_s1_geolocation("data/raw/s1_post.zip")
    
    # We will compute the crop bounding box later, for now save the global one
    geo_meta = {
        "pre_event": {"bbox": list(bbox_pre), "date": "2026-08-24"},
        "post_event": {"bbox": list(bbox_post), "date": "2026-09-05"},
    }
    os.makedirs("data/processed", exist_ok=True)
    with open("data/processed/geolocation.json", "w") as f:
        json.dump(geo_meta, f, indent=2)

    print("\n[3/5] Loading center crop into memory (to save RAM)...")
    # First just open one to get dimensions
    with rasterio.open(s1_pre['vv']) as ds:
        h, w = ds.height, ds.width
        global_transform = ds.transform
        
    crop_size = 2240
    cy, cx = h // 2, w // 2
    window = Window(cx - crop_size//2, cy - crop_size//2, crop_size, crop_size)

    crop_pre_vv, profile = load_band_crop(s1_pre['vv'], window)
    crop_pre_vh, _ = load_band_crop(s1_pre['vh'], window)
    crop_post_vv, _ = load_band_crop(s1_post['vv'], window)
    crop_post_vh, _ = load_band_crop(s1_post['vh'], window)

    # Calculate actual bounds of this crop to fix geolocation
    crop_bounds = rasterio.windows.bounds(window, global_transform)
    # The XML gave us the global EPSG 4326 bounds, but the TIFF might have a different default transform. 
    # To be perfectly safe, we map the pixel crop to the global lat/lon bbox proportionally:
    lon_min, lat_min, lon_max, lat_max = bbox_pre
    d_lon = (lon_max - lon_min) / w
    d_lat = (lat_max - lat_min) / h
    
    crop_lon_min = lon_min + (cx - crop_size//2) * d_lon
    crop_lon_max = lon_min + (cx + crop_size//2) * d_lon
    crop_lat_min = lat_max - (cy + crop_size//2) * d_lat # lat decreases from top to bottom
    crop_lat_max = lat_max - (cy - crop_size//2) * d_lat
    
    profile.update(
        crs=CRS.from_epsg(4326), 
        transform=from_bounds(crop_lon_min, crop_lat_min, crop_lon_max, crop_lat_max, crop_size, crop_size)
    )

    print("\n[4/5] Skipping full-image SAR baseline (optimizing for speed & RAM).")

    print("\n[5/5] Running FloodViT AI inference...")
    import torch
    model = load_model("models/floodvit.pt", device="cpu")

    crop_pre_vv_n = normalize_band(crop_pre_vv)
    crop_pre_vh_n = normalize_band(crop_pre_vh)
    crop_post_vv_n = normalize_band(crop_post_vv)
    crop_post_vh_n = normalize_band(crop_post_vh)
    crop_pre_ratio = normalize_band(crop_pre_vv / (crop_pre_vh + 1e-8))
    crop_post_ratio = normalize_band(crop_post_vv / (crop_post_vh + 1e-8))

    tile_size = 224
    stride = 192
    vit_mask = np.zeros((3, crop_size, crop_size), dtype=np.float32)
    vit_counts = np.zeros((crop_size, crop_size), dtype=np.float32)

    for ty in range(0, crop_size - tile_size + 1, stride):
        for tx in range(0, crop_size - tile_size + 1, stride):
            tile = np.stack([
                crop_pre_vv_n[ty:ty+tile_size, tx:tx+tile_size],
                crop_pre_vh_n[ty:ty+tile_size, tx:tx+tile_size],
                crop_pre_ratio[ty:ty+tile_size, tx:tx+tile_size],
                crop_post_vv_n[ty:ty+tile_size, tx:tx+tile_size],
                crop_post_vh_n[ty:ty+tile_size, tx:tx+tile_size],
                crop_post_ratio[ty:ty+tile_size, tx:tx+tile_size],
            ], axis=0)

            tensor = torch.tensor(tile, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                output = model(tensor)
                prob = torch.softmax(output, dim=1).squeeze(0).cpu().numpy()

            vit_mask[:, ty:ty+tile_size, tx:tx+tile_size] += prob
            vit_counts[ty:ty+tile_size, tx:tx+tile_size] += 1

    for c in range(3): vit_mask[c] /= np.maximum(vit_counts, 1)
    class_mask = np.argmax(vit_mask, axis=0).astype(np.uint8)
    # -- NEW MULTI-MODAL FUSION LOGIC (SENTINEL-1 + SENTINEL-2) --
    print("\n[6/6] Multi-Modal Fusion (Integrating Sentinel-2 Optical Data)...")
    from src.data_loader import extract_s2_bands
    from src.segmentation import compute_optical_indices, fuse_masks
    
    # Extract Sentinel-2
    s2_post = extract_s2_bands("data/raw/s2_post.zip", label="s2_post")
    
    if 'green' in s2_post and 'nir' in s2_post and 'red' in s2_post:
        print("  Aligning Optical and Radar geometries...")
        from rasterio.warp import reproject, Resampling
        
        def load_s2_aligned(s2_path, dest_profile):
            with rasterio.open(s2_path) as src:
                dest_data = np.zeros((dest_profile['height'], dest_profile['width']), dtype=np.float32)
                reproject(
                    source=rasterio.band(src, 1),
                    destination=dest_data,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dest_profile['transform'],
                    dst_crs=dest_profile['crs'],
                    resampling=Resampling.bilinear
                )
                return dest_data

        crop_s2_green = load_s2_aligned(s2_post['green'], profile)
        crop_s2_red = load_s2_aligned(s2_post['red'], profile)
        crop_s2_nir = load_s2_aligned(s2_post['nir'], profile)
        
        # Simulated Cloud Cover Check (Normally derived from S2 Scene Classification Layer)
        # We assume 45% for this specific post-event date (partially clear)
        cloud_cover = 45 
        
        opt_water, opt_debris = compute_optical_indices(crop_s2_green, crop_s2_red, crop_s2_nir)
        final_class_mask = fuse_masks(class_mask, opt_water, opt_debris, cloud_cover_percent=cloud_cover)
    else:
        print("  Sentinel-2 10m JP2 bands not found in zip structure. Using SAR-only output.")
        final_class_mask = class_mask

    full_binary = (final_class_mask > 0).astype(np.uint8)

    save_flood_mask(full_binary, profile, "data/processed/flood_mask.tiff")
    save_flood_mask(final_class_mask, profile, "data/processed/flood_class_mask.tiff")
    print("Phase 1 Complete!\n")

def run_spatial_analysis():
    print("=" * 60)
    print("  PHASE 2: SPATIAL DAMAGE ANALYSIS")
    print("=" * 60)
    subprocess.run([sys.executable, "src/spatial_analysis.py"], check=True)
    print("Phase 2 Complete!\n")

def run_routing_analysis():
    print("=" * 60)
    print("  PHASE 3: NETWORK ROUTING (CUT-OFF VILLAGES)")
    print("=" * 60)
    subprocess.run([sys.executable, "src/routing.py"], check=True)
    print("Phase 3 Complete!\n")

def run_report_generation():
    print("=" * 60)
    print("  PHASE 4: AUTO-GENERATING SITUATION REPORT")
    print("=" * 60)
    subprocess.run([sys.executable, "src/report_generator.py"], check=True)
    print("Phase 4 Complete!\n")

if __name__ == "__main__":
    run_ai_inference()
    run_spatial_analysis()
    run_routing_analysis()
    run_report_generation()
    print("============================================================")
    print("  ORBITALRESQ PIPELINE FINISHED SUCCESSFULLY!")
    print("  All data is ready for the dashboard.")
    print("  Run: cd dashboard/backend && npm start")
    print("  Run: cd dashboard/frontend && npm run dev")
    print("============================================================")
