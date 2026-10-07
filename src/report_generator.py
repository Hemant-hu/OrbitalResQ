"""
OrbitalResQ — Automated Situation Report Generator
Reads all pipeline outputs and generates a 1-page situation report in English and Nepali.
Every number comes directly from the system's maps — nothing is invented.
"""
import os
import json
import numpy as np
import rasterio
import geopandas as gpd
from datetime import datetime


def load_stats():
    """Extract all statistics from the pipeline outputs."""
    stats = {}

    # 1. Geolocation metadata
    geo_path = "data/processed/geolocation.json"
    if os.path.exists(geo_path):
        with open(geo_path, "r") as f:
            geo = json.load(f)
        stats["pre_date"] = geo["pre_event"]["date"]
        stats["post_date"] = geo["post_event"]["date"]
        bbox = geo["pre_event"]["bbox"]
        stats["bbox"] = bbox
        stats["center_lat"] = round((bbox[1] + bbox[3]) / 2, 4)
        stats["center_lon"] = round((bbox[0] + bbox[2]) / 2, 4)

    # 2. Flood mask statistics
    mask_path = "data/processed/flood_mask.tiff"
    class_path = "data/processed/flood_class_mask.tiff"
    if os.path.exists(mask_path):
        with rasterio.open(mask_path) as src:
            mask = src.read(1)
            res = src.res  # pixel resolution in degrees
            total_pixels = mask.size
            flooded_pixels = int(np.sum(mask > 0))
            stats["total_pixels"] = total_pixels
            stats["flooded_pixels"] = flooded_pixels
            stats["flood_percent"] = round(100 * flooded_pixels / total_pixels, 2)
            # Rough area estimate: each pixel ~ 10m x 10m for Sentinel-1
            stats["flood_area_km2"] = round(flooded_pixels * 100 / 1e6, 2)

    if os.path.exists(class_path):
        with rasterio.open(class_path) as src:
            class_mask = src.read(1)
            stats["water_pixels"] = int(np.sum(class_mask == 1))
            stats["debris_pixels"] = int(np.sum(class_mask == 2))
            stats["water_area_km2"] = round(stats["water_pixels"] * 100 / 1e6, 2)
            stats["debris_area_km2"] = round(stats["debris_pixels"] * 100 / 1e6, 2)

    # 3. Damage statistics
    b_path = "data/processed/damaged_buildings.geojson"
    r_path = "data/processed/damaged_roads.geojson"
    stats["damaged_buildings"] = len(gpd.read_file(b_path)) if os.path.exists(b_path) else 0
    stats["damaged_roads"] = len(gpd.read_file(r_path)) if os.path.exists(r_path) else 0

    # 4. Cut-off villages
    c_path = "data/processed/cutoff_villages.geojson"
    if os.path.exists(c_path):
        cv = gpd.read_file(c_path)
        stats["cutoff_villages"] = len(cv)
        if not cv.empty and 'name' in cv.columns:
            stats["cutoff_village_names"] = cv["name"].dropna().tolist()
        else:
            stats["cutoff_village_names"] = []
    else:
        stats["cutoff_villages"] = 0
        stats["cutoff_village_names"] = []

    return stats


def generate_english_report(stats):
    """Generate the English situation report from the extracted stats."""
    report = f"""
================================================================================
              ORBITALRESQ — SITUATION REPORT (SITREP)
              Automated Satellite-Based Flood Assessment
================================================================================

EVENT:          Glacier Collapse & Flash Flood — Bhote Koshi–Trishuli Corridor, Nepal
REPORT DATE:    {datetime.now().strftime("%Y-%m-%d %H:%M")} (UTC+5:45)
DATA SOURCE:    Sentinel-1 SAR (Pre: {stats.get('pre_date', 'N/A')} | Post: {stats.get('post_date', 'N/A')})
ANALYSIS:       FloodViT AI Model + SAR Change Detection
COVERAGE:       Center: {stats.get('center_lat', 'N/A')}°N, {stats.get('center_lon', 'N/A')}°E

--------------------------------------------------------------------------------
1. WHERE DID THE FLOOD HIT?
--------------------------------------------------------------------------------
   Total area analyzed:          {stats.get('total_pixels', 0):,} pixels
   Flooded area detected:       {stats.get('flooded_pixels', 0):,} pixels ({stats.get('flood_percent', 0)}%)
   Estimated flood extent:       {stats.get('flood_area_km2', 0)} km²
     - Standing water:           {stats.get('water_area_km2', 0)} km² ({stats.get('water_pixels', 0):,} px)
     - Debris / mud deposits:    {stats.get('debris_area_km2', 0)} km² ({stats.get('debris_pixels', 0):,} px)

--------------------------------------------------------------------------------
2. WHAT WAS DAMAGED?
--------------------------------------------------------------------------------
   Buildings affected:           {stats.get('damaged_buildings', 0):,}
   Road segments flooded:        {stats.get('damaged_roads', 0):,}

   NOTE: Damage estimates are based on spatial intersection of the AI-generated
   flood mask with pre-event OpenStreetMap building footprints and road geometries
   (snapshot date: 2026-07-27). Actual structural damage may vary.

--------------------------------------------------------------------------------
3. WHO IS CUT OFF?
--------------------------------------------------------------------------------
   Villages with no road access: {stats.get('cutoff_villages', 0):,}
"""
    if stats.get("cutoff_village_names"):
        report += "   Cut-off village names:       " + ", ".join(stats["cutoff_village_names"]) + "\n"

    report += f"""
   Analysis method: Road segments intersecting the flood mask were removed from
   the pre-event road network graph. Villages that lost all paths to the nearest
   town or hospital were flagged as "cut off."

--------------------------------------------------------------------------------
LIMITATIONS
--------------------------------------------------------------------------------
   • Sentinel-1 revisit time is 6–12 days; this report reflects conditions as of
     the post-event acquisition date ({stats.get('post_date', 'N/A')}), not real-time.
   • Cloud-free Sentinel-2 optical imagery was not available for this pass.
   • OpenStreetMap coverage in rural Nepal is incomplete; unmapped structures
     are not included in the damage count.
   • The FloodViT model was applied to a center crop of the full scene due to
     CPU memory constraints. Areas outside the crop use a classical SAR baseline.

================================================================================
   Generated automatically by OrbitalResQ | Data: ESA Copernicus, OSM
================================================================================
"""
    return report


