"""
OrbitalResQ — Flood Segmentation (Inference Only)
Uses pre-trained FloodViT model (floodvit.pt) on CPU.
Model expects: 6-channel 224x224 input (pre_VV, pre_VH, pre_ratio, post_VV, post_VH, post_ratio)
Model outputs: 3-class segmentation (no-flood, flood-water, flood-debris)
"""
import os
import sys
import numpy as np
import torch
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS

# Add kurosiwo_deps to path so torch.load can find the model classes
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kurosiwo_deps'))


def load_model(model_path="models/floodvit.pt", device="cpu"):
    """Load the pre-trained FloodViT model for inference."""
    print(f"Loading FloodViT from {model_path} on {device}...")
    model = torch.load(model_path, map_location=device, weights_only=False)
    model.eval()
    print(f"  Model loaded: {type(model).__name__}")
    return model


def load_s1_pair(pre_vv_path, pre_vh_path, post_vv_path, post_vh_path):
    """
    Load Sentinel-1 VV and VH bands for pre and post event.
    Returns numpy arrays and the rasterio profile for saving results.
    """
    with rasterio.open(pre_vv_path) as ds:
        pre_vv = ds.read(1).astype(np.float32)
        profile = ds.profile.copy()
        transform = ds.transform
        crs = ds.crs
        bounds = ds.bounds
    with rasterio.open(pre_vh_path) as ds:
        pre_vh = ds.read(1).astype(np.float32)
    with rasterio.open(post_vv_path) as ds:
        post_vv = ds.read(1).astype(np.float32)
    with rasterio.open(post_vh_path) as ds:
        post_vh = ds.read(1).astype(np.float32)

    return pre_vv, pre_vh, post_vv, post_vh, profile


def normalize_band(band):
    """Min-max normalize a single band to [0, 1], handling nodata."""
    valid = band[band > 0]
    if len(valid) == 0:
        return np.zeros_like(band, dtype=np.float32)
    vmin, vmax = np.percentile(valid, [2, 98])
    normed = (band - vmin) / (vmax - vmin + 1e-8)
    return np.clip(normed, 0, 1).astype(np.float32)


