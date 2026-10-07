@echo off
echo ============================================================
echo   OrbitalResQ: End-to-End Startup Script
echo ============================================================

echo.
echo [1/3] Running Python Data & AI Pipeline...
echo This will take raw satellite images, detect floods, calculate damage, and route cut-off villages.
set PYTHONPATH=.
python run_pipeline.py
if %errorlevel% neq 0 (
    echo AI Pipeline failed! Exiting...
    pause
    exit /b %errorlevel%
)

echo.
echo [2/3] Generating Web Assets...
python -c "import os, json, numpy as np, rasterio, cv2, shutil; from PIL import Image; out='dashboard/backend/public'; os.makedirs(out, exist_ok=True); src_file='data/processed/flood_class_mask.tiff'; (ds := rasterio.open(src_file)); bounds=ds.bounds; json.dump([[bounds.bottom, bounds.left], [bounds.top, bounds.right]], open(os.path.join(out, 'bounds.json'), 'w')); data=ds.read(1); rgba=np.zeros((data.shape[0], data.shape[1], 4), dtype=np.uint8); rgba[data == 1] = [30, 144, 255, 180]; rgba[data == 2] = [139, 69, 19, 180]; (scale := 2000 / max(rgba.shape[0], rgba.shape[1])) if max(rgba.shape[0], rgba.shape[1]) > 2000 else 1; rgba = cv2.resize(rgba, (int(rgba.shape[1]*scale), int(rgba.shape[0]*scale)), interpolation=cv2.INTER_NEAREST) if scale < 1 else rgba; Image.fromarray(rgba).save(os.path.join(out, 'flood_overlay.png')); [shutil.copy(f'data/processed/{f}', os.path.join(out, f)) for f in ['damaged_buildings.geojson', 'damaged_roads.geojson', 'cutoff_villages.geojson'] if os.path.exists(f'data/processed/{f}')]"

echo.
echo [3/3] Starting MERN Dashboard...
echo Starting Express Backend...
start cmd /k "cd dashboard\backend && npm start"

echo Starting React Frontend...
start cmd /k "cd dashboard\frontend && npm run dev"

echo.
echo ============================================================
echo   System is live!
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:5000
echo ============================================================
pause
