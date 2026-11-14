import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
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

function project(lat, lon) {
  if (!Number.isFinite(Number(lat)) || !Number.isFinite(Number(lon))) return {};
  // Approximate service-area grid for San Diego. It is not a route map.
  const x = Math.max(7, Math.min(93, ((Number(lon) + 117.55) / 0.7) * 100));
  const y = Math.max(8, Math.min(92, ((33.05 - Number(lat)) / 0.55) * 100));
  return { left: `${x}%`, top: `${y}%` };
}

function App() {
  const [state, setState] = useState({ incidents: [], units: [], hazards: [], last_seq: 0 });
  const [settings, setSettings] = useState({ overflow_enabled: false, mode: 'mock' });
  const [selectedId, setSelectedId] = useState(null);
  const [calls, setCalls] = useState({});
  const [cameras, setCameras] = useState([]);
  const [notice, setNotice] = useState('Starting local command view');
  const [connection, setConnection] = useState('connecting');
  const [busy, setBusy] = useState(false);
  const [route, setRoute] = useState(null);
  const headers = useMemo(() => ({ ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}) }), []);
  const incidents = state.incidents || [];
  const selected = incidents.find(item => item.id === selectedId) || incidents[0] || null;
  const relatedMerge = state.merges?.find(item => item.kept_id === selected?.id || item.merged_id === selected?.id);
  const selectedRing = state.rings?.find(item => item.incident_id === selected?.id);

  const refresh = useCallback(async () => {
    const [stateRes, settingsRes] = await Promise.all([
      fetch(`${API}/api/state`, { headers }),
      fetch(`${API}/api/settings`, { headers }),
    ]);
    if (!stateRes.ok || !settingsRes.ok) throw new Error('Console access failed. Check the API and operator token.');
    const [nextState, nextSettings] = await Promise.all([stateRes.json(), settingsRes.json()]);
    setState(nextState);
    setSettings(nextSettings);
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
      const seen = Number(localStorage.getItem('agni.eventSeq') || 0);
      if (seq && seq <= seen) return;
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
      setNotice(`${payload.type.replaceAll('.', ' ')} · ${new Date(payload.ts).toLocaleTimeString()}`);
      refresh().catch(() => {});
    };
    EVENT_TYPES.forEach(type => feed.addEventListener(type, onEvent));
    return () => feed.close();
  }, [refresh]);

  useEffect(() => {
    if (!selected?.lat || !selected?.lon) { setCameras([]); setRoute(null); return; }
    const query = new URLSearchParams({ lat: selected.lat, lon: selected.lon, n: 3 });
    fetch(`${API}/api/cameras?${query}`, { headers }).then(r => r.ok ? r.json() : { cameras: [] })
      .then(result => setCameras(result.cameras || [])).catch(() => setCameras([]));
  }, [selected?.id, selected?.lat, selected?.lon, headers]);

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
      setNotice(`Dispatch approved · ${unit.callsign} · route ${unit.route_kind}`); await refresh();
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

  useEffect(() => {
    const onKey = event => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      if (event.key.toLowerCase() === 'c') confirmFire();
      if (event.key.toLowerCase() === 'a') approveDispatch();
      if (event.key.toLowerCase() === 'j') setNotice('JUMP IN transfer is not connected yet');
      if (event.key.toLowerCase() === 'w') sendWarning();
      if (event.key.toLowerCase() === 'm') mergeAction('accept');
      if (event.key.toLowerCase() === 'n') mergeAction('keep-apart');
      if (event.key.toLowerCase() === 'u' && relatedMerge?.state === 'accepted') mergeAction('undo');
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selected, settings, busy, relatedMerge, selectedRing]);

  const cameraItems = cameras.length ? cameras.slice(0, 3) : [
    { id: 'camera-unknown-1', name: 'CAMERA FEED', site: settings.mode === 'mock' ? 'Awaiting replay fixture' : 'No nearby feed', online: 'unknown' },
    { id: 'camera-unknown-2', name: 'CAMERA FEED', site: 'Availability unknown', online: 'unknown' },
    { id: 'camera-unknown-3', name: 'CAMERA FEED', site: 'Availability unknown', online: 'unknown' },
  ];
  const callerLines = calls[selected?.id]?.lines || [];
  const evidence = selected?.evidence || [];

  return <main className="console-shell">
    <header className="topbar">
      <div className="brand"><span className="brand-mark">A</span><span>AGNI<small> INCIDENT COMMAND</small></span></div>
      <div className="top-meta"><span className={`connection ${connection}`}><i />{connection === 'live' ? 'EVENT STREAM CONNECTED' : connection.toUpperCase()}</span>
        <span className="region-label">SAN DIEGO REGION</span><span className="mode-chip">{settings.mode === 'mock' ? 'PRACTICE' : 'LIVE · UNVERIFIED'}</span></div>
      <button className={`overflow-toggle ${settings.overflow_enabled ? 'on' : ''}`} onClick={toggleOverflow} disabled={busy}>
        <span className="toggle-dot" />911 OVERFLOW {settings.overflow_enabled ? 'ON' : 'OFF'}
      </button>
    </header>

    <section className="workspace">
      <aside className="left-rail">
        <div className="panel-heading"><span>INCIDENT QUEUE</span><b>{incidents.length.toString().padStart(2, '0')}</b></div>
        <div className="incident-list">
          {incidents.map(item => <button key={item.id} className={`incident-row ${selected?.id === item.id ? 'selected' : ''}`} onClick={() => setSelectedId(item.id)}>
            <span className={`priority-dot p${item.level || 3}`} />
            <span className="incident-copy"><strong>{item.title || 'Possible fire report'}</strong>
              <small>{item.location_src === 'estimate' ? 'ESTIMATED LOCATION' : item.lat ? 'CALLER LOCATION' : 'LOCATION PENDING'}</small>
              <em>{item.why_line || 'Caller report · evidence not checked'}</em>
              {state.merges?.some(merge => merge.state === 'suggested' && (merge.kept_id === item.id || merge.merged_id === item.id)) && <small className="merge-flag">POSSIBLE DUPLICATE · REVIEW</small>}
            </span>
            <span className="incident-level">P{item.level || 3}</span>
          </button>)}
          {!incidents.length && <div className="empty-queue">No active incident rows.<br />New reports appear here.</div>}
        </div>
        <div className="panel-heading subheading"><span>LIVE CALL</span><span className="live-label">{callerLines.length ? 'ACTIVE' : 'WAITING'}</span></div>
        <div className="call-card">
          {calls[selected?.id] ? <>
            <div className="call-meta"><span>{calls[selected.id].language?.toUpperCase() || 'LANGUAGE UNKNOWN'}</span><span>{calls[selected.id].direction || 'INBOUND'}</span></div>
            <div className="transcript-lines">{callerLines.map((line, index) => <p key={`${line.ts || ''}-${index}`}><b>{line.speaker?.toUpperCase()}</b>{line.text}</p>)}
              {!callerLines.length && <p className="muted">Call connected. Transcript will appear here.</p>}</div>
          </> : <p className="muted">No active call for this incident.</p>}
          <button className="takeover-button" onClick={() => setNotice('JUMP IN transfer is not connected yet')}>J <span>JUMP IN</span><small>TRANSFER NOT CONNECTED</small></button>
        </div>
        <div className="queue-footer"><span className="green-led" />{notice}</div>
      </aside>

      <section className="map-column">
        <div className="map-head"><div><span className="eyebrow">TACTICAL VIEW</span><h1>{selected?.title || 'San Diego response area'}</h1></div>
          <span className="map-update">{selected?.location_src === 'estimate' ? 'ESTIMATE' : 'MAP · PRACTICE'}</span></div>
        <div className="map-canvas">
          <div className="map-grid" />
          <svg className="roads" viewBox="0 0 900 600" preserveAspectRatio="none" aria-hidden="true">
            <path d="M20 110 C180 130 250 90 420 126 S720 180 890 142" />
            <path d="M-30 250 C160 225 270 272 420 244 S700 208 930 260" />
            <path d="M20 430 C210 390 280 445 480 410 S710 390 900 430" />
            <path d="M175 -15 C155 140 205 230 190 350 S170 510 215 630" />
            <path d="M520 -10 C495 120 535 250 500 380 S515 530 540 620" />
            <path d="M760 -10 C735 130 775 255 742 380 S760 520 790 620" />
          </svg>
          <div className="map-coord coord-a">SAN DIEGO · SERVICE AREA GRID</div><div className="map-coord coord-b">SCHEMATIC · NOT A ROUTE MAP</div>
          {selected?.lat != null && selected?.lon != null ? <div className="map-pin caller-pin" style={project(selected.lat, selected.lon)}><span /><b>CALLER REPORT</b></div> : <div className="location-pending"><span>LOCATION PENDING</span><small>Landmark captured · coordinate not verified</small></div>}
          {state.units?.map(unit => <div key={unit.id} className="unit-pin" style={project(unit.lat, unit.lon)} title={unit.callsign}><span>+</span><small>{unit.callsign}</small></div>)}
          {selected?.location_src === 'estimate' && <div className="estimate-ring" style={project(selected.lat, selected.lon)} aria-label="Estimated location uncertainty" />}
          <div className="map-scale">N ↑ &nbsp;&nbsp; 1 KM <span /></div>
        </div>
        <div className="map-legend"><span><i className="legend-caller" />CALLER</span><span><i className="legend-unit" />AVAILABLE UNIT</span><span><i className="legend-estimate" />ESTIMATE</span></div>
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
              const row = evidence.find(item => item.source === source);
              const status = row?.state || 'unknown';
              return <div className="evidence-row" key={source}><span className={`evidence-dot ${status}`} /><span><b>{source === 'firms' ? 'SATELLITE · FIRMS' : source.toUpperCase()}</b><small>{row?.detail || (status === 'unknown' ? 'Not checked · status unknown' : 'No supporting evidence')}</small></span><time>{row?.age_s == null ? '—' : `${Math.floor(row.age_s / 60)}m`}</time></div>;
            })}
          </div>
          <div className="why-card"><span className="eyebrow">WHY THIS PIN</span><p>{selected?.why_line || (selected?.lat ? 'Caller report · no other source has been checked' : 'Caller report · landmark needs a coordinate match')}</p></div>
          {relatedMerge && <div className="merge-card"><span className="eyebrow">POSSIBLE DUPLICATE</span><p>{relatedMerge.state === 'accepted' ? 'Merge accepted. You can undo it.' : `Reports are within ${relatedMerge.distance_m} m and ${Math.round(relatedMerge.dt_s / 60)} min.`}</p>
            <div><button disabled={busy || relatedMerge.state !== 'suggested'} onClick={() => mergeAction('accept')}>M · ACCEPT</button><button disabled={busy || relatedMerge.state !== 'suggested'} onClick={() => mergeAction('keep-apart')}>N · KEEP APART</button>{relatedMerge.state === 'accepted' && <button disabled={busy} onClick={() => mergeAction('undo')}>U · UNDO</button>}</div>
          </div>}
          {route && <div className="route-card"><span className="eyebrow">ROUTE RESULT</span>{route.units?.[0] ? <p>{route.units[0].callsign} · {route.units[0].route_kind} route · estimate only</p> : <p>No available unit found</p>}{route.note && <small>{route.note}</small>}</div>}
          {selectedRing && <div className="route-card"><span className="eyebrow">SPREAD RING</span><p>{selectedRing.minutes}-min estimate · downwind model</p><small>Human review required before a warning.</small></div>}
          <div className="human-actions">
            <button className="confirm-button" disabled={!selected || selected.status === 'confirmed' || selected.status === 'dispatched' || busy} onClick={confirmFire}><kbd>C</kbd>{selected?.status === 'confirmed' || selected?.status === 'dispatched' ? 'FIRE CONFIRMED' : 'CONFIRM FIRE'}</button>
            <button className="dispatch-button" disabled={!selected || selected.status !== 'confirmed' || busy} onClick={approveDispatch}><kbd>A</kbd>APPROVE DISPATCH</button>
            <button className="ring-button" disabled={!selected?.lat || !selected?.lon || busy} onClick={createRing}>CREATE 30-MIN ESTIMATE</button>
            <div className="disabled-actions"><button disabled={!selectedRing || !['confirmed','dispatched'].includes(selected?.status) || busy} onClick={sendWarning}><kbd>W</kbd>SEND TARGETED WARNING</button><button disabled={relatedMerge?.state !== 'accepted' || busy} onClick={() => mergeAction('undo')}><kbd>U</kbd>UNDO MERGE</button></div>
            <small className="human-note">Fire, dispatch and warning actions need a dispatcher.</small>
          </div>
        </section>
        <section className="operations-card"><div className="panel-heading"><span>OPERATIONS</span><span className="practice-pill">{settings.mode === 'mock' ? 'MOCK' : 'LIVE-UNVERIFIED'}</span></div>
          <div className="ops-row"><span>Overflow line</span><strong className={settings.overflow_enabled ? 'text-green' : 'text-amber'}>{settings.overflow_enabled ? 'ENABLED' : 'DISABLED'}</strong></div>
          <div className="ops-row"><span>Fire confirmation</span><strong>HUMAN REQUIRED</strong></div>
          <div className="ops-row"><span>Data age</span><strong>{state.feeds?.status === 'mock' ? 'MOCK DATA' : 'UNKNOWN'}</strong></div>
          <div className="ops-alert"><span>!</span>Unknown evidence is gray. A missing feed cannot mean safe.</div>
        </section>
      </aside>
    </section>
    <footer className="page-footer"><span>AGNI · 911 OVERFLOW SUPPORT · NOT A 911 REPLACEMENT</span><span>KEYS: C CONFIRM · A APPROVE · J JUMP IN · W WARN · U UNDO</span></footer>
  </main>;
}

createRoot(document.getElementById('root')).render(<App />);