def predict_flood_mask_tiled(model, pre_vv, pre_vh, post_vv, post_vh,
                              tile_size=224, overlap=32, device="cpu"):
    """
    Run inference in 224x224 tiles across the full image.
    
    FloodViT expects 6-channel input:
      [pre_VV, pre_VH, pre_VV/VH_ratio, post_VV, post_VH, post_VV/VH_ratio]
    
    FloodViT outputs 3 classes:
      0 = no flood, 1 = flood water, 2 = flood debris
    """
    h, w = pre_vv.shape
    stride = tile_size - overlap

    # Output: 3-class probability map
    mask = np.zeros((3, h, w), dtype=np.float32)
    counts = np.zeros((h, w), dtype=np.float32)

    # Normalize all bands
    pre_vv_n = normalize_band(pre_vv)
    pre_vh_n = normalize_band(pre_vh)
    post_vv_n = normalize_band(post_vv)
    post_vh_n = normalize_band(post_vh)

    # Compute VV/VH ratio bands
    pre_ratio = normalize_band(pre_vv / (pre_vh + 1e-8))
    post_ratio = normalize_band(post_vv / (post_vh + 1e-8))

    total_y = max(1, (h - tile_size) // stride + 1)
    total_x = max(1, (w - tile_size) // stride + 1)
    total_tiles = total_y * total_x
    tile_count = 0

    print(f"Running tiled inference: {h}x{w} image, tile_size={tile_size}, stride={stride}")
    print(f"Estimated tiles: ~{total_tiles}")

    for y in range(0, h - tile_size + 1, stride):
        for x in range(0, w - tile_size + 1, stride):
            y_end = y + tile_size
            x_end = x + tile_size

            # Stack 6 channels: [pre_VV, pre_VH, pre_ratio, post_VV, post_VH, post_ratio]
            tile = np.stack([
                pre_vv_n[y:y_end, x:x_end],
                pre_vh_n[y:y_end, x:x_end],
                pre_ratio[y:y_end, x:x_end],
                post_vv_n[y:y_end, x:x_end],
                post_vh_n[y:y_end, x:x_end],
                post_ratio[y:y_end, x:x_end],
            ], axis=0)  # Shape: [6, 224, 224]

            tensor = torch.tensor(tile, dtype=torch.float32).unsqueeze(0).to(device)

            with torch.no_grad():
                output = model(tensor)  # Shape: [1, 3, 224, 224]
                prob = torch.softmax(output, dim=1).squeeze(0).cpu().numpy()  # [3, 224, 224]

            mask[:, y:y_end, x:x_end] += prob
            counts[y:y_end, x:x_end] += 1

            tile_count += 1
            if tile_count % 200 == 0:
                pct = 100 * tile_count / total_tiles
                print(f"  [{pct:.1f}%] Processed {tile_count}/{total_tiles} tiles...")

    # Average overlapping regions
    counts_safe = np.maximum(counts, 1)
    for c in range(3):
        mask[c] = mask[c] / counts_safe

    # Argmax to get class labels: 0=no flood, 1=water, 2=debris
    class_mask = np.argmax(mask, axis=0).astype(np.uint8)

    # Binary flood mask: anything that is NOT class 0
    binary_mask = (class_mask > 0).astype(np.uint8)

    flood_pixels = binary_mask.sum()
    total_pixels = binary_mask.size
    print(f"\nInference complete!")
    print(f"  Flooded pixels: {flood_pixels:,} / {total_pixels:,} ({100*flood_pixels/total_pixels:.2f}%)")
    print(f"  Water pixels (class 1): {(class_mask==1).sum():,}")
    print(f"  Debris pixels (class 2): {(class_mask==2).sum():,}")

    return binary_mask, class_mask, mask


def save_flood_mask(mask_data, reference_profile, output_path, num_bands=1):
    """Save a mask as a GeoTIFF using the reference image's geotransform."""
    profile = reference_profile.copy()
    profile.update(dtype=rasterio.uint8, count=num_bands, compress='lz4')

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with rasterio.open(output_path, 'w', **profile) as dst:
        if num_bands == 1:
            dst.write(mask_data.astype(np.uint8), 1)
        else:
            for i in range(num_bands):
                dst.write(mask_data[i].astype(np.uint8), i + 1)

    print(f"Saved: {output_path}")
    return output_path





# ──────────────────────────────────────────────
# MULTI-MODAL SENSOR FUSION (Sentinel-1 + Sentinel-2)
# ──────────────────────────────────────────────
def compute_optical_indices(green_band, red_band, nir_band):
    """
    Computes NDWI for Water and NDDI-like index for Debris/Mud.
    Returns binary masks for optical water and optical debris.
    """
    print("  Calculating Sentinel-2 Optical Indices (NDWI/NDDI)...")
    eps = 1e-8
    
    # NDWI (Water) = (Green - NIR) / (Green + NIR)
    ndwi = (green_band - nir_band) / (green_band + nir_band + eps)
    optical_water = (ndwi > 0.1).astype(np.uint8)
    
    # Debris index (Simplified NDDI/Mud index)
    nddi = (green_band - red_band) / (green_band + red_band + eps)
    optical_debris = ((nddi > 0.05) & (nir_band > 1000)).astype(np.uint8) # High reflectance + soil signature
    
    return optical_water, optical_debris

def fuse_masks(sar_class_mask, optical_water, optical_debris, cloud_cover_percent):
    """
    Fuses Sentinel-1 AI Mask with Sentinel-2 Optical Mask.
    If cloud cover is > 60%, trusts SAR completely.
    Otherwise, uses Optical to enhance the SAR mask.
    """
    fused_mask = sar_class_mask.copy()
    
    if cloud_cover_percent > 60:
        print(f"  [Fusion] High cloud cover ({cloud_cover_percent}%). Trusting Sentinel-1 Radar completely.")
        return fused_mask
        
    print(f"  [Fusion] Clear sky ({cloud_cover_percent}% clouds). Fusing S1 AI with S2 Optical data.")
    
    # 1: Water, 2: Debris
    # Enhance water detection where optical strongly agrees, or finds new water
    fused_mask[(optical_water == 1) & (fused_mask == 0)] = 1
    
    # Enhance debris detection
    fused_mask[(optical_debris == 1) & (fused_mask == 0)] = 2
    
    return fused_mask


# ──────────────────────────────────────────────
# SIMPLE CHANGE DETECTION (Fallback / Baseline)
# ──────────────────────────────────────────────
def simple_change_detection(pre_vv, pre_vh, post_vv, post_vh, threshold=0.3):
    """
    Classical SAR change detection as a fallback/baseline.
    Uses log-ratio of VV and VH intensities between pre and post.
    """
    print("Running simple SAR change detection (log-ratio method)...")

    eps = 1e-6
    pre_vv_db = 10 * np.log10(pre_vv.astype(np.float64) + eps)
    post_vv_db = 10 * np.log10(post_vv.astype(np.float64) + eps)
    pre_vh_db = 10 * np.log10(pre_vh.astype(np.float64) + eps)
    post_vh_db = 10 * np.log10(post_vh.astype(np.float64) + eps)

    ratio_vv = post_vv_db - pre_vv_db
    ratio_vh = post_vh_db - pre_vh_db
    change = (ratio_vv + ratio_vh) / 2
    change_norm = normalize_band(-change)
    flood_mask = (change_norm > threshold).astype(np.uint8)

    print(f"  Flooded pixels: {flood_mask.sum():,} / {flood_mask.size:,} "
          f"({100 * flood_mask.sum() / flood_mask.size:.2f}%)")

    return flood_mask, change_norm


if __name__ == "__main__":
    print("Segmentation module ready.")
    print("FloodViT expects: 6-ch 224x224 input → 3-class output")