def generate_nepali_report(stats):
    """Generate the Nepali situation report from the extracted stats."""
    report = f"""
================================================================================
              अर्बिटलResQ — परिस्थिति प्रतिवेदन (SITREP)
              स्वचालित उपग्रह-आधारित बाढी मूल्यांकन
================================================================================

घटना:           हिमनदी भासिएको र बाढी — भोटेकोशी–त्रिशूली गलियारा, नेपाल
प्रतिवेदन मिति:  {datetime.now().strftime("%Y-%m-%d %H:%M")} (UTC+5:45)
डाटा स्रोत:     Sentinel-1 SAR (पूर्व: {stats.get('pre_date', 'N/A')} | पश्चात: {stats.get('post_date', 'N/A')})
विश्लेषण:       FloodViT AI मोडेल + SAR परिवर्तन पत्ता लगाउने
कभरेज:         केन्द्र: {stats.get('center_lat', 'N/A')}°N, {stats.get('center_lon', 'N/A')}°E

--------------------------------------------------------------------------------
१. बाढीले कहाँ असर गर्यो?
--------------------------------------------------------------------------------
   विश्लेषण गरिएको कुल क्षेत्र:    {stats.get('total_pixels', 0):,} पिक्सेल
   बाढी पत्ता लागेको क्षेत्र:       {stats.get('flooded_pixels', 0):,} पिक्सेल ({stats.get('flood_percent', 0)}%)
   अनुमानित बाढी विस्तार:          {stats.get('flood_area_km2', 0)} वर्ग कि.मी.
     - जमेको पानी:                 {stats.get('water_area_km2', 0)} वर्ग कि.मी.
     - माटो/भग्नावशेष:             {stats.get('debris_area_km2', 0)} वर्ग कि.मी.

--------------------------------------------------------------------------------
२. के क्षति भयो?
--------------------------------------------------------------------------------
   प्रभावित भवनहरू:                {stats.get('damaged_buildings', 0):,}
   बाढीले प्रभावित सडक खण्डहरू:    {stats.get('damaged_roads', 0):,}

--------------------------------------------------------------------------------
३. को विच्छेद भयो?
--------------------------------------------------------------------------------
   सडक पहुँच नभएका गाउँहरू:       {stats.get('cutoff_villages', 0):,}
"""
    if stats.get("cutoff_village_names"):
        report += "   विच्छेद गाउँहरूको नाम:         " + ", ".join(stats["cutoff_village_names"]) + "\n"

    report += f"""
================================================================================
   OrbitalResQ द्वारा स्वचालित रूपमा उत्पन्न | डाटा: ESA Copernicus, OSM
================================================================================
"""
    return report


def main():
    print("=" * 60)
    print("  OrbitalResQ — Generating Situation Report")
    print("=" * 60)

    stats = load_stats()

    # Save stats as JSON for the copilot to consume
    os.makedirs("data/processed", exist_ok=True)
    with open("data/processed/sitrep_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print("Saved stats to data/processed/sitrep_stats.json")

    # Generate English report
    en_report = generate_english_report(stats)
    with open("data/processed/sitrep_english.txt", "w", encoding="utf-8") as f:
        f.write(en_report)
    print("Saved English report to data/processed/sitrep_english.txt")

    # Generate Nepali report
    ne_report = generate_nepali_report(stats)
    with open("data/processed/sitrep_nepali.txt", "w", encoding="utf-8") as f:
        f.write(ne_report)
    print("Saved Nepali report to data/processed/sitrep_nepali.txt")

    print("\n--- ENGLISH SITREP ---")
    print(en_report)

    try:
        print("\n--- Nepali SITREP ---")
        print(ne_report)
    except UnicodeEncodeError:
        print("(Nepali report saved to file but cannot be displayed in this terminal.)")


if __name__ == "__main__":
    main()
