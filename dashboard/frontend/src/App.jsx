import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, ImageOverlay, GeoJSON } from 'react-leaflet';
import axios from 'axios';
import 'leaflet/dist/leaflet.css';
import './App.css';

function App() {
  const [config, setConfig] = useState(null);
  const [buildings, setBuildings] = useState(null);
  const [roads, setRoads] = useState(null);

  useEffect(() => {
    // Fetch Map config (bounds and layer paths)
    axios.get('http://localhost:5000/api/config')
      .then(res => {
        if (res.data.status === 'success') {
          setConfig(res.data);
          
          // Fetch GeoJSON data based on paths
          if (res.data.layers.buildings) {
            axios.get(`http://localhost:5000${res.data.layers.buildings}`)
              .then(bRes => setBuildings(bRes.data))
              .catch(err => console.error('No buildings data', err));
          }
          if (res.data.layers.roads) {
            axios.get(`http://localhost:5000${res.data.layers.roads}`)
              .then(rRes => setRoads(rRes.data))
              .catch(err => console.error('No roads data', err));
          }
        }
      })
      .catch(err => console.error("Error fetching config:", err));
  }, []);

  if (!config) return <div className="loading">Loading OrbitalResQ Data...</div>;

  const center = [
    (config.bounds[0][0] + config.bounds[1][0]) / 2,
    (config.bounds[0][1] + config.bounds[1][1]) / 2
  ];

  return (
    <div className="App">
      <header className="header">
        <h1>🛰️ OrbitalResQ: MERN Stack Flood Dashboard</h1>
        <p>AI Flood Mapping from Sentinel-1 SAR</p>
      </header>
      
      <div className="dashboard-content">
        <div className="sidebar">
          <h2>Damage Statistics</h2>
          <div className="stat-box">
            <h3>Damaged Buildings</h3>
            <p className="stat-number">{buildings ? buildings.features?.length || 0 : '...'}</p>
          </div>
          <div className="stat-box">
            <h3>Flooded Roads</h3>
            <p className="stat-number">{roads ? roads.features?.length || 0 : '...'}</p>
          </div>
          <div className="legend">
            <h3>Legend</h3>
            <div className="legend-item"><span className="color-box water"></span> Flood Water</div>
            <div className="legend-item"><span className="color-box debris"></span> Debris</div>
            <div className="legend-item"><span className="color-box bldg"></span> Damaged Buildings</div>
            <div className="legend-item"><span className="color-box road"></span> Flooded Roads</div>
          </div>
        </div>

        <div className="map-container">
          <MapContainer center={center} zoom={13} style={{ height: "100%", width: "100%" }}>
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
            />
            
            {/* AI Flood Mask Overlay */}
            <ImageOverlay
              url={`http://localhost:5000${config.layers.floodOverlay}`}
              bounds={config.bounds}
              opacity={0.8}
            />

            {/* Buildings GeoJSON */}
            {buildings && buildings.features?.length > 0 && (
              <GeoJSON 
                data={buildings} 
                style={{ color: '#e74c3c', weight: 1, fillColor: '#c0392b', fillOpacity: 0.7 }}
              />
            )}

            {/* Roads GeoJSON */}
            {roads && roads.features?.length > 0 && (
              <GeoJSON 
                data={roads} 
                style={{ color: '#f39c12', weight: 4 }}
              />
            )}
          </MapContainer>
        </div>
      </div>
    </div>
  );
}

export default App;
