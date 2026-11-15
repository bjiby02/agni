import React, { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import L from 'leaflet';
import QRCode from 'qrcode';
import 'leaflet/dist/leaflet.css';
import './styles.css';

// Same origin when FastAPI serves the built console; the Vite dev server talks to the local API.
const API = import.meta.env.VITE_API_URL || (location.port === '5173' ? 'http://127.0.0.1:8000' : '');
const TOKEN = (() => { try { return localStorage.getItem('agni.operatorToken') || ''; } catch { return ''; } })();
const AUTH = TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {};
const EVENT_TYPES = [
  'signal.new', 'call.started', 'call.transcript', 'incident.created', 'incident.merge_suggested',
  'incident.merged', 'incident.unmerged', 'incident.confirmed', 'triage.result', 'route.ready', 'unit.dispatched',
  'handoff.started', 'handoff.ended', 'ring.updated', 'warning.sent', 'surge.stats', 'incident.closed',
  'bearing.added', 'estimate.updated', 'cameras.selected', 'satellite.result', 'evidence.updated',
  'rescue.requested', 'wind.updated', 'hazards.updated', 'log.anchored', 'ops.mode',
];
const CENTER = [32.885, -117.2];

async function api(path, { method = 'GET', body, headers = {} } = {}) {
  const res = await fetch(`${API}${path}`, {
    method, headers: { ...AUTH, ...(body ? { 'Content-Type': 'application/json' } : {}), ...headers },
    body: body ? JSON.stringify(body) : method === 'POST' ? '{}' : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

// The console is a pure function of the event stream: a refresh replays from seq 0.
const initialLive = { seq: 0, calls: {}, rescues: [], handoffs: {}, routes: {}, triage: {}, surge: null };
function liveReducer(state, ev) {
  if (ev.reset) return initialLive;
  if (ev.seq && ev.seq <= state.seq) return state;
  const next = { ...state, seq: ev.seq || state.seq };
  const d = ev.data || {};
  switch (ev.type) {
    case 'ops.mode': return d.reset ? { ...initialLive, seq: next.seq } : next;
    case 'call.started': {
      const prev = next.calls[d.call_id] || {};
      return { ...next, calls: { ...next.calls, [d.call_id]: { ...prev, id: d.call_id, incident_id: ev.incident_id, language: d.language, started: ev.ts, lines: prev.lines || [] } } };
    }
    case 'call.transcript': {
      const prev = next.calls[d.call_id] || { id: d.call_id, incident_id: ev.incident_id, lines: [] };
      return { ...next, calls: { ...next.calls, [d.call_id]: { ...prev, lang: d.lang || prev.lang, lines: [...prev.lines, { ...d, ts: ev.ts, seq: ev.seq }].slice(-40) } } };
    }
    case 'handoff.started': return d.call_id ? { ...next, handoffs: { ...next.handoffs, [d.call_id]: { ...d, open: true, startSeq: ev.seq } } } : next;
    case 'handoff.ended': return { ...next, handoffs: { ...next.handoffs, [d.call_id]: { ...(next.handoffs[d.call_id] || {}), ...d, open: false, endSeq: ev.seq } } };
    case 'route.ready': return { ...next, routes: { ...next.routes, [ev.incident_id]: d } };
    case 'triage.result': return { ...next, triage: { ...next.triage, [ev.incident_id]: d } };
    case 'rescue.requested': return d.lat != null ? { ...next, rescues: [...next.rescues, { ...d, incident_id: ev.incident_id, ts: ev.ts }] } : next;
    case 'surge.stats': return { ...next, surge: d };
    default: return next;
  }
}

function useAgni() {
  const [state, setState] = useState({ incidents: [], units: [], hazards: [], merges: [], rings: [], ops: {}, feeds: {} });
  const [settings, setSettings] = useState({ overflow_enabled: false, mode: 'mock' });
  const [live, dispatch] = useReducer(liveReducer, initialLive);
  const [connection, setConnection] = useState('connecting');
  const [last, setLast] = useState('Starting');
  const refresh = useCallback(async () => {
    const [s, st] = await Promise.all([api('/api/state'), api('/api/settings')]);
    setState(s); setSettings(st);
  }, []);
  useEffect(() => {
    refresh().catch(e => setLast(e.message));
    const feed = new EventSource(`${API}/api/stream?since=0${TOKEN ? `&token=${encodeURIComponent(TOKEN)}` : ''}`);
    feed.onopen = () => setConnection('live');
    feed.onerror = () => setConnection('reconnecting');
    let pending = null;
    const onEvent = e => {
      const ev = JSON.parse(e.data);
      dispatch(ev);
      setLast(`${ev.type} · ${new Date(ev.ts.endsWith('Z') ? ev.ts : ev.ts + 'Z').toLocaleTimeString()}`);
      clearTimeout(pending); pending = setTimeout(() => refresh().catch(() => {}), 120);
    };
    EVENT_TYPES.forEach(t => feed.addEventListener(t, onEvent));
    return () => { feed.close(); clearTimeout(pending); };
  }, [refresh]);
  return { state, settings, setSettings, live, connection, last, refresh };
}

function MapView({ state, live, selected, onSelect }) {
  const el = useRef(null);
  const map = useRef(null);
  const layers = useRef(null);
  useEffect(() => {
    map.current = L.map(el.current, { zoomControl: false, attributionControl: true }).setView(CENTER, 12);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap &copy; CARTO', subdomains: 'abcd', maxZoom: 19,
    }).addTo(map.current);
    L.control.zoom({ position: 'bottomright' }).addTo(map.current);
    layers.current = L.layerGroup().addTo(map.current);
    return () => map.current.remove();
  }, []);
  useEffect(() => {
    const g = layers.current; if (!g) return;
    g.clearLayers();
    (state.hazards || []).forEach(h => {
      if (h.geometry?.type === 'LineString') {
        L.polyline(h.geometry.coordinates.map(([lon, lat]) => [lat, lon]), { color: '#FF9F0A', weight: 4, dashArray: '2 6', opacity: .9 })
          .bindTooltip(`${h.title} · ${h.source}`).addTo(g);
      }
    });
    (state.rings || []).forEach(r => {
      const coords = r.geometry?.coordinates?.[0];
      if (coords) L.polygon(coords.map(([lon, lat]) => [lat, lon]), { color: '#FF9F0A', weight: 1, fillOpacity: .18, dashArray: '4 4' })
        .bindTooltip(`${r.minutes}-min estimate`, { permanent: false }).addTo(g);
    });
    (state.signals || []).forEach(sg => {
      if (sg.lat == null) return;
      L.circleMarker([sg.lat, sg.lon], { radius: 5, color: '#8E8E93', weight: 1, dashArray: '2 2', fillOpacity: 0 })
        .bindTooltip(`Unverified ${sg.source} post · ${sg.classifier}${sg.url.startsWith('https://practice.invalid') ? ' · practice fixture' : ''}`).addTo(g);
    });
    (state.units || []).forEach(u => L.circleMarker([u.lat, u.lon], { radius: 5, color: '#fff', weight: 1.5, fillColor: u.status === 'available' ? '#fff' : '#8E8E93', fillOpacity: .9 })
      .bindTooltip(`${u.callsign} · ${u.status}`).addTo(g));
    const route = selected && live.routes[selected.id];
    if (route?.line?.coordinates) {
      L.polyline(route.line.coordinates.map(([lon, lat]) => [lat, lon]), { color: '#fff', weight: 2.5, dashArray: '6 6' })
        .bindTooltip('Direction only · straight-line estimate').addTo(g);
    }
    if (route?.shelter) L.circleMarker([route.shelter.lat, route.shelter.lon], { radius: 8, color: '#fff', weight: 2, fillColor: '#fff', fillOpacity: .25 })
      .bindTooltip(`Shelter · ${route.shelter.name}`).addTo(g);
    (state.incidents || []).forEach(i => {
      if (i.lat == null || i.lon == null) return;
      const confirmed = ['confirmed', 'dispatched'].includes(i.status);
      if (i.location_src === 'estimate') {
        L.circle([i.lat, i.lon], { radius: Math.max(150, i.estimate_m || 300), color: '#FF9F0A', weight: 1.5, fillOpacity: .12 })
          .bindTooltip(i.why_line || 'Estimate').addTo(g);
      }
      L.circleMarker([i.lat, i.lon], {
        radius: selected?.id === i.id ? 10 : 7, weight: 2,
        color: confirmed ? '#FF3B30' : '#8E8E93', fillColor: confirmed ? '#FF3B30' : '#0A0A0B', fillOpacity: confirmed ? .9 : .6,
      }).on('click', () => onSelect(i.id)).bindTooltip(`${i.title || 'Report'} · ${confirmed ? 'confirmed by human' : 'not confirmed'}`).addTo(g);
    });
    live.rescues.forEach(r => L.marker([r.lat, r.lon], { icon: L.divIcon({ className: 'rescue-pin', html: '<span></span>', iconSize: [18, 18] }) })
      .bindTooltip('Resident asked for help').addTo(g));
  }, [state, live, selected, onSelect]);
  useEffect(() => {
    if (map.current && selected?.lat != null) map.current.flyTo([selected.lat, selected.lon], Math.max(map.current.getZoom(), 13), { duration: .6 });
  }, [selected?.id, selected?.lat, selected?.lon]);
  return <div className="map" ref={el} />;
}

function age(ts) {
  if (!ts) return 'time unknown';
  const s = Math.max(0, (Date.now() - new Date(ts).getTime()) / 1000);
  return s < 60 ? `${Math.round(s)} s old` : `${Math.round(s / 60)} min old`;
}

function CameraWall({ selected, mock }) {
  const [cams, setCams] = useState([]);
  useEffect(() => {
    if (selected?.lat == null) { setCams([]); return; }
    api(`/api/cameras?lat=${selected.lat}&lon=${selected.lon}&n=3`).then(r => setCams(r.cameras || [])).catch(() => setCams([]));
  }, [selected?.id, selected?.lat, selected?.lon]);
  const tiles = cams.length ? cams.slice(0, 3) : [0, 1, 2].map(i => ({ id: `none-${i}` }));
  return <div className="camera-wall">{tiles.map((c, i) => {
    const stale = c.fetched_at && (Date.now() - new Date(c.fetched_at).getTime()) > 600000;
    return <figure className={`cam ${stale ? 'stale' : ''}`} key={c.id || i}>
      {c.name ? <img alt={`${c.name} still`} src={`${API}/api/cameras/${encodeURIComponent(c.id)}/frame?lat=${selected.lat}&lon=${selected.lon}${TOKEN ? `&token=${encodeURIComponent(TOKEN)}` : ''}`} onError={e => { e.currentTarget.style.display = 'none'; }} />
        : <div className="cam-empty"><b>{mock ? 'Replay not loaded' : 'No camera nearby'}</b><small>Unknown · never means safe</small></div>}
      <figcaption><span>{c.name || `Camera ${i + 1}`}</span><small>{c.name ? `${c.label || 'Live'} · ${stale ? 'Stale · ' : ''}${age(c.fetched_at)}` : '—'}</small>
        <em className="verdict gray">Not analyzed</em></figcaption>
    </figure>;
  })}</div>;
}

function Evidence({ incident, seq }) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    if (!incident) { setRows([]); return; }
    api(`/api/incidents/${incident.id}/evidence`).then(r => setRows(r.rows || [])).catch(() => setRows([]));
  }, [incident?.id, seq]);
  const names = { public: 'Public posts', callers: 'Callers', caller_location: 'Caller landmark', cameras: 'Cameras', wind: 'Wind', firms: 'Satellite · FIRMS', nifc: 'Perimeter · NIFC' };
  return <div className="evidence">{rows.map(r => <div className="ev-row" key={r.source}>
    <i className={`dot ${r.state === 'agree' ? 'agree' : r.state === 'partial' ? 'partial' : 'unknown'}`} />
    <span><b>{names[r.source] || r.source}</b><small>{r.detail}</small></span>
  </div>)}</div>;
}

