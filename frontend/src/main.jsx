import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const API = 'http://localhost:8000';

function App() {
  const [incidents, setIncidents] = useState([]);
  const [notice, setNotice] = useState('Connecting to dispatch feed…');
  const incident = incidents[0];

  useEffect(() => {
    fetch(`${API}/api/incidents`).then(r => r.json()).then(setIncidents).catch(() => setNotice('API offline — start the backend.'));
    const feed = new EventSource(`${API}/api/events`);
    feed.addEventListener('incidents', e => { setIncidents(JSON.parse(e.data)); setNotice('Live simulation feed'); });
    feed.onerror = () => setNotice('Feed reconnecting…');
    return () => feed.close();
  }, []);

  async function action(path, body) {
    if (!incident) return;
    const response = await fetch(`${API}/api/incidents/${incident.id}/${path}`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: body && JSON.stringify(body) });
    const result = await response.json();
    setNotice(response.ok ? `${path.replace('-', ' ')} complete` : result.detail);
  }

  if (!incident) return <main className="loading">AGNI · {notice}</main>;
  const critical = incident.triage_level <= 1;
  return <main>
    <header><div className="brand"><span className="ember">◉</span> AGNI <small>CRISIS INTELLIGENCE</small></div><div className="island"><span>● {incidents.length} ACTIVE</span><span>DATA: CACHED DEMO</span><button className="override" onClick={() => action('override', {note:'Dispatcher assuming voice control.'})}>JUMP IN · OVERRIDE</button></div></header>
    <section className="grid">
      <aside className="panel queue"><p className="eyebrow">ACTIVE INCIDENTS</p><article className={critical ? 'incident critical' : 'incident'}><span className="level">P{incident.triage_level}</span><div><strong>{incident.caller_label}</strong><p>{incident.summary}</p><small>{incident.status.replace('_', ' ')}</small></div></article><p className="eyebrow">LIVE TRANSCRIPT</p><div className="transcript"><p><b>CALLER</b> I can see dark smoke by the trail.</p><p><b>AGNI</b> Stay clear of smoke. I’m locating help.</p></div></aside>
      <section className="map panel"><div className="map-label">SAN DIEGO · SIMULATION MAP</div><div className="fire-zone">HAZARD<br/><small>ROAD CLOSURE</small></div><div className="route">RECOMMENDED RESPONSE ROUTE</div><div className="marker caller">●<small>CALLER</small></div><div className="marker unit">◆<small>ENGINE 17</small></div><div className="legend">● Incident &nbsp; ◆ Unit &nbsp; ━ Recommended route</div></section>
      <aside className="panel controls"><p className="eyebrow">VISUAL TRIAGE</p><div className="vision"><span>CAMERA LINK READY</span><h2>{incident.vision.smoke_density || 'No'} smoke assessment</h2><p>Flames: {incident.vision.visible_flames ? 'detected' : 'not detected'}<br/>Blocked exit: {incident.vision.blocked_exit ? 'detected' : 'not detected'}</p><button onClick={() => action('vision', {smoke_density:'heavy', visible_flames:true, blocked_exit:true})}>SIMULATE CRITICAL FRAME</button></div><p className="eyebrow">DISPATCH</p><div className="dispatch"><strong>{incident.assigned_unit_id ? 'UNIT ASSIGNED' : 'RECOMMENDED: ENGINE 17'}</strong><p>Available route avoids closure.</p><button className="primary" onClick={() => action('dispatch')}>DISPATCH UNIT</button></div><footer>{notice}</footer></aside>
    </section><p className="disclaimer">Prototype simulation only — not an emergency service. For emergencies, call local emergency services.</p>
  </main>;
}
createRoot(document.getElementById('root')).render(<App />);

