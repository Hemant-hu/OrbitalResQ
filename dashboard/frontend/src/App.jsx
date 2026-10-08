import { useEffect, useState, useRef } from 'react';
import { MapContainer, TileLayer, ImageOverlay, GeoJSON } from 'react-leaflet';
import axios from 'axios';
import { 
  Map, FileText, MessageSquare, 
  Activity, House, Route, Users, 
  Satellite, AlertTriangle, ChevronRight, Send, Search
} from 'lucide-react';
import 'leaflet/dist/leaflet.css';

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
    { role: 'bot', text: 'Hello! I am the OrbitalResQ Copilot. Ask me anything about the flood damage — every number I give comes directly from our satellite analysis. Try: "How much area was flooded?"' }
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

    axios.get(`${API}/api/sitrep`)
      .then(res => res.data.status === 'success' && setSitrep(res.data.stats))
      .catch(() => {});
  }, []);

  useEffect(() => {
    axios.get(`${API}/api/sitrep/${sitrepLang}`)
      .then(res => res.data.status === 'success' && setSitrepText(res.data.report))
      .catch(() => setSitrepText('Report not available. Run: python src/report_generator.py'));
  }, [sitrepLang]);

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

  if (!config) return (
    <div className="flex h-screen w-screen items-center justify-center bg-white">
      <div className="flex flex-col items-center animate-pulse">
        <Satellite className="w-16 h-16 text-orange-500 mb-4 animate-spin-slow" />
        <h1 className="text-2xl font-bold text-blue-900 tracking-widest">ORBITAL<span className="text-orange-500">RESQ</span></h1>
        <p className="text-slate-500 mt-2 font-medium">Loading Satellite Telemetry...</p>
      </div>
    </div>
  );

  const center = [
    (config.bounds[0][0] + config.bounds[1][0]) / 2,
    (config.bounds[0][1] + config.bounds[1][1]) / 2
  ];

  const bldgCount = buildings?.features?.length || 0;
  const roadCount = roads?.features?.length || 0;

  return (
    <div className="flex flex-col min-h-screen bg-gray-50 font-sans">
      
      {/* ─── TOP ORANGE BAR ─── */}
      <div className="bg-[#f59e0b] text-white text-xs font-bold px-6 py-1.5 flex justify-between shrink-0">
        <span>#OrbitalResQ</span>
        <div className="flex gap-6">
          <span className="cursor-pointer hover:underline">Resources</span>
          <span className="cursor-pointer hover:underline">Contact</span>
          <span className="cursor-pointer hover:underline bg-blue-900 px-3 py-0.5 rounded-full text-white">Login</span>
        </div>
      </div>

      {/* ─── HEADER ─── */}
      <header className="bg-white py-4 px-6 flex justify-between items-center shadow-sm z-20 shrink-0">
        <div className="flex items-center gap-5">
          {/* Fake EU Flag */}
          <div className="bg-[#034ea2] text-[#ffcc00] font-bold p-2 flex flex-col items-center justify-center text-[8px] w-14 h-10 rounded-sm leading-tight text-center">
            PROGRAMME OF THE<br/>EUROPEAN UNION
          </div>
          {/* Main Logos */}
          <div className="flex items-center">
            <h1 className="text-[#034ea2] font-black text-3xl tracking-tight pr-4 border-r border-gray-300">
              Orbital<span className="text-blue-400 font-medium">ResQ</span>
            </h1>
            <div className="text-[#f59e0b] flex items-center gap-2 text-sm font-bold pl-4">
              <AlertTriangle size={20}/> 
              <span className="leading-tight">Emergency<br/>Management</span>
            </div>
          </div>
        </div>

        <nav className="hidden md:flex gap-8 text-gray-600 font-semibold text-sm">
          <span className="text-[#f59e0b] border-b-2 border-[#f59e0b] pb-1 cursor-pointer">Home</span>
          <span className="hover:text-[#034ea2] cursor-pointer">About</span>
          <span className="hover:text-[#034ea2] cursor-pointer">Activations</span>
          <span className="hover:text-[#034ea2] cursor-pointer">Stats</span>
          <span className="hover:text-[#034ea2] cursor-pointer">News</span>
          <Search size={18} className="text-gray-400 hover:text-gray-700 cursor-pointer"/>
        </nav>
      </header>

      {/* ─── HERO BANNER ─── */}
      <div className="relative h-48 bg-slate-800 shrink-0">
        {/* We use a CSS gradient as the background image replacement */}
        <div className="absolute inset-0 bg-gradient-to-r from-[#034ea2] to-cyan-700 opacity-95"></div>
        <div className="absolute inset-0 p-8 flex items-center">
          <div className="bg-black/30 backdrop-blur-md p-6 rounded-xl text-white max-w-3xl border border-white/10 shadow-2xl">
            <h1 className="text-3xl font-bold mb-2">OrbitalResQ</h1>
            <h2 className="text-xl font-semibold mb-3">Emergency Management Service - On Demand Mapping</h2>
            <p className="text-sm text-gray-200 leading-relaxed">
              We use AI-fused satellite imagery (Sentinel-1 SAR & Sentinel-2 Optical) and spatial routing to provide free of charge mapping service and situational awareness in cases of natural hazards and humanitarian crises.
            </p>
          </div>
        </div>
      </div>

      {/* ─── MAIN SPLIT CONTENT ─── */}
      <div className="flex flex-1 bg-white">
        
        {/* LEFT SIDEBAR: Search & Activations */}
        <div className="w-[400px] border-r border-gray-200 flex flex-col bg-white z-10 shadow-lg shrink-0">
          
          {/* Search Box */}
          <div className="p-4 border-b border-gray-100 bg-gray-50">
            <div className="relative mb-3">
              <input type="text" placeholder="Search for event, activations, areas..." className="w-full border border-gray-300 rounded shadow-inner px-3 py-2 text-sm focus:outline-none focus:border-[#034ea2]" />
              <Search size={16} className="absolute right-3 top-2.5 text-gray-400"/>
            </div>
            <select className="w-full border border-gray-300 rounded shadow-inner px-3 py-2 text-sm mb-3 bg-white text-gray-700 focus:outline-none">
              <option>Country: Nepal</option>
            </select>
            <div className="flex gap-2">
              <select className="flex-1 border border-gray-300 rounded shadow-inner px-3 py-2 text-sm bg-white text-gray-700 focus:outline-none">
                <option>Phase</option>
              </select>
              <button className="px-4 py-2 text-sm text-gray-500 border border-gray-300 rounded bg-white font-semibold">ONGOING</button>
            </div>
          </div>
          
          {/* Activations List */}
          <div className="flex-1 p-4 space-y-4">
            
            <div className="bg-white border-2 border-[#f59e0b] rounded shadow-sm p-4 cursor-pointer relative overflow-hidden">
              <div className="absolute top-0 left-0 w-1 h-full bg-[#f59e0b]"></div>
              
              <div className="flex justify-between items-start mb-3 ml-2">
                <div className="flex items-center gap-2 text-[#f59e0b] font-bold text-sm">
                  <div className="p-1 bg-orange-100 rounded-full"><Satellite size={14}/></div>
                  EMSR927 - Rapid Mapping
                </div>
                <span className="bg-[#f59e0b] text-white text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider">Ongoing</span>
              </div>
              
              <h3 className="font-bold text-gray-900 mb-3 ml-2">Glacier Collapse & Flood in Trishuli, Nepal</h3>
              
              <div className="grid grid-cols-2 gap-4 text-[11px] text-gray-500 mb-5 ml-2">
                <div>
                  <div className="uppercase">Activation Time</div>
                  <div className="font-semibold text-gray-700">26/08/2026, 14:02</div>
                </div>
                <div>
                  <div className="uppercase">Service Output</div>
                  <div className="font-semibold text-gray-700">Multi-Modal AI Fusion</div>
                </div>
              </div>

              {/* TABS (Styled as interactive activation details) */}
              <div className="space-y-2 border-t border-gray-100 pt-3">
                <button 
                  onClick={() => setActiveTab('map')} 
                  className={`w-full text-left px-3 py-2.5 rounded-md text-sm font-semibold flex items-center justify-between transition-all ${activeTab === 'map' ? 'bg-blue-50 text-[#034ea2] border border-blue-200 shadow-sm' : 'hover:bg-gray-50 text-gray-600 border border-transparent'}`}
                >
                  <span className="flex items-center gap-2"><Map size={16}/> Interactive Damage Map</span>
                  <ChevronRight size={16} className={activeTab === 'map' ? 'text-[#034ea2]' : 'text-gray-400'}/>
                </button>
                <button 
                  onClick={() => setActiveTab('sitrep')} 
                  className={`w-full text-left px-3 py-2.5 rounded-md text-sm font-semibold flex items-center justify-between transition-all ${activeTab === 'sitrep' ? 'bg-blue-50 text-[#034ea2] border border-blue-200 shadow-sm' : 'hover:bg-gray-50 text-gray-600 border border-transparent'}`}
                >
                  <span className="flex items-center gap-2"><FileText size={16}/> Official Situation Report</span>
                  <ChevronRight size={16} className={activeTab === 'sitrep' ? 'text-[#034ea2]' : 'text-gray-400'}/>
                </button>
                <button 
                  onClick={() => setActiveTab('copilot')} 
                  className={`w-full text-left px-3 py-2.5 rounded-md text-sm font-semibold flex items-center justify-between transition-all ${activeTab === 'copilot' ? 'bg-blue-50 text-[#034ea2] border border-blue-200 shadow-sm' : 'hover:bg-gray-50 text-gray-600 border border-transparent'}`}
                >
                  <span className="flex items-center gap-2"><MessageSquare size={16}/> AI Mission Copilot</span>
                  <ChevronRight size={16} className={activeTab === 'copilot' ? 'text-[#034ea2]' : 'text-gray-400'}/>
                </button>
              </div>
            </div>
            
            {/* Dummy inactive event to show scrollable list style */}
            <div className="bg-white border border-gray-200 rounded p-4 opacity-60 grayscale ml-1">
              <div className="flex justify-between items-start mb-2">
                <div className="flex items-center gap-2 text-gray-600 font-bold text-sm">
                  <div className="p-1 bg-gray-100 rounded-full"><Satellite size={14}/></div>
                  EMSN238 - Risk Mapping
                </div>
              </div>
              <h3 className="font-bold text-gray-800 text-sm">Dam Break Scenarios in Sardinia, Italy</h3>
            </div>

          </div>
        </div>

        {/* RIGHT CONTENT AREA (The actual view) */}
        <div className="flex-1 bg-gray-100 relative min-h-[750px]">
          
          {/* 🗺️ MAP VIEW */}
          {activeTab === 'map' && (
            <div className="w-full h-full min-h-[750px] relative">
              <MapContainer center={center} zoom={13} className="h-full w-full z-0">
                <TileLayer
                  url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                  attribution='&copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
                />
                <ImageOverlay url={`${API}${config.layers.floodOverlay}`} bounds={config.bounds} opacity={0.85} />
                {buildings?.features?.length > 0 && (
                  <GeoJSON data={buildings} style={{ color: '#ef4444', weight: 1, fillColor: '#dc2626', fillOpacity: 0.8 }} />
                )}
                {roads?.features?.length > 0 && (
                  <GeoJSON data={roads} style={{ color: '#f59e0b', weight: 4 }} />
                )}
              </MapContainer>
              
              {/* Legend overlay matching Copernicus style */}
              <div className="absolute bottom-6 right-6 bg-white/95 backdrop-blur rounded shadow-lg border border-gray-200 p-4 z-[400] w-64">
                <h4 className="text-xs font-bold text-gray-500 uppercase mb-3 border-b border-gray-200 pb-2">Activation Legend</h4>
                <div className="space-y-3 text-sm font-semibold text-gray-700">
                  <div className="flex items-center gap-3"><span className="w-5 h-5 rounded-sm border border-blue-600 bg-blue-500/80"></span> Flood Water</div>
                  <div className="flex items-center gap-3"><span className="w-5 h-5 rounded-sm border border-[#5c2e0b] bg-[#8B4513]/80"></span> Debris / Mudslide</div>
                  <div className="flex items-center gap-3"><span className="w-5 h-5 rounded-sm border border-red-700 bg-red-600"></span> Damaged Buildings</div>
                  <div className="flex items-center gap-3"><span className="w-5 h-2 rounded-full bg-[#f59e0b]"></span> Flooded Roads</div>
                </div>
              </div>
            </div>
          )}

          {/* 📋 SITREP VIEW */}
          {activeTab === 'sitrep' && (
            <div className="h-full min-h-[750px] flex flex-col bg-white">
              <div className="flex bg-gray-50 border-b border-gray-200 p-3 gap-3 justify-center shadow-sm shrink-0">
                <button 
                  onClick={() => setSitrepLang('en')}
                  className={`px-6 py-2 rounded font-bold text-sm transition-colors border ${sitrepLang === 'en' ? 'bg-[#034ea2] text-white border-[#034ea2]' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-100'}`}
                >
                  🇬🇧 English Report
                </button>
                <button 
                  onClick={() => setSitrepLang('ne')}
                  className={`px-6 py-2 rounded font-bold text-sm transition-colors border ${sitrepLang === 'ne' ? 'bg-[#034ea2] text-white border-[#034ea2]' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-100'}`}
                >
                  🇳🇵 नेपाली प्रतिवेदन
                </button>
              </div>
              <div className="flex-1 p-8 bg-gray-100">
                <pre className="font-mono text-sm leading-relaxed text-gray-800 whitespace-pre-wrap max-w-4xl mx-auto bg-white p-10 rounded shadow-md border border-gray-200">
                  {sitrepText}
                </pre>
              </div>
            </div>
          )}

          {/* 🤖 COPILOT VIEW */}
          {activeTab === 'copilot' && (
            <div className="h-full min-h-[750px] flex flex-col bg-white">
              <div className="bg-gray-50 border-b border-gray-200 px-6 py-4 shrink-0">
                <h2 className="text-lg font-bold text-[#034ea2] flex items-center gap-2">
                  <MessageSquare size={20}/> Copernicus Integration Copilot
                </h2>
                <p className="text-xs text-gray-500 font-medium">Ask questions grounded strictly in the satellite telemetry from EMSR927.</p>
              </div>
              <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-gray-50 h-[500px]">
                {messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] p-4 shadow-sm ${msg.role === 'user' ? 'bg-[#034ea2] text-white rounded-l-xl rounded-br-xl' : 'bg-white border border-gray-200 rounded-r-xl rounded-bl-xl'}`}>
                      <div className="flex items-center gap-2 mb-2 opacity-80">
                        {msg.role === 'user' ? <Users size={14} /> : <Satellite size={14} />}
                        <span className="text-[10px] font-bold uppercase tracking-wider">{msg.role === 'user' ? 'Rescuer' : 'Copilot System'}</span>
                      </div>
                      <p className="leading-relaxed text-sm font-medium">{msg.text}</p>
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="flex justify-start">
                    <div className="bg-white border border-gray-200 rounded-r-xl rounded-bl-xl p-4 shadow-sm flex gap-2 items-center text-gray-500">
                      <Activity className="w-4 h-4 animate-spin" />
                      <span className="text-sm font-medium">Analyzing telemetry...</span>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
              
              <div className="p-4 bg-white border-t border-gray-200 shrink-0">
                <div className="relative flex items-center max-w-4xl mx-auto">
                  <input
                    type="text"
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask about flood damage, cut-off villages, or specific metrics..."
                    className="w-full bg-gray-100 border border-gray-300 rounded px-6 py-4 pr-14 text-gray-700 font-medium focus:ring-2 focus:ring-[#f59e0b] focus:border-transparent outline-none transition-all shadow-inner"
                  />
                  <button 
                    onClick={sendMessage} 
                    disabled={loading || !input.trim()}
                    className="absolute right-3 p-2 bg-[#f59e0b] text-white rounded hover:bg-orange-600 disabled:opacity-50 transition-colors"
                  >
                    <Send size={18} />
                  </button>
                </div>
              </div>
            </div>
          )}

        </div>
      </div>

      {/* ─── BOTTOM ORANGE STATS FOOTER ─── */}
      <div className="bg-[#e68a00] text-white py-3 px-8 flex justify-around items-center shrink-0 shadow-[0_-4px_10px_rgba(0,0,0,0.1)] z-20">
        
        <div className="flex items-center gap-4">
          <Activity size={32} strokeWidth={1.5} className="opacity-90"/>
          <div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-light">{sitrep ? sitrep.flood_area_km2 : '-'}</span>
              <span className="text-sm font-medium opacity-90">for</span>
            </div>
            <div className="text-sm font-bold uppercase tracking-wider">Area Flooded (km²)</div>
          </div>
        </div>

        <div className="w-px h-10 bg-white/30"></div>
        
        <div className="flex items-center gap-4">
          <House size={32} strokeWidth={1.5} className="opacity-90"/>
          <div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-light">{buildings ? bldgCount : '-'}</span>
              <span className="text-sm font-medium opacity-90">for</span>
            </div>
            <div className="text-sm font-bold uppercase tracking-wider">Damaged Buildings</div>
          </div>
        </div>

        <div className="w-px h-10 bg-white/30"></div>

        <div className="flex items-center gap-4">
          <Route size={32} strokeWidth={1.5} className="opacity-90"/>
          <div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-light">{roads ? roadCount : '-'}</span>
              <span className="text-sm font-medium opacity-90">for</span>
            </div>
            <div className="text-sm font-bold uppercase tracking-wider">Flooded Roads</div>
          </div>
        </div>

        <div className="w-px h-10 bg-white/30"></div>

        <div className="flex items-center gap-4">
          <Users size={32} strokeWidth={1.5} className="opacity-90"/>
          <div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-light">{sitrep ? sitrep.cutoff_villages : '-'}</span>
              <span className="text-sm font-medium opacity-90">for</span>
            </div>
            <div className="text-sm font-bold uppercase tracking-wider">Cut-off Villages</div>
          </div>
        </div>
        
      </div>
    </div>
  );
}

export default App;