function Report({ incident, onDone }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { setReport(null); setError(''); if (incident) api(`/api/incidents/${incident.id}/report`).then(setReport).catch(() => {}); }, [incident?.id]);
  if (!incident) return null;
  const close = () => api(`/api/incidents/${incident.id}/close`, { method: 'POST' }).then(setReport).catch(e => setError(e.message));
  const sign = () => api(`/api/incidents/${incident.id}/report/sign`, { method: 'POST', body: { actor: 'dispatcher' } })
    .then(() => api(`/api/incidents/${incident.id}/report`)).then(r => { setReport(r); onDone?.(); }).catch(e => setError(e.message));
  return <section className="card report">
    <header><span className="eyebrow">After-action</span>{report?.signed_by && <span className="pill">Signed · {report.signed_by}</span>}</header>
    {!report && <button onClick={close} disabled={incident.status !== 'dispatched'}>Close and draft report</button>}
    {report && <>
      <ol>{report.draft.map((l, i) => <li key={i}>{l}</li>)}</ol>
      <p className="clock">Signal to dispatch: {report.clock?.signal_to_dispatch_s ?? 'not measured'}{report.clock?.signal_to_dispatch_s != null ? ' s, from event timestamps' : ''}</p>
      <small className="hash">Log SHA-256 {report.log_sha256.slice(0, 20)}… · {report.events} events · {report.draft_source === 'template' ? 'template draft (Gemini not used)' : 'Gemini draft'}</small>
      {!report.signed_by && <button onClick={sign}>Sign report</button>}
    </>}
    {error && <small className="error">{error}</small>}
  </section>;
}

