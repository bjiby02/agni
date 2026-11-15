import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './styles.css';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const TOKEN = localStorage.getItem('agni.operatorToken') || '';
const EVENT_TYPES = [
  'signal.new', 'call.started', 'call.transcript', 'incident.created', 'incident.merge_suggested',
  'incident.merged', 'triage.result', 'route.ready', 'unit.dispatched', 'handoff.started',
  'handoff.ended', 'ring.updated', 'warning.sent', 'surge.stats', 'incident.closed',
  'bearing.added', 'estimate.updated', 'cameras.selected', 'satellite.result', 'evidence.updated',
  'rescue.requested',
];

function App() {
  const [state, setState] = useState({ incidents: [], units: [], hazards: [], signals: [], calls: [], last_seq: 0 });
  const [settings, setSettings] = useState({ overflow_enabled: false, mode: 'mock' });
  const [selectedId, setSelectedId] = useState(null);
  const [calls, setCalls] = useState({});
  const [cameras, setCameras] = useState([]);
  const [notice, setNotice] = useState('Starting local command view');
  const [connection, setConnection] = useState('connecting');
  const [busy, setBusy] = useState(false);
  const [route, setRoute] = useState(null);
  const [proof, setProof] = useState({ sim: null, eval: null });
  const [handoff, setHandoff] = useState(null);
  const [seen, setSeen] = useState(() => {
    try { return JSON.parse(localStorage.getItem('agni.lastSeen') || '{}'); } catch { return {}; }
  });
  const mapRef = useRef(null);
  const mapNode = useRef(null);
  const layerRef = useRef(null);
  const headers = useMemo(() => ({ ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}) }), []);
  const incidents = state.incidents || [];
  const selected = incidents.find(item => item.id === selectedId) || incidents[0] || null;
  const relatedMerge = state.merges?.find(item => item.kept_id === selected?.id || item.merged_id === selected?.id);
  const selectedRing = state.rings?.find(item => item.incident_id === selected?.id);
  const liveCall = (state.calls || []).find(c => c.incident_id === selected?.id);
  const humanOnCall = liveCall?.state === 'human' || handoff?.incident_id === selected?.id;

  const refresh = useCallback(async () => {
    const [stateRes, settingsRes, proofRes] = await Promise.all([
      fetch(`${API}/api/state`, { headers }),
      fetch(`${API}/api/settings`, { headers }),
      fetch(`${API}/api/proof`, { headers }),
    ]);
    if (!stateRes.ok || !settingsRes.ok) throw new Error('Console access failed. Check the API and operator token.');
    const [nextState, nextSettings, nextProof] = await Promise.all([
      stateRes.json(), settingsRes.json(), proofRes.ok ? proofRes.json() : { sim: null, eval: null },
    ]);
    setState(nextState);
    setSettings(nextSettings);
    setProof(nextProof);
    setSelectedId(current => current || nextState.incidents?.[0]?.id || null);
  }, [headers]);

  useEffect(() => {
    refresh().then(() => setConnection('live')).catch(error => {
      setConnection('offline'); setNotice(error.message);
    });
    const last = Number(localStorage.getItem('agni.eventSeq') || 0);
    const feed = new EventSource(`${API}/api/events?since=${last}${TOKEN ? `&token=${encodeURIComponent(TOKEN)}` : ''}`);
    feed.onopen = () => { setConnection('live'); setNotice('Receiving incident events'); };
    feed.onerror = () => { setConnection('reconnecting'); setNotice('Reconnecting to the event stream'); };
    const onEvent = event => {
      const payload = JSON.parse(event.data);
      const seq = Number(payload.seq || event.lastEventId || 0);
      const seenSeq = Number(localStorage.getItem('agni.eventSeq') || 0);
      if (seq && seq <= seenSeq) return;
      if (seq) localStorage.setItem('agni.eventSeq', String(seq));
      if (payload.type === 'call.started') {
        setCalls(current => ({ ...current, [payload.incident_id]: {
          ...(current[payload.incident_id] || {}), id: payload.data.call_id,
          direction: payload.data.direction, language: payload.data.language,
        } }));
      }
      if (payload.type === 'call.transcript') {
        setCalls(current => {
          const previous = current[payload.incident_id] || {};
          return { ...current, [payload.incident_id]: {
            ...previous,
            lines: [...(previous.lines || []), payload.data].slice(-12),
          } };
        });
      }
      if (payload.type === 'handoff.started') {
        setHandoff({ incident_id: payload.incident_id, summary: payload.data.summary, call_id: payload.data.call_id });
      }
      if (payload.type === 'handoff.ended') setHandoff(null);
      setNotice(`${payload.type.replaceAll('.', ' ')} · ${new Date(payload.ts).toLocaleTimeString()}`);
      refresh().catch(() => {});
    };
    EVENT_TYPES.forEach(type => feed.addEventListener(type, onEvent));
    return () => feed.close();
  }, [refresh]);

  useEffect(() => {
    if (!mapNode.current || mapRef.current) return;
    const map = L.map(mapNode.current, { zoomControl: false, attributionControl: true }).setView([32.87, -117.25], 12);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap &copy; CARTO',
      maxZoom: 19,
    }).addTo(map);
    L.control.zoom({ position: 'bottomright' }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();
    (state.signals || []).forEach(sig => {
      if (sig.lat == null || sig.lon == null) return;
      L.circleMarker([sig.lat, sig.lon], {
        radius: 6, color: '#8899a3', fillColor: '#7d878d', fillOpacity: 0.7, weight: 1, dashArray: '2 3',
      }).bindTooltip(`unverified · ${sig.source}`, { permanent: false }).addTo(layer);
    });
    (state.units || []).forEach(unit => {
      if (unit.lat == null || unit.lon == null) return;
      L.marker([unit.lat, unit.lon], {
        icon: L.divIcon({ className: 'unit-marker', html: `<span>+</span><small>${unit.callsign}</small>` }),
      }).addTo(layer);
    });
    incidents.forEach(item => {
      if (item.lat == null || item.lon == null) return;
      const confirmed = item.status === 'confirmed' || item.status === 'dispatched';
      L.circleMarker([item.lat, item.lon], {
        radius: confirmed ? 9 : 7,
        color: confirmed ? '#ff685c' : '#f2b544',
        fillColor: confirmed ? '#ff685c' : '#f2b544',
        fillOpacity: confirmed ? 0.9 : 0.45,
        weight: 2,
      }).bindTooltip(item.title || item.id).on('click', () => setSelectedId(item.id)).addTo(layer);
    });
    if (selectedRing?.geometry) {
      try {
        L.geoJSON(selectedRing.geometry, {
          style: { color: '#f2b544', weight: 2, fillColor: '#f2b544', fillOpacity: 0.12, dashArray: '4 4' },
        }).bindTooltip(`${selectedRing.minutes}-min estimate`).addTo(layer);
      } catch { /* ignore bad geometry */ }
    }
    if (selected?.lat != null && selected?.lon != null) {
      map.panTo([selected.lat, selected.lon], { animate: true });
    }
  }, [state.signals, state.units, incidents, selected?.id, selected?.lat, selected?.lon, selectedRing]);

  useEffect(() => {
    if (!selected?.lat || !selected?.lon) { setCameras([]); setRoute(null); return; }
    const query = new URLSearchParams({ lat: selected.lat, lon: selected.lon, n: 3 });
    fetch(`${API}/api/cameras?${query}`, { headers }).then(r => r.ok ? r.json() : { cameras: [] })
      .then(result => setCameras(result.cameras || [])).catch(() => setCameras([]));
  }, [selected?.id, selected?.lat, selected?.lon, headers]);

  const markSeen = id => {
    if (!id) return;
    const next = { ...seen, [id]: state.last_seq || 0 };
    setSeen(next);
    localStorage.setItem('agni.lastSeen', JSON.stringify(next));
  };

  useEffect(() => { if (selectedId) markSeen(selectedId); }, [selectedId, state.last_seq]);

  const newCount = item => {
    const baseline = seen[item.id] || 0;
    return Math.max(0, (state.last_seq || 0) - baseline) > 0 && selected?.id !== item.id ? 'NEW' : null;
  };

  const request = async (path, body, extra = {}) => {
    const response = await fetch(`${API}${path}`, {
      method: 'POST', headers: { ...headers, 'Content-Type': 'application/json', ...extra },
      body: body ? JSON.stringify(body) : '{}',
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.detail || `Request failed (${response.status})`);
    return result;
  };

  const confirmFire = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await request(`/api/incidents/${selected.id}/confirm`, { actor: 'dispatcher', note: 'Confirmed by dispatcher' });
      setNotice('Fire confirmed by dispatcher'); await refresh();
    } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  };

  const approveDispatch = async () => {
    if (!selected || selected.status !== 'confirmed') return;
    setBusy(true);
    try {
      const options = await fetch(`${API}/api/incidents/${selected.id}/route`, { headers }).then(r => r.json());
      setRoute(options);
      const unit = options.units?.[0];
      if (!unit) throw new Error('No available unit is listed');
      await request(`/api/incidents/${selected.id}/dispatch`, { unit_id: unit.unit_id, approved_by: 'dispatcher' },
        { 'Idempotency-Key': crypto.randomUUID() });
      setNotice(`Dispatch approved · ${unit.callsign} · serial buzz queued`); await refresh();
    } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  };

  const createRing = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await request(`/api/incidents/${selected.id}/ring`, { minutes: 30, wind_to_deg: 135 });
      setNotice('30-minute estimate created for dispatcher review');
      await refresh();
    } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  };

  const sendWarning = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      const result = await request(`/api/warnings/${selected.id}`, { languages: ['en'], message_key: 'wildfire_targeted_warning' },
        { 'Idempotency-Key': crypto.randomUUID() });
      setNotice(`${result.recipients} opted-in warning calls queued in mock mode`);
      await refresh();
    } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  };

  const toggleOverflow = async () => {
    setBusy(true);
    try {
      const response = await fetch(`${API}/api/settings`, {
        method: 'PUT', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ overflow_enabled: !settings.overflow_enabled }),
      });
      if (!response.ok) throw new Error('Could not change overflow setting');
      setSettings(await response.json());
      setNotice(`Overflow ${!settings.overflow_enabled ? 'enabled' : 'disabled'} by dispatcher`);
    } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  };

  const mergeAction = async action => {
    if (!relatedMerge) return;
    setBusy(true);
    try {
      await request(`/api/merges/${relatedMerge.id}/${action}`, {});
      setNotice(action === 'accept' ? 'Merge accepted by dispatcher' : action === 'undo' ? 'Merge undone' : 'Reports kept separate');
      await refresh();
    } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  };

  const jumpIn = async () => {
    if (!selected || !liveCall) { setNotice('No live call to jump into'); return; }
    setBusy(true);
    try {
      const result = await request(`/api/incidents/${selected.id}/jump-in`, { actor: 'dispatcher' });
      setHandoff({ incident_id: selected.id, summary: result.summary, call_id: result.call_id });
      setNotice('JUMP IN · you are live with the caller');
      await refresh();
    } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  };

  const handBack = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await request(`/api/incidents/${selected.id}/hand-back`, { actor: 'dispatcher' });
      setHandoff(null);
      setNotice('Handed back · AGNI callback path (mock)');
      await refresh();
    } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  };

  const signClose = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await request(`/api/incidents/${selected.id}/report/sign`, { actor: 'dispatcher', edits: '' });
      setNotice('After-action signed · incident closed');
      await refresh();
    } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  };

  const primaryAction = () => {
    if (!selected) return;
    if (selected.status === 'possible') return confirmFire();
    if (selected.status === 'confirmed') return approveDispatch();
    if (selectedRing && ['confirmed', 'dispatched'].includes(selected.status)) return sendWarning();
  };

  useEffect(() => {
    const onKey = event => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      const key = event.key.toLowerCase();
      if (event.key === 'Enter') { event.preventDefault(); primaryAction(); }
      if (key === 'c') confirmFire();
      if (key === 'a') approveDispatch();
      if (key === 'j') { if (humanOnCall) handBack(); else jumpIn(); }
      if (key === 'w') sendWarning();
      if (key === 'm') mergeAction('accept');
      if (key === 'n') mergeAction('keep-apart');
      if (key === 'u' && relatedMerge?.state === 'accepted') mergeAction('undo');
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selected, settings, busy, relatedMerge, selectedRing, liveCall, humanOnCall]);

  const cameraItems = cameras.length ? cameras.slice(0, 3) : [
    { id: 'camera-unknown-1', name: 'CAMERA FEED', site: settings.mode === 'mock' ? 'Awaiting replay fixture' : 'No nearby feed', online: 'unknown' },
    { id: 'camera-unknown-2', name: 'CAMERA FEED', site: 'Availability unknown', online: 'unknown' },
    { id: 'camera-unknown-3', name: 'CAMERA FEED', site: 'Availability unknown', online: 'unknown' },
  ];
  const callerLines = calls[selected?.id]?.lines || [];
  const evidence = selected?.evidence || [];
  const measured = proof.sim
    ? `${proof.sim.calls || proof.sim.n || '—'} → ${proof.sim.incidents || proof.sim.visible_incidents || '—'}`
    : '— not measured yet';
  const liveCount = (state.calls || []).filter(c => c.state === 'live' || c.state === 'human').length;

  return <main className="console-shell">
    <header className="topbar">
      <div className="brand"><span className="brand-mark">A</span><span>AGNI<small> INCIDENT COMMAND</small></span></div>
      <div className="top-meta">
        <span className={`connection ${connection}`}><i />{connection === 'live' ? 'EVENT STREAM CONNECTED' : connection.toUpperCase()}</span>
        <span className="region-label">Overflow {settings.overflow_enabled ? 'ON' : 'OFF'} · {liveCount} live calls</span>
        <span className="mode-chip">{settings.mode === 'mock' ? 'PRACTICE' : 'LIVE · UNVERIFIED'}</span>
        <span className="proof-chip" title="Reads sim.json / eval.json only">Headline: {measured}</span>
      </div>
      <button className={`overflow-toggle ${settings.overflow_enabled ? 'on' : ''}`} onClick={toggleOverflow} disabled={busy}>
        <span className="toggle-dot" />911 OVERFLOW {settings.overflow_enabled ? 'ON' : 'OFF'}
      </button>
    </header>

    <section className="workspace">
      <aside className="left-rail">
        <div className="panel-heading"><span>FIRES</span><b>{incidents.length.toString().padStart(2, '0')}</b></div>
        <div className="incident-list">
          {incidents.map(item => {
            const mergeSuggested = state.merges?.some(merge => merge.state === 'suggested' && (merge.kept_id === item.id || merge.merged_id === item.id));
            const badge = newCount(item);
            return <button key={item.id} className={`incident-row ${selected?.id === item.id ? 'selected' : ''}`} onClick={() => setSelectedId(item.id)}>
              <span className={`priority-dot p${item.level || 3} ${item.status === 'possible' ? 'unverified' : ''}`} />
              <span className="incident-copy">
                <strong>{item.title || 'Possible fire report'}{badge && <span className="new-badge">{badge}</span>}</strong>
                <small>{item.status?.toUpperCase()} · {item.location_src === 'estimate' ? 'ESTIMATE' : item.lat ? 'PINNED' : 'UNPINNED'}</small>
                <em>{item.why_line || 'Caller report · evidence not checked'}</em>
                {mergeSuggested && <small className="merge-flag">SUGGESTED MERGE · M ACCEPT · N KEEP</small>}
              </span>
              <span className="incident-level">P{item.level || 3}</span>
            </button>;
          })}
          {!incidents.length && <div className="empty-queue">No active fire rows.<br />Signals and callers appear here.</div>}
        </div>
        <div className="panel-heading subheading"><span>LIVE CALL</span><span className="live-label">{callerLines.length || liveCall ? 'ACTIVE' : 'WAITING'}</span></div>
        <div className="call-card">
          {calls[selected?.id] || liveCall ? <>
            <div className="call-meta">
              <span className="lang-pill">{(calls[selected?.id]?.language || liveCall?.language || 'en').toUpperCase()}</span>
              <span>{liveCall?.state === 'human' ? 'HUMAN ON LINE' : (calls[selected?.id]?.direction || liveCall?.direction || 'INBOUND')}</span>
            </div>
            {handoff?.incident_id === selected?.id && <div className="handoff-card"><span className="eyebrow">YOU'RE LIVE</span><p>{handoff.summary}</p></div>}
            <div className="transcript-lines">{callerLines.map((line, index) => <p key={`${line.ts || ''}-${index}`}><b>{line.speaker?.toUpperCase()}</b>{line.text}</p>)}
              {!callerLines.length && <p className="muted">Call connected. Transcript will appear here.</p>}</div>
          </> : <p className="muted">No active call for this fire.</p>}
          {humanOnCall
            ? <button className="takeover-button live" onClick={handBack} disabled={busy}>J <span>HAND BACK</span><small>CALLBACK TO AGENT</small></button>
            : <button className="takeover-button" onClick={jumpIn} disabled={busy || !liveCall}>J <span>JUMP IN</span><small>{liveCall ? 'TAKE CALL' : 'NO LIVE CALL'}</small></button>}
        </div>
        <div className="queue-footer"><span className="green-led" />{notice}</div>
      </aside>

      <section className="map-column">
        <div className="map-head"><div><span className="eyebrow">TACTICAL VIEW · CARTO DARK MATTER</span><h1>{selected?.title || 'San Diego response area'}</h1></div>
          <span className="map-update">{selected?.location_src === 'estimate' ? 'ESTIMATE' : settings.mode === 'mock' ? 'MAP · PRACTICE' : 'MAP · LIVE-UNVERIFIED'}</span></div>
        <div className="map-canvas leaflet-host" ref={mapNode} />
        <div className="map-legend"><span><i className="legend-caller" />FIRE</span><span><i className="legend-unit" />UNIT</span><span><i className="legend-estimate" />SIGNAL / RING</span></div>
        <div className="camera-section">
          <div className="panel-heading camera-heading"><span>NEAREST CAMERA CHECK</span><small>{cameras.length ? `${cameras.length} FEEDS` : 'FEED STATUS UNKNOWN'}</small></div>
          <div className="camera-wall">{cameraItems.map((cam, index) => <article className="camera-tile" key={cam.id || index}>
            {cam.image ? <img src={cam.image} alt={`${cam.name || 'Camera'} still`} /> : <div className="camera-placeholder"><span className="camera-reticle">◎</span><b>{settings.mode === 'mock' ? 'REPLAY NOT LOADED' : 'NO FRAME'}</b><small>UNKNOWN · NEVER MEANS SAFE</small></div>}
            <div className="camera-caption"><span>{cam.name || `CAM ${String(index + 1).padStart(2, '0')}`}</span><small>{cam.site || cam.location || 'LOCATION UNKNOWN'}</small></div>
          </article>)}</div>
        </div>
      </section>

      <aside className="right-rail">
        <section className="action-panel"><div className="panel-heading"><span>EVIDENCE & ACTION</span><span className="unknown-key"><i />UNKNOWN</span></div>
          <div className="evidence-list">
            {['callers', 'cameras', 'wind', 'firms', 'nifc'].map(source => {
              const row = evidence.find(item => item.source === source || item.source === 'caller_location' && source === 'callers');
              const status = row?.state || 'unknown';
              return <div className="evidence-row" key={source}><span className={`evidence-dot ${status}`} /><span><b>{source === 'firms' ? 'SATELLITE · FIRMS' : source.toUpperCase()}</b><small>{row?.detail || (status === 'unknown' ? 'Not checked · status unknown' : 'No supporting evidence')}</small></span><time>{row?.age_s == null ? '—' : `${Math.floor(row.age_s / 60)}m`}</time></div>;
            })}
          </div>
          <div className="why-card"><span className="eyebrow">WHY THIS PIN</span><p>{selected?.why_line || (selected?.lat ? 'Caller report · no other source has been checked' : 'Caller report · landmark needs a coordinate match')}</p></div>
          {relatedMerge && <div className="merge-card"><span className="eyebrow">POSSIBLE DUPLICATE</span><p>{relatedMerge.state === 'accepted' ? 'Merge accepted. You can undo it.' : `Reports are within ${relatedMerge.distance_m} m and ${Math.round(relatedMerge.dt_s / 60)} min.`}</p>
            <div><button disabled={busy || relatedMerge.state !== 'suggested'} onClick={() => mergeAction('accept')}>M · ACCEPT</button><button disabled={busy || relatedMerge.state !== 'suggested'} onClick={() => mergeAction('keep-apart')}>N · KEEP APART</button>{relatedMerge.state === 'accepted' && <button disabled={busy} onClick={() => mergeAction('undo')}>U · UNDO</button>}</div>
          </div>}
          {route && <div className="route-card"><span className="eyebrow">ROUTE RESULT</span>{route.units?.[0] ? <p>{route.units[0].callsign} · {route.units[0].route_kind} route · estimate only</p> : <p>No available unit found</p>}{route.refused?.length ? <small>Refused: {route.refused.map(r => r.reason || r.name).join('; ')}</small> : null}{route.note && <small>{route.note}</small>}</div>}
          {selectedRing && <div className="route-card"><span className="eyebrow">SPREAD RING</span><p>{selectedRing.minutes}-min estimate · downwind model</p><small>Human review required before a warning.</small></div>}
          <div className="human-actions">
            <button className="confirm-button" disabled={!selected || selected.status === 'confirmed' || selected.status === 'dispatched' || busy} onClick={confirmFire}><kbd>⏎/C</kbd>{selected?.status === 'confirmed' || selected?.status === 'dispatched' ? 'FIRE CONFIRMED' : 'CONFIRM FIRE'}</button>
            <button className="dispatch-button" disabled={!selected || selected.status !== 'confirmed' || busy} onClick={approveDispatch}><kbd>A</kbd>APPROVE DISPATCH</button>
            <button className="ring-button" disabled={!selected?.lat || !selected?.lon || busy} onClick={createRing}>CREATE 30-MIN ESTIMATE</button>
            <div className="disabled-actions">
              <button disabled={!selectedRing || !['confirmed','dispatched'].includes(selected?.status) || busy} onClick={sendWarning}><kbd>W</kbd>SEND WARNING</button>
              <button disabled={!selected || busy} onClick={signClose}><kbd>S</kbd>SIGN & CLOSE</button>
            </div>
            <small className="human-note">Fire, dispatch and warning actions need a dispatcher.</small>
          </div>
        </section>
        <section className="operations-card"><div className="panel-heading"><span>OPERATIONS</span><span className="practice-pill">{settings.mode === 'mock' ? 'MOCK' : 'LIVE-UNVERIFIED'}</span></div>
          <div className="ops-row"><span>Overflow line</span><strong className={settings.overflow_enabled ? 'text-green' : 'text-amber'}>{settings.overflow_enabled ? 'ENABLED' : 'DISABLED'}</strong></div>
          <div className="ops-row"><span>Measured proof</span><strong>{proof.sim ? 'sim.json' : 'not measured yet'}</strong></div>
          <div className="ops-row"><span>Data age</span><strong>{state.feeds?.status === 'mock' ? 'MOCK DATA' : 'UNKNOWN'}</strong></div>
          <div className="ops-alert"><span>!</span>Unknown evidence is gray. A missing feed cannot mean safe.</div>
        </section>
      </aside>
    </section>
    <footer className="page-footer"><span>AGNI · 911 OVERFLOW SUPPORT · NOT A 911 REPLACEMENT</span><span>KEYS: ⏎ PRIMARY · C CONFIRM · A APPROVE · J JUMP/HAND BACK · W WARN · M/N MERGE · U UNDO</span></footer>
  </main>;
}

createRoot(document.getElementById('root')).render(<App />);
