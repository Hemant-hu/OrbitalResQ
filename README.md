# 🛰️ OrbitalResQ: AI Flood Damage Assessment System

**OrbitalResQ** is a satellite-based disaster response system built for the Copernicus Emergency Management Service (EMSR927) hackathon challenge. 

When roads, bridges, and phone lines are destroyed, this system uses **Sentinel-1 SAR radar imagery** (which sees through monsoon clouds), **OpenStreetMap**, and the **FloodViT** AI model to automatically map flood boundaries, calculate structural damage, and identify cut-off villages from space.

---

## 🚀 Features
1. **AI Flood Mapping:** Utilizes the `FloodViT` Vision Transformer model to detect flood water and debris.
2. **Structural Damage Assessment:** Spatially intersects the flood mask with pre-event OpenStreetMap building and road footprints.
3. **Network Connectivity Routing:** Analyzes the road graph to identify isolated settlements that have lost connection to the nearest hospital or town.
4. **MERN Interactive Dashboard:** A full-stack web application to visualize the AI predictions and infrastructure damage.

---

## 🛠️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/orbitalresq.git
cd orbitalresq
```

### 2. Install Dependencies
Make sure you have Python 3.10+ and Node.js installed.
```bash
# Install Python dependencies for the AI pipeline
pip install -r requirements.txt

# Install Backend dependencies
cd dashboard/backend
npm install

# Install Frontend dependencies
cd ../frontend
npm install
```

### 3. Download the Massive Data Files (CRITICAL)
Because GitHub cannot host files larger than 100MB, the satellite images and AI models are hosted externally. 

1. **Download the Data ZIP:** [Insert your Google Drive link here]
2. **Extract and place the files exactly as follows:**
   - Place `s1_pre.zip` and `s1_post.zip` inside the `data/raw/` folder.
   - Place `floodvit.pt` inside the `models/` folder.

---

## 🏃‍♂️ How to Run the System (End-to-End)

The entire system is designed to run automatically. You can start the AI pipeline and the web dashboards simultaneously by running:

### On Windows:
Double click the `run_all.bat` file, or run it in your terminal:
```cmd
run_all.bat
```

### Manual Execution:
If you prefer to run the steps manually:
1. **Run the AI Pipeline:** `python run_pipeline.py` (Outputs will save to `data/processed/`)
2. **Start Backend:** `cd dashboard/backend && npm start`
3. **Start Frontend:** `cd dashboard/frontend && npm run dev`

The interactive dashboard will be available at **http://localhost:5173**.

---

## ⚠️ Limitations & Technical Rules
* **SAR Angles:** We rely on Sentinel-1 radar images from the exact same orbit track (12 days apart) to perform valid change detection.
* **OpenStreetMap Constraints:** Following the rules, we only request historical OSM data from *before* the disaster (`2026-07-27`) to ensure no post-event edits leak into the damage assessment.
* **API Rate Limits:** The Overpass API is used to fetch the road network. If the bounding box is too large, it may timeout. The pipeline gracefully falls back to empty datasets to prevent crashing during these network outages.