function Console() {
  const { state, settings, setSettings, live, connection, last, refresh } = useAgni();
  const [selectedId, setSelectedId] = useState(null);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const incidents = state.incidents || [];
  const selected = incidents.find(i => i.id === selectedId) || incidents[0] || null;
  const merge = (state.merges || []).find(m => m.kept_id === selected?.id || m.merged_id === selected?.id);
  const ring = (state.rings || []).find(r => r.incident_id === selected?.id);
  const activeCall = Object.values(live.calls).find(c => c.incident_id === selected?.id) || null;
  const handoff = activeCall ? live.handoffs[activeCall.id] : null;
  const replay = state.ops?.mode === 'replay';
  const route = selected ? live.routes[selected.id] : null;

  const act = useCallback(async (label, fn) => {
    if (busy) return; setBusy(true);
    try { const msg = await fn(); setNotice(msg || label); await refresh(); } catch (e) { setNotice(e.message); } finally { setBusy(false); }
  }, [busy, refresh]);

  const confirm = () => selected && act('Fire confirmed by dispatcher', () => api(`/api/incidents/${selected.id}/confirm`, { method: 'POST', body: { actor: 'dispatcher' } }).then(() => api(`/api/incidents/${selected.id}/route`)).then(() => 'Fire confirmed · route prepared'));
  const approve = () => selected?.status === 'confirmed' && act('Dispatch approved', async () => {
    const r = route || await api(`/api/incidents/${selected.id}/route`);
    if (!r.recommended_unit) throw new Error('No unit has a clear path');
    const d = await api(`/api/incidents/${selected.id}/dispatch`, { method: 'POST', body: { unit_id: r.recommended_unit, approved_by: 'dispatcher' }, headers: { 'Idempotency-Key': `${selected.id}:${r.recommended_unit}` } });
    return `${d.callsign || d.unit_id} dispatched by dispatcher`;
  });
  const jump = () => activeCall && act('Jump in', () => handoff?.open
    ? api(`/api/calls/${activeCall.id}/handback`, { method: 'POST', body: { actor: 'dispatcher' } }).then(r => r.banner || 'Handed back · AGNI is calling the caller back')
    : api(`/api/calls/${activeCall.id}/takeover`, { method: 'POST', body: { actor: 'dispatcher' } }).then(() => "You're live · summary on screen"));
  const warn = () => selected && ['confirmed', 'dispatched'].includes(selected.status) && act('Warning', async () => {
    if (!ring) await api(`/api/incidents/${selected.id}/ring`, { method: 'POST', body: { minutes: 30, wind_to_deg: state.feeds?.wind?.to_deg ?? 200 } });
    const w = await api(`/api/warnings/${selected.id}`, { method: 'POST', body: { languages: ['es', 'en'] }, headers: { 'Idempotency-Key': `${selected.id}:warn` } });
    return `Warning approved · ${w.recipients} opted-in homes · ${w.dial === 'mock' ? 'practice, no phone rang' : w.dial}`;
  });
  const mergeDo = action => merge && act(action, () => api(`/api/merges/${merge.id}/${action}`, { method: 'POST' }).then(() => ({ accept: 'Merge accepted', undo: 'Merge undone', 'keep-apart': 'Kept apart' })[action]));
  const toggleOverflow = () => act('Overflow', async () => {
    const r = await fetch(`${API}/api/settings`, { method: 'PUT', headers: { ...AUTH, 'Content-Type': 'application/json' }, body: JSON.stringify({ overflow_enabled: !settings.overflow_enabled }) });
    const s = await r.json(); setSettings(s); return `Overflow ${s.overflow_enabled ? 'on' : 'off'}`;
  });

  useEffect(() => {
    const onKey = e => {
      if (e.target instanceof HTMLInputElement || e.metaKey || e.ctrlKey) return;
      const k = e.key.toLowerCase();
      ({ c: confirm, a: approve, j: jump, w: warn, m: () => mergeDo('accept'), n: () => mergeDo('keep-apart'), u: () => merge?.state === 'accepted' && mergeDo('undo') })[k]?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const lines = activeCall?.lines || [];
  return <main className="shell">
    <header className="top">
      <div className="brand"><b>AGNI</b><span>911 overflow</span></div>
      {activeCall && <div className="call-pill"><i />{replay ? 'Replay · ' : ''}Live call · {(activeCall.lang || activeCall.language || '??').toUpperCase()}</div>}
      <div className="top-right">
        {replay && <span className="pill amber">{state.ops.replay_label}</span>}
        {state.ops?.safe_mode ? <span className="pill">Wi-Fi-safe · cached data</span> : null}
        <span className="pill">{settings.mode === 'mock' ? 'Practice data' : 'Live · unverified'}</span>
        <span className={`conn ${connection}`}>{connection === 'live' ? 'Connected' : connection === 'reconnecting' ? 'Reconnecting…' : 'Connecting'}</span>
        <button className={`overflow ${settings.overflow_enabled ? 'on' : ''}`} onClick={toggleOverflow}>Overflow {settings.overflow_enabled ? 'on' : 'off'}</button>
        <a className="ops-link" href="#/ops">Ops</a>
      </div>
    </header>
    <section className="grid">
      <aside className="rail left">
        <div className="section-title">Incidents <b>{incidents.length}</b></div>
        <div className="queue">{incidents.map(i => <button key={i.id} className={`row ${selected?.id === i.id ? 'sel' : ''}`} onClick={() => setSelectedId(i.id)}>
          <i className={`dot ${['confirmed', 'dispatched'].includes(i.status) ? 'red' : 'unknown'}`} />
          <span><b>{i.title || 'Possible fire report'}</b><small>{i.why_line || 'Caller report · evidence not checked'}</small>
            {(state.merges || []).some(m => m.state === 'suggested' && (m.kept_id === i.id || m.merged_id === i.id)) && <em className="chip">Possible duplicate</em>}</span>
          <span className="lvl">P{i.level}</span>
        </button>)}
          {!incidents.length && <p className="muted">Calm. No reports.</p>}</div>
        <div className="section-title">Live call {activeCall && <small>{activeCall.id.startsWith('replay-') ? 'Replay' : ''}</small>}</div>
        <div className="transcript">{lines.map(l => <p key={l.seq} className={l.speaker === 'caller' ? 'caller' : 'agent'}><b>{l.speaker === 'caller' ? 'Caller' : handoff?.startSeq && l.seq > handoff.startSeq && (!handoff.endSeq || l.seq < handoff.endSeq) ? 'Dispatcher' : 'AGNI'}</b>{l.text}</p>)}
          {!lines.length && <p className="muted">No live call for this incident.</p>}</div>
        {handoff?.open && <div className="card handoff"><span className="eyebrow">You're live</span><p>{handoff.summary}</p><button onClick={jump}><kbd>J</kbd>Hand back</button></div>}
        {handoff && !handoff.open && handoff.banner && <div className="card warnbox">{handoff.banner}</div>}
        <div className="foot">{notice || last}</div>
      </aside>
      <section className="center">
        <MapView state={state} live={live} selected={selected} onSelect={setSelectedId} />
        <div className="map-legend"><span><i className="dot unknown" />Not confirmed</span><span><i className="dot red" />Confirmed by human</span><span><i className="dot est" />Estimate</span><span><i className="dot unknown" style={{ borderStyle: 'dashed', width: 8, height: 8 }} />Public post (unverified)</span><span><i className="dash" />Closure ({state.hazards?.[0]?.source || 'none'})</span></div>
        <CameraWall selected={selected} mock={settings.mode === 'mock'} />
      </section>
      <aside className="rail right">
        <section className="card">
          <header><span className="eyebrow">Why this pin</span><span className="pill">{selected?.status || '—'}</span></header>
          <p className="why">{selected?.why_line || (selected ? 'Caller report · no other source checked' : 'Select an incident')}</p>
          <Evidence incident={selected} seq={live.seq} />
        </section>
        {merge && <section className="card"><span className="eyebrow">Possible duplicate</span>
          <p>{merge.state === 'accepted' ? 'Merged by dispatcher. You can undo it.' : `${Math.round(merge.distance_m)} m and ${Math.round(merge.dt_s / 60)} min apart.`}</p>
          <div className="btns">{merge.state === 'suggested' ? <><button onClick={() => mergeDo('accept')}><kbd>M</kbd>Merge</button><button onClick={() => mergeDo('keep-apart')}><kbd>N</kbd>Keep apart</button></> : <button onClick={() => mergeDo('undo')}><kbd>U</kbd>Undo</button>}</div>
        </section>}
        {route && <section className="card"><span className="eyebrow">Route</span>
          <p>{route.recommended_unit ? `${route.units.find(u => u.unit_id === route.recommended_unit)?.callsign} · about ${Math.round((route.units.find(u => u.unit_id === route.recommended_unit)?.eta_s || 0) / 60)} min (estimate)` : 'No unit has a clear path'}</p>
          {route.avoids?.length > 0 && <small>Avoids: {[...new Set(route.avoids)].join(', ')}</small>}
          <p>{route.shelter ? `Shelter: ${route.shelter.name}` : route.shelter_note}</p>
          {route.refused?.map(r => <small key={r.name} className="refused">✕ {r.name} · {r.reason}</small>)}
          <small className="muted">Wind: {route.wind_source}</small>
        </section>}
        <section className="actions">
          <button className="primary" disabled={!selected || selected.status !== 'possible' || busy} onClick={confirm}><kbd>C</kbd>Confirm fire</button>
          <button className="primary" disabled={selected?.status !== 'confirmed' || busy} onClick={approve}><kbd>A</kbd>Approve dispatch</button>
          <button disabled={!activeCall || busy} onClick={jump}><kbd>J</kbd>{handoff?.open ? 'Hand back' : 'Jump in'}</button>
          <button disabled={!selected || !['confirmed', 'dispatched'].includes(selected?.status) || busy} onClick={warn}><kbd>W</kbd>Warn homes in the 30-min estimate</button>
          <small className="muted">A human confirms every fire, dispatch and warning.</small>
        </section>
        <Report incident={selected} onDone={refresh} />
      </aside>
    </section>
  </main>;
}

function CamLink() {
  const [link, setLink] = useState(null);
  const [qr, setQr] = useState('');
  const [err, setErr] = useState('');
  const make = async () => {
    try {
      const st = await api('/api/state');
      const inc = st.incidents?.[0];
      if (!inc) throw new Error('No open incident yet');
      const l = await api('/api/ops/cam-link', { method: 'POST', body: { incident_id: inc.id } });
      const url = l.url || `${location.origin}${location.pathname}${l.path.slice(1)}`;
      setLink({ ...l, url, title: inc.title }); setQr(await QRCode.toDataURL(url, { margin: 1, width: 220 })); setErr('');
    } catch (e) { setErr(e.message); }
  };
  return <div className="card"><span className="eyebrow">Caller camera link</span>
    <button onClick={make}>New one-time link for the newest incident</button>
    {link && <><img className="qr" src={qr} alt="QR code for the camera page" /><small className="hash">{link.url}</small><small className="muted">Expires {new Date(link.expires_at).toLocaleTimeString()} · one upload</small></>}
    {err && <small className="error">{err}</small>}
  </div>;
}

function readHeading(e) {
  if (typeof e.webkitCompassHeading === 'number') return e.webkitCompassHeading;
  if (e.absolute && typeof e.alpha === 'number') return (360 - e.alpha) % 360;
  return null;
}

function compassWord(deg) {
  return ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][Math.round(deg / 45) % 8];
}

function CamPage({ token }) {
  const [stage, setStage] = useState('start'); // start, camera, analyzing, result, denied, failed, invalid
  const [status, setStatus] = useState(null);
  const [heading, setHeading] = useState(null);
  const [result, setResult] = useState(null);
  const video = useRef(null);
  const stream = useRef(null);
  const fix = useRef(null);
  const frame = useRef(null);
  useEffect(() => { api(`/api/cam/${token}`).then(setStatus).catch(() => setStatus({ valid: false })); }, [token]);
  useEffect(() => () => stream.current?.getTracks().forEach(t => t.stop()), []);
  const start = async () => {
    try {
      if (typeof DeviceOrientationEvent !== 'undefined' && DeviceOrientationEvent.requestPermission) await DeviceOrientationEvent.requestPermission().catch(() => {});
      const onTurn = e => { const h = readHeading(e); if (h != null) setHeading(Math.round(h)); };
      addEventListener('deviceorientationabsolute', onTurn); addEventListener('deviceorientation', onTurn);
      navigator.geolocation?.getCurrentPosition(p => { fix.current = p.coords; }, () => {}, { enableHighAccuracy: true, timeout: 8000 });
      stream.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
      setStage('camera');
      setTimeout(() => { if (video.current) { video.current.srcObject = stream.current; video.current.play(); } }, 0);
    } catch { setStage('denied'); }
  };
  const send = async blob => {
    setStage('analyzing');
    const q = new URLSearchParams();
    if (heading != null) q.set('heading_deg', String(heading % 360));
    if (fix.current) { q.set('lat', fix.current.latitude); q.set('lon', fix.current.longitude); q.set('accuracy_m', Math.round(fix.current.accuracy)); }
    try {
      const r = await fetch(`${API}/api/cam/${token}/frame?${q}`, { method: 'POST', headers: { 'Content-Type': 'image/jpeg' }, body: blob });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || 'failed');
      setResult(data); setStage('result');
    } catch { setStage('failed'); }
  };
  const capture = () => {
    const v = video.current; if (!v) return;
    const scale = Math.min(1, 1280 / Math.max(v.videoWidth, v.videoHeight));
    const c = document.createElement('canvas'); c.width = v.videoWidth * scale; c.height = v.videoHeight * scale;
    c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
    stream.current?.getTracks().forEach(t => t.stop());
    c.toBlob(b => { frame.current = b; send(b); }, 'image/jpeg', 0.7);
  };
  const unsure = result && !['smoke', 'flames'].includes(result.label);
  if (status && !status.valid) return <main className="cam-page"><h1>This link has {status.expired ? 'expired' : status.used ? 'already been used' : 'a problem'}.</h1><p>That's okay. Stay on the line and keep talking to us.</p></main>;
  return <main className="cam-page">
    <p className="eyebrow">AGNI · 911 overflow</p>
    <h1>San Diego 911 sent you this link.</h1>
    {stage === 'start' && <><p>If it is safe, point your phone at the smoke. This helps a dispatcher see it.</p><button className="big" onClick={start}>Show us what you see</button><small className="muted">We ask for the camera only after you tap.</small></>}
    {stage === 'camera' && <><video ref={video} playsInline muted className="viewfinder" />
      <div className="compass">{heading != null ? `Pointing ${compassWord(heading)} · ${heading}°` : 'Compass not available'}</div>
      <button className="big" onClick={capture}>Send this view</button></>}
    {stage === 'analyzing' && <div className="analyzing"><span className="spinner" />Looking at your photo…</div>}
    {stage === 'result' && <><h2>{unsure ? "Can't tell from the image" : result.label === 'flames' ? 'We see flames' : 'We see smoke'}</h2>
      <p>{unsure ? 'Your call still counts. A dispatcher has your report.' : 'Thank you. A dispatcher can see this now.'}</p><p className="muted">Stay on the line.</p></>}
    {stage === 'denied' && <><h2>That's okay.</h2><p>Stay on the line and keep talking to us.</p></>}
    {stage === 'failed' && <><h2>Couldn't send.</h2><p>Your photo is kept on this page.</p><button className="big" onClick={() => frame.current && send(frame.current)}>Try again</button></>}
  </main>;
}

function Ops() {
  const [status, setStatus] = useState(null);
  const [msg, setMsg] = useState('');
  const load = useCallback(() => api('/api/ops').then(setStatus).catch(e => setMsg(e.message)), []);
  useEffect(() => { load(); const t = setInterval(load, 2000); return () => clearInterval(t); }, [load]);
  const run = (label, fn) => fn().then(r => { setMsg(`${label} · ${JSON.stringify(r).slice(0, 140)}`); load(); }).catch(e => setMsg(e.message));
  const metric = (name, m) => <div className="metric" key={name}><span>{name.replaceAll('_', ' ')}</span>
    <b>{m && m.n ? `${m.value} (n=${m.n})` : 'not measured yet'}</b><small>{m?.data || m?.reason || ''}</small></div>;
  const ev = status?.proof?.eval; const sim = status?.proof?.sim;
  return <main className="ops">
    <header className="top"><div className="brand"><b>AGNI</b><span>/ops</span></div><a className="ops-link" href="#/">Console</a></header>
    <section className="ops-grid">
      <div className="card"><span className="eyebrow">Demo controls</span>
        <button onClick={() => run('Reset to Calm', () => api('/api/ops/reset', { method: 'POST' }))}>Reset to Calm</button>
        <button onClick={() => run('Replay call', () => api('/api/ops/replay', { method: 'POST', body: { name: 'call_es', speed: 1 } }))}>Play replay call (labeled)</button>
        <button onClick={() => run('Surge', () => api('/api/ops/surge', { method: 'POST', body: { n: 75, seconds: 90 } }))}>Start 75-call surge (separate database)</button>
        <button onClick={() => run('Load cached scrapes', () => api('/api/ops/poll/signals', { method: 'POST' }))}>Load public posts (Bright Data, cached in practice)</button>
        <button onClick={() => run('Wind', () => api('/api/ops/poll/wind', { method: 'POST' }))}>Check wind (NWS)</button>
        <button onClick={() => run('Satellite', () => api('/api/ops/poll/satellite', { method: 'POST' }))}>Check satellite (FIRMS)</button>
        <button onClick={() => run('Closures', () => api('/api/ops/poll/closures', { method: 'POST' }))}>Check road closures (Caltrans)</button>
        <button onClick={() => run('Wi-Fi-safe', () => api('/api/ops/safe-mode', { method: 'POST', body: { on: !status?.safe_mode } }))}>Wi-Fi-safe mode: {status?.safe_mode ? 'on' : 'off'}</button>
        <p className="muted">Mode: {status?.mode || '—'} · {status?.mock ? 'practice data' : 'live, unverified'} · cached camera stills: {status?.cached_cameras ?? 0}</p>
        <p className="muted">{msg}</p>
      </div>
      <CamLink />
      <div className="card"><span className="eyebrow">Proof panel · only measured numbers</span>
        {['merge_precision', 'triage_accuracy', 'post_precision', 'caller_personas'].map(k => metric(k, ev?.[k]))}
        <div className="metric"><span>surge: calls → incidents</span><b>{sim ? `${sim.calls} → ${sim.visible_incidents}` : 'not measured yet'}</b><small>{sim ? `${sim.accepted_merges} merges in ${sim.duration_s} s · ${sim.branch}` : 'run the surge'}</small></div>
      </div>
    </section>
  </main>;
}

function App() {
  const [route, setRoute] = useState(location.hash);
  useEffect(() => { const f = () => setRoute(location.hash); addEventListener('hashchange', f); return () => removeEventListener('hashchange', f); }, []);
  const cam = route.match(/^#\/sos\/cam\/([A-Za-z0-9_-]{8,64})/);
  if (cam) return <CamPage token={cam[1]} />;
  return route.startsWith('#/ops') ? <Ops /> : <Console />;
}

createRoot(document.getElementById('root')).render(<App />);
