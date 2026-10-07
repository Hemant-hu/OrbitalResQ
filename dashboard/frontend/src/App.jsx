import { useEffect, useState, useRef } from 'react';
import { MapContainer, TileLayer, ImageOverlay, GeoJSON } from 'react-leaflet';
import axios from 'axios';
import 'leaflet/dist/leaflet.css';
import './App.css';

const API = 'http://localhost:5000';

function App() {
  const [config, setConfig] = useState(null);
  const [buildings, setBuildings] = useState(null);
  const [roads, setRoads] = useState(null);
  const [sitrep, setSitrep] = useState(null);
  const [sitrepLang, setSitrepLang] = useState('en');
  const [sitrepText, setSitrepText] = useState('');
  const [activeTab, setActiveTab] = useState('map');
  
  // Copilot state
  const [messages, setMessages] = useState([
    { role: 'bot', text: 'Hello! I am the OrbitalResQ Copilot. Ask me anything about the flood damage — every number I give comes directly from our satellite analysis. Try: "How much area was flooded?" or "How many villages are cut off?"' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    axios.get(`${API}/api/config`)
      .then(res => {
        if (res.data.status === 'success') {
          setConfig(res.data);
          axios.get(`${API}${res.data.layers.buildings}`)
            .then(bRes => setBuildings(bRes.data))
            .catch(() => setBuildings({ type: "FeatureCollection", features: [] }));
          axios.get(`${API}${res.data.layers.roads}`)
            .then(rRes => setRoads(rRes.data))
            .catch(() => setRoads({ type: "FeatureCollection", features: [] }));
        }
      })
      .catch(err => console.error("Config error:", err));

    // Load sitrep stats
    axios.get(`${API}/api/sitrep`)
      .then(res => res.data.status === 'success' && setSitrep(res.data.stats))
      .catch(() => {});
  }, []);

  // Load sitrep text when language changes
  useEffect(() => {
    axios.get(`${API}/api/sitrep/${sitrepLang}`)
      .then(res => res.data.status === 'success' && setSitrepText(res.data.report))
      .catch(() => setSitrepText('Report not available. Run: python src/report_generator.py'));
  }, [sitrepLang]);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;
    const userMsg = input.trim();
    setMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setInput('');
    setLoading(true);

    try {
      const res = await axios.post(`${API}/api/copilot`, { question: userMsg });
      setMessages(prev => [...prev, { role: 'bot', text: res.data.answer }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'bot', text: 'Error: Could not process your question.' }]);
    }
    setLoading(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (!config) return <div className="loading">Loading OrbitalResQ Data...</div>;

  const center = [
    (config.bounds[0][0] + config.bounds[1][0]) / 2,
    (config.bounds[0][1] + config.bounds[1][1]) / 2
  ];

  const bldgCount = buildings?.features?.length || 0;
  const roadCount = roads?.features?.length || 0;

  return (
    <div className="App">
      <header className="header">
        <h1>🛰️ OrbitalResQ: AI Flood Damage Assessment</h1>
        <p>Satellite-Based Disaster Response — Bhote Koshi–Trishuli Corridor, Nepal</p>
      </header>
      
      {/* Tab Navigation */}
      <nav className="tab-nav">
        <button className={activeTab === 'map' ? 'active' : ''} onClick={() => setActiveTab('map')}>🗺️ Map</button>
        <button className={activeTab === 'sitrep' ? 'active' : ''} onClick={() => setActiveTab('sitrep')}>📋 Situation Report</button>
        <button className={activeTab === 'copilot' ? 'active' : ''} onClick={() => setActiveTab('copilot')}>🤖 Copilot</button>
      </nav>

      <div className="dashboard-content">
        {/* ─── Sidebar ─── */}
        <div className="sidebar">
          <h2>Damage Statistics</h2>
          <div className="stat-box">
            <h3>Flood Area</h3>
            <p className="stat-number">{sitrep ? `${sitrep.flood_area_km2} km²` : '...'}</p>
          </div>
          <div className="stat-box">
            <h3>Damaged Buildings</h3>
            <p className="stat-number">{buildings ? bldgCount : '...'}</p>
          </div>
          <div className="stat-box">
            <h3>Flooded Roads</h3>
            <p className="stat-number">{roads ? roadCount : '...'}</p>
          </div>
          <div className="stat-box">
            <h3>Cut-off Villages</h3>
            <p className="stat-number">{sitrep ? sitrep.cutoff_villages : '...'}</p>
          </div>
          <div className="legend">
            <h3>Legend</h3>
            <div className="legend-item"><span className="color-box water"></span> Flood Water</div>
            <div className="legend-item"><span className="color-box debris"></span> Debris</div>
            <div className="legend-item"><span className="color-box bldg"></span> Damaged Buildings</div>
            <div className="legend-item"><span className="color-box road"></span> Flooded Roads</div>
          </div>
        </div>

        {/* ─── Main Content Area ─── */}
        <div className="main-content">
          
          {/* MAP TAB */}
          {activeTab === 'map' && (
            <div className="map-container">
              <MapContainer center={center} zoom={13} style={{ height: "100%", width: "100%" }}>
                <TileLayer
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                />
                <ImageOverlay
                  url={`${API}${config.layers.floodOverlay}`}
                  bounds={config.bounds}
                  opacity={0.8}
                />
                {buildings?.features?.length > 0 && (
                  <GeoJSON data={buildings} style={{ color: '#e74c3c', weight: 1, fillColor: '#c0392b', fillOpacity: 0.7 }} />
                )}
                {roads?.features?.length > 0 && (
                  <GeoJSON data={roads} style={{ color: '#f39c12', weight: 4 }} />
                )}
              </MapContainer>
            </div>
          )}

          {/* SITREP TAB */}
          {activeTab === 'sitrep' && (
            <div className="sitrep-container">
              <div className="sitrep-controls">
                <button className={sitrepLang === 'en' ? 'active' : ''} onClick={() => setSitrepLang('en')}>🇬🇧 English</button>
                <button className={sitrepLang === 'ne' ? 'active' : ''} onClick={() => setSitrepLang('ne')}>🇳🇵 नेपाली</button>
              </div>
              <pre className="sitrep-text">{sitrepText}</pre>
            </div>
          )}

          {/* COPILOT TAB */}
          {activeTab === 'copilot' && (
            <div className="copilot-container">
              <div className="chat-messages">
                {messages.map((msg, i) => (
                  <div key={i} className={`chat-msg ${msg.role}`}>
                    <span className="chat-label">{msg.role === 'user' ? '👤 Rescuer' : '🤖 Copilot'}</span>
                    <p>{msg.text}</p>
                  </div>
                ))}
                {loading && <div className="chat-msg bot"><span className="chat-label">🤖 Copilot</span><p className="typing">Analyzing data...</p></div>}
                <div ref={chatEndRef} />
              </div>
              <div className="chat-input-area">
                <input
                  type="text"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask about flood damage, roads, buildings, cut-off villages..."
                />
                <button onClick={sendMessage} disabled={loading}>Send</button>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

export default App;
