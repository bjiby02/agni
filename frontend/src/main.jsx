import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './styles.css';

// Empty = same origin (Vite proxies /api → :8000). Override with VITE_API_URL if needed.
const API = import.meta.env.VITE_API_URL ?? '';
const TOKEN = localStorage.getItem('agni.operatorToken') || '';
const EVENT_TYPES = [
  'signal.new', 'call.started', 'call.transcript', 'incident.created', 'incident.merge_suggested',
  'incident.merged', 'triage.result', 'route.ready', 'unit.dispatched', 'handoff.started',
  'handoff.ended', 'ring.updated', 'warning.sent', 'surge.stats', 'incident.closed',
  'bearing.added', 'estimate.updated', 'cameras.selected', 'satellite.result', 'evidence.updated',
  'rescue.requested', 'camera.link', 'call.needs_human', 'ops.reset', 'guidance.ready',
];
const STUCK_SILENCE_S = 25;
const HUMAN_ASK_RE = /\b(human|dispatcher|operator|real person|speak to (a |someone|somebody)|transfer|jump in)\b/i;
const SILENCE_STUCK_REASONS = new Set(['silence', 'no_transcript', 'needs_human']);

function callSilenceSeconds(iid, liveStartedMs, callStartedAt, lastTranscriptAt) {
  const startedMs = liveStartedMs || callStartedAt || Date.now();
  const last = (iid && lastTranscriptAt.current[iid]) || startedMs;
  return (Date.now() - last) / 1000;
}

/** True only when takeover is warranted — not during normal agent intake Q&A. */
function evaluateCallStuck({
  incidentId,
  liveCall,
  humanOnCall,
  stuckByIncident,
  liveStartedMs,
  callStartedAt,
  lastTranscriptAt,
}) {
  if (!incidentId || !liveCall || humanOnCall) {
    return { stuck: false, reason: null };
  }
  const silentS = callSilenceSeconds(incidentId, liveStartedMs, callStartedAt, lastTranscriptAt);
  const meta = stuckByIncident[incidentId];
  const serverReason = liveCall.needs_human_reason || null;
  if (liveCall.needs_human) {
    // Ignore premature silence / no_transcript from the server during intake.
    if (serverReason === 'no_transcript') {
      const startedMs = liveStartedMs || callStartedAt || Date.now();
      if ((Date.now() - startedMs) / 1000 < 90) {
        return { stuck: false, reason: serverReason };
      }
    }
    if (SILENCE_STUCK_REASONS.has(serverReason) && silentS < STUCK_SILENCE_S) {
      return { stuck: false, reason: serverReason };
    }
    if (serverReason === 'silence' && !(incidentId && lastTranscriptAt.current[incidentId])) {
      return { stuck: false, reason: serverReason };
    }
    return { stuck: true, reason: serverReason || 'needs_human' };
  }
  if (meta?.reason === 'caller_asked_human') {
    return { stuck: true, reason: 'caller_asked_human' };
  }
  if (meta?.reason === 'silence' && silentS >= STUCK_SILENCE_S) {
    return { stuck: true, reason: 'silence' };
  }
  return { stuck: false, reason: null };
}
function pinSourceLabel(src, landmarkChip) {
  if (src === 'landmark' || /landmark list|cached San Diego/i.test(landmarkChip || '')) {
    return 'Pin from cached San Diego landmarks';
  }
  if (src === 'caller' || /caller GPS/i.test(landmarkChip || '')) {
    return 'Caller GPS';
  }
  if (src === 'geocode' || /geocode/i.test(landmarkChip || '')) {
    return 'Pin from region geocode (never invented)';
  }
  if (src === 'estimate') return 'Estimate from bearings (not a confirmed pin)';
  return null;
}

function ageLabel(iso) {
  if (!iso) return null;
  const ms = Date.now() - Date.parse(iso);
  if (Number.isNaN(ms) || ms < 0) return null;
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min`;
  return `${Math.floor(m / 60)} h`;
}

function truncate(text, n = 96) {
  const t = String(text || '').replace(/\s+/g, ' ').trim();
  if (t.length <= n) return t;
  return `${t.slice(0, n - 1)}…`;
}

function playCallChime() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.value = 660;
    gain.gain.value = 0.04;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.18);
    osc.stop(ctx.currentTime + 0.2);
    setTimeout(() => ctx.close().catch(() => {}), 300);
  } catch { /* optional */ }
}
const EVIDENCE_LABEL = {
  callers: 'Phone callers',
  caller_location: 'Phone callers',
  cameras: 'Nearby cameras',
  posts: 'Social posts',
  firms: 'Satellite heat',
  nifc: 'Official perimeter',
  wind: 'Wind',
};

function evidenceStatus(state) {
  if (state === 'agree') return { chip: 'Supports', cls: 'ok' };
  if (state === 'disagree') return { chip: 'Conflicts', cls: 'bad' };
  if (state === 'error') return { chip: 'Error', cls: 'bad' };
  return { chip: 'No signal yet', cls: 'wait' };
}

function plainEvidenceDetail(source, detail, state) {
  const raw = String(detail || '').trim();
  if (source === 'callers' || source === 'caller_location') {
    if (/Bright Data landmark|cached San Diego landmarks|Caller GPS|region geocode/i.test(raw)) {
      return raw; // honest pin story — keep the source line intact
    }
    if (state === 'agree' || /landmark|caller/i.test(raw)) {
      return raw && !/^not checked/i.test(raw)
        ? `Someone called this in. ${raw.replace(/\.$/, '')}.`
        : 'Someone called this in.';
    }
    return 'No caller report tied to this pin yet.';
  }
  if (source === 'cameras') {
    if (/not triaged|stills/i.test(raw)) {
      return 'We opened the nearest wildfire cameras. A human (or triage) still needs to say if smoke is visible.';
    }
    if (state === 'agree') return raw || 'Camera stills show smoke near this pin.';
    if (/not checked/i.test(raw) || !raw) return 'Cameras not checked for this pin yet.';
    return raw;
  }
  if (source === 'posts') {
    if (/Bright Data/i.test(raw)) {
      return raw; // gray unverified public ears — never “confirmed”
    }
    if (/not checked|unknown|no public/i.test(raw) || !raw) {
      return 'No public social posts linked to this pin yet.';
    }
    return raw;
  }
  if (source === 'firms') {
    if (/key not set/i.test(raw)) return 'Satellite key missing — cannot check heat.';
    if (/no detection|lag/i.test(raw) || state === 'empty') {
      return 'No satellite heat near this pin yet (can lag by hours). That does not mean no fire.';
    }
    if (state === 'agree') return raw || 'Satellite heat detected near this pin.';
    return raw || 'Satellite not checked yet.';
  }
  if (source === 'nifc') {
    if (/not checked|none mapped|no perimeter|unknown/i.test(raw) || !raw) {
      return 'No official fire perimeter drawn here yet.';
    }
    return raw;
  }
  if (source === 'wind') {
    if (/not checked|unknown/i.test(raw) || !raw) return 'Wind not loaded for this pin yet.';
    return raw;
  }
  return raw || 'No data yet.';
}

function fmtClock(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return '--:--';
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
}

function fireIcon(status) {
  const cls = status === 'confirmed' || status === 'dispatched' ? 'confirmed' : 'possible';
  return L.divIcon({
    className: `pin-fire ${cls}`,
    html: '<i></i>',
    iconSize: [14, 14],
    iconAnchor: [7, 14],
  });
}

function signalIcon() {
  return L.divIcon({
    className: 'pin-signal',
    html: '<i></i>',
    iconSize: [11, 11],
    iconAnchor: [5, 5],
  });
}

function unitIcon(callsign) {
  return L.divIcon({
    className: 'pin-unit',
    html: `<span><i class="truck"></i>${callsign || 'Unit'}</span>`,
    iconSize: [90, 24],
    iconAnchor: [12, 12],
  });
}

function App() {
  const [state, setState] = useState({
    incidents: [], units: [], hazards: [], signals: [], calls: [], merges: [], rings: [], last_seq: 0,
  });
  const [settings, setSettings] = useState({ overflow_enabled: false, mode: 'mock' });
  const [selectedId, setSelectedId] = useState(null);
  const [callLines, setCallLines] = useState({});
  const [callMeta, setCallMeta] = useState({});
  const [cameras, setCameras] = useState([]);
  const [cameraStatus, setCameraStatus] = useState('idle'); // idle | loading | ready | error
  const [cameraReason, setCameraReason] = useState('');
  const [evidence, setEvidence] = useState([]);
  const [whyLine, setWhyLine] = useState('');
  const [notice, setNotice] = useState('');
  const [connection, setConnection] = useState('connecting');
  const [busy, setBusy] = useState(false);
  const [route, setRoute] = useState(null);
  const [proof, setProof] = useState({ sim: null, eval: null });
  const [handoff, setHandoff] = useState(null);
  const [callStartedAt, setCallStartedAt] = useState(null);
  const [tick, setTick] = useState(0);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [camByIncident, setCamByIncident] = useState({});
  const [callPop, setCallPop] = useState(null);
  const [stuckByIncident, setStuckByIncident] = useState({});
  const [newsPulse, setNewsPulse] = useState(0);
  const [climax, setClimax] = useState(null); // unit.dispatched / warning.sent (secondary beat)
  // Jobs reveal: exact line ElevenLabs speaks from Bright Data shelter cache.
  const [spokenPath, setSpokenPath] = useState(null);
  const [mapReady, setMapReady] = useState(false);
  const [seen, setSeen] = useState(() => {
    try { return JSON.parse(localStorage.getItem('agni.lastSeen') || '{}'); } catch { return {}; }
  });
  const mapRef = useRef(null);
  const mapNode = useRef(null);
  const layerRef = useRef(null);
  const routeLayerRef = useRef(null);
  const lastTranscriptAt = useRef({});
  const chimePlayed = useRef(new Set());
  const lastFlyKey = useRef('');
  const routeRef = useRef(null);

  const flyToPin = useCallback((lat, lon, key) => {
    const map = mapRef.current;
    const la = Number(lat);
    const lo = Number(lon);
    if (!map || !Number.isFinite(la) || !Number.isFinite(lo)) return false;
    const flyKey = key || `${la.toFixed(5)}:${lo.toFixed(5)}`;
    const already = lastFlyKey.current === flyKey;
    const zoom = typeof map.getZoom === 'function' ? map.getZoom() : 0;
    // Re-zoom if still on the calm wide view even when coords were seen earlier.
    if (already && zoom >= 14) return true;
    lastFlyKey.current = flyKey;
    try {
      map.stop();
    } catch { /* ignore */ }
    if (zoom < 13) {
      map.setView([la, lo], 15, { animate: true });
    } else {
      map.flyTo([la, lo], 15, { duration: 0.7, easeLinearity: 0.25 });
    }
    return true;
  }, []);

  const headers = useMemo(() => ({ ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}) }), []);
  const incidents = (state.incidents || []).filter(i => !i.merged_into && i.status !== 'rejected');
  // Never auto-grab the first noisy row — only follow a live call or an explicit click.
  const selected = incidents.find(item => item.id === selectedId) || null;
  const relatedMerge = (state.merges || []).find(
    item => item.kept_id === selected?.id || item.merged_id === selected?.id,
  );
  const selectedRing = (state.rings || []).find(item => item.incident_id === selected?.id);
  const callIsActive = (c) => {
    if (!c || (c.state !== 'live' && c.state !== 'human')) return false;
    if (c.ended_at) return false;
    // Smoke-test rows without a post-call webhook can stick as live forever.
    const started = c.started_at ? Date.parse(c.started_at) : NaN;
    if (!Number.isNaN(started) && Date.now() - started > 15 * 60 * 1000) return false;
    return true;
  };
  const liveCall = (state.calls || []).find(
    c => c.incident_id === selected?.id && callIsActive(c),
  );
  const selectedCall = liveCall || (state.calls || []).find(c => c.incident_id === selected?.id);
  const humanOnCall = Boolean(
    liveCall?.state === 'human'
    || (handoff?.incident_id && selected?.id && handoff.incident_id === selected.id),
  );
  const liveStartedMs = liveCall?.started_at
    ? Date.parse(liveCall.started_at)
    : (callStartedAt || null);
  const stuckState = evaluateCallStuck({
    incidentId: selected?.id,
    liveCall,
    humanOnCall,
    stuckByIncident,
    liveStartedMs,
    callStartedAt,
    lastTranscriptAt,
  });
  const isStuck = stuckState.stuck;
  const liveCount = (state.calls || []).filter(callIsActive).length;
  const isReplay = settings.demo_replay === true || settings.mode === 'mock';
  const firmsKeySet = settings.firms_key_set === true;
  const unitsFree = (state.units || []).filter(u => u.status === 'available' || !u.status).length;
  const unitsTotal = (state.units || []).length || 0;
  const residentsWarned = proof.sim?.residents_warned ?? proof.sim?.warned ?? null;
  const dispatchClock = liveStartedMs ? (Date.now() - liveStartedMs) / 1000 : null;
  void selectedCall;

  const refresh = useCallback(async () => {
    const [stateRes, settingsRes, proofRes] = await Promise.all([
      fetch(`${API}/api/state`, { headers }),
      fetch(`${API}/api/settings`, { headers }),
      fetch(`${API}/api/proof`, { headers }),
    ]);
    if (!stateRes.ok || !settingsRes.ok) throw new Error('Console access failed. Check API and operator token.');
    const [nextState, nextSettings, nextProof] = await Promise.all([
      stateRes.json(),
      settingsRes.json(),
      proofRes.ok ? proofRes.json() : { sim: null, eval: null },
    ]);
    setState(nextState);
    setSettings(nextSettings);
    setProof(nextProof);
    // Hydrate transcript lines from /api/state so a late join / missed SSE still shows speech.
    setCallLines(current => {
      const next = { ...current };
      for (const call of nextState.calls || []) {
        const iid = call.incident_id;
        const serverLines = Array.isArray(call.transcript) ? call.transcript : [];
        if (!iid || !serverLines.length) continue;
        const prev = next[iid] || [];
        if (serverLines.length >= prev.length) {
          next[iid] = serverLines.slice(-20);
        }
      }
      return next;
    });
    setCallMeta(current => {
      const next = { ...current };
      for (const call of nextState.calls || []) {
        const iid = call.incident_id;
        if (!iid) continue;
        // Prefer spoken landmark_text from the live call row over stale meta.
        const spoken = (call.landmark_text || '').trim();
        next[iid] = {
          ...(next[iid] || {}),
          id: call.id,
          language: call.language || next[iid]?.language,
          ...(spoken ? { landmark_text: spoken } : {}),
          phone_last4: call.phone_last4 || next[iid]?.phone_last4,
        };
      }
      return next;
    });
    setSelectedId(current => {
      const live = (nextState.calls || []).find(c => c.state === 'live' || c.state === 'human');
      if (live?.incident_id) return live.incident_id;
      if (current && (nextState.incidents || []).some(i => i.id === current && !i.merged_into)) {
        return current;
      }
      return null;
    });
  }, [headers]);

  const clearSlate = useCallback(async () => {
    setBusy(true);
    try {
      const res = await fetch(`${API}/api/ops/reset`, { method: 'POST', headers });
      if (!res.ok) throw new Error(`Reset failed (${res.status})`);
      localStorage.setItem('agni.eventSeq', '0');
      localStorage.removeItem('agni.lastSeen');
      setSeen({});
      setSelectedId(null);
      setCallLines({});
      setCallMeta({});
      setCameras([]);
      setCameraStatus('idle');
      setCameraReason('');
      setEvidence([]);
      setWhyLine('');
      setRoute(null);
      setHandoff(null);
      setCallPop(null);
      setStuckByIncident({});
      setCamByIncident({});
      setCallStartedAt(null);
      setEvidenceOpen(false);
      setClimax(null);
      setSpokenPath(null);
      lastFlyKey.current = '';
      chimePlayed.current = new Set();
      lastTranscriptAt.current = {};
      await refresh();
      setNotice('Clean slate — dial AGNI for the next call');
    } catch (error) {
      setNotice(error.message || 'Reset failed');
    } finally {
      setBusy(false);
    }
  }, [headers, refresh]);

  useEffect(() => {
    refresh().then(() => setConnection('live')).catch(error => {
      setConnection('offline');
      setNotice(error.message);
    });
    const last = Number(localStorage.getItem('agni.eventSeq') || 0);
    const feed = new EventSource(
      `${API}/api/events?since=${last}${TOKEN ? `&token=${encodeURIComponent(TOKEN)}` : ''}`,
    );
    feed.onopen = () => { setConnection('live'); setNotice(''); };
    feed.onerror = () => { setConnection('reconnecting'); setNotice('Reconnecting to event stream…'); };
    const onEvent = event => {
      const payload = JSON.parse(event.data);
      const seq = Number(payload.seq || event.lastEventId || 0);
      const seenSeq = Number(localStorage.getItem('agni.eventSeq') || 0);
      if (seq && seq <= seenSeq) return;
      if (seq) localStorage.setItem('agni.eventSeq', String(seq));

      if (payload.type === 'call.started') {
        const iid = payload.incident_id;
        const startedMs = Date.now();
        setCallMeta(current => ({
          ...current,
          [iid]: {
            ...(current[iid] || {}),
            id: payload.data.call_id,
            direction: payload.data.direction,
            language: payload.data.language,
            landmark_text: payload.data.landmark_text,
            phone_last4: payload.data.phone_last4,
          },
        }));
        setCallStartedAt(startedMs);
        if (iid) {
          // Do NOT seed lastTranscriptAt here — silence-stuck only after a real line arrives.
          setSelectedId(iid);
        }
        setCallPop({
          id: payload.data.call_id || `${iid}-${startedMs}`,
          incident_id: iid,
          call_id: payload.data.call_id,
          language: payload.data.language || 'en',
          landmark_text: payload.data.landmark_text || '',
          phone_last4: payload.data.phone_last4 || '',
          startedAt: startedMs,
        });
        const chimeKey = payload.data.call_id || iid;
        if (chimeKey && !chimePlayed.current.has(chimeKey)) {
          chimePlayed.current.add(chimeKey);
          playCallChime();
        }
        flyToPin(
          payload.data?.lat,
          payload.data?.lon,
          `${payload.data.call_id || iid}:${payload.data?.lat}:${payload.data?.lon}`,
        );
        // Pull /api/state so the live call row appears even if SSE raced ahead of DB reads.
        refresh().catch(() => {});
      }
      if (payload.type === 'incident.created' || payload.type === 'estimate.updated') {
        flyToPin(
          payload.data?.lat,
          payload.data?.lon,
          `${payload.incident_id || 'inc'}:${payload.data?.lat}:${payload.data?.lon}`,
        );
      }
      if (payload.type === 'evidence.updated') {
        const iid = payload.incident_id;
        if (iid && payload.data?.landmark_text) {
          setCallMeta(current => ({
            ...current,
            [iid]: {
              ...(current[iid] || {}),
              // Prefer spoken landmark words over matched cache name.
              landmark_text: payload.data.landmark_text,
            },
          }));
        }
        if (iid && (payload.data?.location_src || payload.data?.first_mention || payload.data?.landmark_name
            || payload.data?.lat != null)) {
          setState(current => ({
            ...current,
            incidents: (current.incidents || []).map(inc => {
              if (inc.id !== iid) return inc;
              const next = { ...inc };
              if (payload.data.location_src) next.location_src = payload.data.location_src;
              if (payload.data.lat != null) next.lat = payload.data.lat;
              if (payload.data.lon != null) next.lon = payload.data.lon;
              if (payload.data.why_line) next.why_line = payload.data.why_line;
              if (payload.data.first_mention) next.first_mention = payload.data.first_mention;
              if (payload.data.location_src === 'landmark' || /Bright Data landmark|cached San Diego/i.test(payload.data.detail || '')) {
                next.landmark_chip = 'Pin from cached San Diego landmarks';
              } else if (payload.data.location_src === 'geocode' || /region geocode/i.test(payload.data.detail || '')) {
                next.landmark_chip = 'Pin from region geocode (never invented)';
              } else if (payload.data.location_src === 'caller' || /caller GPS/i.test(payload.data.detail || '')) {
                next.landmark_chip = 'Caller GPS';
              }
              return next;
            }),
          }));
        }
      }
      if (payload.type === 'evidence.updated' && payload.data?.lat != null && payload.data?.lon != null) {
        flyToPin(
          payload.data.lat,
          payload.data.lon,
          `${payload.incident_id || 'ev'}:${payload.data.lat}:${payload.data.lon}`,
        );
      }
      if (payload.type === 'call.transcript') {
        const iid = payload.incident_id;
        lastTranscriptAt.current[iid] = Date.now();
        setStuckByIncident(current => {
          if (!iid || !current[iid]) return current;
          if (current[iid].reason === 'silence') {
            const next = { ...current };
            delete next[iid];
            return next;
          }
          return current;
        });
        setCallLines(current => {
          const previous = current[iid] || [];
          return { ...current, [iid]: [...previous, payload.data].slice(-20) };
        });
        if (payload.data?.language && iid) {
          setCallMeta(current => ({
            ...current,
            [iid]: { ...(current[iid] || {}), language: payload.data.language },
          }));
        }
        const speaker = String(payload.data?.speaker || '').toLowerCase();
        if (iid && speaker && HUMAN_ASK_RE.test(payload.data?.text || '')
            && (speaker === 'caller' || speaker === 'user')) {
          setStuckByIncident(current => ({
            ...current,
            [iid]: { reason: 'caller_asked_human', at: Date.now() },
          }));
        }
      }
      if (payload.type === 'call.needs_human') {
        const iid = payload.incident_id;
        if (iid) {
          setStuckByIncident(current => ({
            ...current,
            [iid]: { reason: payload.data?.reason || 'needs_human', at: Date.now() },
          }));
          setSelectedId(iid);
          setNotice(payload.data?.say || 'AGNI is stuck — press J to take over');
        }
      }
      if (payload.type === 'signal.new') {
        setNewsPulse(n => n + 1);
      }
      if (payload.type === 'ops.reset') {
        localStorage.setItem('agni.eventSeq', String(seq || 0));
        setSelectedId(null);
        setCallLines({});
        setCallMeta({});
        setCameras([]);
        setCameraStatus('idle');
        setCameraReason('');
        setEvidence([]);
        setWhyLine('');
        setRoute(null);
        setHandoff(null);
        setCallPop(null);
        setStuckByIncident({});
        setCamByIncident({});
        setCallStartedAt(null);
        lastFlyKey.current = '';
        setClimax(null);
        setSpokenPath(null);
        setNotice('Clean slate — ready for the next call');
        refresh().catch(() => {});
      }
      if (payload.type === 'guidance.ready' && payload.incident_id) {
        const shelter = payload.data?.shelter || {};
        const refused = (payload.data?.refused || [])[0] || null;
        setSelectedId(payload.incident_id);
        setSpokenPath({
          incident_id: payload.incident_id,
          say: payload.data?.say || '',
          shelter_name: shelter.name || null,
          shelter_lat: shelter.lat,
          shelter_lon: shelter.lon,
          room: shelter.room,
          capacity_label: shelter.capacity_label || payload.data?.label || 'Bright Data · shelter capacity',
          refused_name: refused?.name || null,
          refused_why: refused?.reason || refused?.why || null,
          label: payload.data?.label || 'Bright Data · safest open shelter',
          at: Date.now(),
        });
        if (shelter.lat != null && shelter.lon != null) {
          flyToPin(shelter.lat, shelter.lon, `shelter:${payload.incident_id}`);
        }
        setNotice('Caller hears the safe path · Bright Data shelter');
      }
      if (payload.type === 'unit.dispatched' && payload.incident_id) {
        const iid = payload.incident_id;
        const rt = routeRef.current || {};
        const fromRoute = (rt.units || []).find(
          u => (u.unit_id || u.id) === payload.data?.unit_id,
        ) || (rt.units || [])[0];
        const shelter = rt.shelter || payload.data?.shelter || null;
        const refused = (rt.refused || [])[0] || null;
        setSelectedId(iid);
        setClimax(current => ({
          incident_id: iid,
          callsign: payload.data?.callsign || current?.callsign || payload.data?.unit_id || 'Unit',
          unit_id: payload.data?.unit_id || current?.unit_id,
          eta_s: payload.data?.eta_s ?? current?.eta_s ?? fromRoute?.eta_s ?? null,
          shelter_name: shelter?.name || current?.shelter_name || null,
          shelter_why: shelter
            ? (shelter.capacity_label || shelter.status || 'open · away from downwind')
            : null,
          refused_name: refused?.name || refused?.why || current?.refused_name || null,
          recipients: current?.recipients ?? null,
          warned: Boolean(current?.warned),
          at: Date.now(),
          source: 'unit.dispatched',
        }));
        setNotice(
          `${payload.data?.callsign || payload.data?.unit_id || 'Unit'} en route`,
        );
      }
      if (payload.type === 'warning.sent' && payload.incident_id) {
        const n = payload.data?.recipients;
        setClimax(current => {
          if (current?.incident_id && current.incident_id !== payload.incident_id) return current;
          return {
            ...(current || {}),
            incident_id: payload.incident_id,
            recipients: typeof n === 'number' ? n : (current?.recipients ?? null),
            warned: true,
            at: Date.now(),
            source: current?.source || 'warning.sent',
          };
        });
        setNotice(
          typeof n === 'number'
            ? `Warning calls queued to ${n} opt-in home${n === 1 ? '' : 's'}`
            : 'Warning calls queued to opt-in homes',
        );
      }
      if (payload.type === 'handoff.started') {
        setHandoff({
          incident_id: payload.incident_id,
          summary: payload.data.summary,
          call_id: payload.data.call_id,
        });
        setStuckByIncident(current => {
          if (!payload.incident_id) return current;
          const next = { ...current };
          delete next[payload.incident_id];
          return next;
        });
        setCallPop(null);
      }
      if (payload.type === 'handoff.ended') setHandoff(null);
      if (payload.type === 'route.ready') setRoute(payload.data);
      if (payload.type === 'camera.link' && payload.incident_id) {
        setCamByIncident(current => ({
          ...current,
          [payload.incident_id]: {
            code: payload.data.code,
            url: payload.data.url,
            sms_ok: payload.data.sms_ok,
          },
        }));
        setSelectedId(payload.incident_id);
        setNotice(
          payload.data.sms_ok
            ? 'Text sent to caller — optional camera link'
            : 'Optional camera link ready — copy only if you want a photo',
        );
      }
      // cameras.selected intentionally omits image blobs — keep wall on /api/cameras fetch
      refresh().catch(() => {});
    };
    EVENT_TYPES.forEach(type => feed.addEventListener(type, onEvent));
    return () => feed.close();
  }, [refresh, flyToPin]);

  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    routeRef.current = route;
  }, [route]);

  // Client-side silence stuck: only after we have heard the caller, then they go quiet.
  // Never flag "stuck" during normal intake before any transcript arrives.
  useEffect(() => {
    if (!liveCall || humanOnCall || !selected?.id) return;
    const iid = selected.id;
    if (stuckByIncident[iid] || liveCall.needs_human) return;
    const lastLine = lastTranscriptAt.current[iid];
    if (!lastLine) return;
    const silentS = (Date.now() - lastLine) / 1000;
    if (silentS >= STUCK_SILENCE_S) {
      setStuckByIncident(current => ({
        ...current,
        [iid]: { reason: 'silence', at: Date.now() },
      }));
    }
  }, [tick, liveCall, humanOnCall, selected?.id, stuckByIncident]);

  useEffect(() => {
    // Mode banner replaces the call pop — auto-dismiss so it does not stack.
    if (!callPop) return undefined;
    const t = setTimeout(() => setCallPop(null), 2500);
    return () => clearTimeout(t);
  }, [callPop?.id]);

  useEffect(() => {
    if (!mapNode.current || mapRef.current) return;
    const map = L.map(mapNode.current, {
      zoomControl: false,
      attributionControl: true,
      preferCanvas: true,
    }).setView([32.92, -117.23], 12);
    // CARTO dark basemap (HTTPS). Spec says dark_matter; that path 404s on cartocdn —
    // dark_all is the working dark style (same family). Esri Canvas paints
    // "Map data not yet available" watermarks across the viewport — do not use it.
    // CartoCDN now stamps "API KEY REQUIRED" — use Esri dark gray (no key) for the demo.
    L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
      {
        attribution: 'Tiles &copy; Esri',
        maxZoom: 16,
        className: 'agni-basemap',
      },
    ).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    routeLayerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    setMapReady(true);
    const bump = () => {
      try { map.invalidateSize({ pan: false }); } catch { /* ignore */ }
    };
    requestAnimationFrame(bump);
    const t1 = setTimeout(bump, 50);
    const t2 = setTimeout(bump, 250);
    const t3 = setTimeout(bump, 800);
    window.addEventListener('resize', bump);
    let ro;
    if (typeof ResizeObserver !== 'undefined' && mapNode.current) {
      ro = new ResizeObserver(bump);
      ro.observe(mapNode.current);
    }
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      window.removeEventListener('resize', bump);
      if (ro) ro.disconnect();
      map.remove();
      mapRef.current = null;
      setMapReady(false);
    };
  }, []);

  // Neighborhood zoom when selected/live incident has a pin (incl. late landmark geocode).
  useEffect(() => {
    if (!mapReady) return;
    const live = (state.calls || []).find(callIsActive);
    const focus = selected
      || (live && (state.incidents || []).find(i => i.id === live.incident_id))
      || null;
    const lat = focus?.lat;
    const lon = focus?.lon;
    if (lat == null || lon == null) return;
    flyToPin(lat, lon, `${focus.id}:${Number(lat).toFixed(5)}:${Number(lon).toFixed(5)}`);
  }, [mapReady, state.calls, state.incidents, selected?.id, selected?.lat, selected?.lon, flyToPin]);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();

    (state.signals || []).forEach(sig => {
      if (sig.lat == null || sig.lon == null) return;
      L.marker([sig.lat, sig.lon], { icon: signalIcon(), opacity: 0.9 })
        .bindTooltip(`Unverified · ${sig.source || 'signal'}`, { direction: 'top', opacity: 0.9 })
        .addTo(layer);
    });

    (state.units || []).forEach(unit => {
      if (unit.lat == null || unit.lon == null) return;
      L.marker([unit.lat, unit.lon], { icon: unitIcon(unit.callsign) }).addTo(layer);
    });

    incidents.forEach(item => {
      if (item.lat == null || item.lon == null) return;
      const confirmed = item.status === 'confirmed' || item.status === 'dispatched';
      const marker = L.marker([item.lat, item.lon], { icon: fireIcon(item.status) })
        .bindTooltip(item.title || item.why_line || item.id, { direction: 'top' })
        .on('click', () => setSelectedId(item.id))
        .addTo(layer);
      if (confirmed || item.status === 'possible') {
        L.circle([item.lat, item.lon], {
          radius: confirmed ? 420 : 280,
          color: confirmed ? '#ff3b30' : '#9aa3ad',
          weight: 1,
          fillColor: confirmed ? '#ff3b30' : '#9aa3ad',
          fillOpacity: confirmed ? 0.12 : 0.06,
          opacity: 0.55,
        }).addTo(layer);
      }
      void marker;
    });

    if (selectedRing?.geometry || selectedRing?.geom || selectedRing?.geojson) {
      const geom = selectedRing.geometry || selectedRing.geom || selectedRing.geojson;
      try {
        L.geoJSON(geom, {
          style: {
            color: '#f0a500',
            weight: 2,
            fillColor: '#f0a500',
            fillOpacity: 0.1,
            dashArray: '5 6',
          },
        }).bindTooltip(`${selectedRing.minutes || 30}-min estimate`).addTo(layer);
      } catch { /* ignore */ }
    }
    // Zoom is owned by flyToPin — never panTo here (it cancels neighborhood zoom).
  }, [state.signals, state.units, incidents, selected?.id, selectedRing]);

  useEffect(() => {
    const layer = routeLayerRef.current;
    if (!layer) return;
    layer.clearLayers();
    const geo = route?.geojson || route?.units?.[0]?.geojson || route?.route_geojson;
    if (geo) {
      try {
        L.geoJSON(geo, {
          style: { color: '#ffffff', weight: 4, opacity: 0.9 },
        }).addTo(layer);
      } catch { /* ignore */ }
    }
    (state.hazards || []).forEach(h => {
      const geom = h.geom || h.geometry || h.geojson;
      if (!geom) return;
      try {
        L.geoJSON(typeof geom === 'string' ? JSON.parse(geom) : geom, {
          style: { color: '#8a939c', weight: 3, dashArray: '6 6', opacity: 0.8 },
        }).bindTooltip(h.title || 'Closure').addTo(layer);
      } catch { /* ignore */ }
    });
  }, [route, state.hazards]);

  useEffect(() => {
    if (selected?.lat == null || selected?.lon == null
        || !Number.isFinite(Number(selected.lat)) || !Number.isFinite(Number(selected.lon))) {
      setCameras([]);
      setCameraStatus('idle');
      setCameraReason('');
      setRoute(null);
      return undefined;
    }
    const query = new URLSearchParams({
      lat: String(selected.lat),
      lon: String(selected.lon),
      n: '3',
    });
    let cancelled = false;
    const objectUrls = [];
    setCameraStatus('loading');
    setCameraReason('');
    setCameras([]);
    (async () => {
      try {
        const r = await fetch(`${API}/api/cameras?${query}`, { headers });
        if (!r.ok) {
          if (!cancelled) {
            setCameras([]);
            setCameraStatus('error');
            setCameraReason(r.status === 401 ? 'Operator token required' : `Cameras HTTP ${r.status}`);
          }
          return;
        }
        const result = await r.json();
        if (cancelled) return;
        const source = result.frame_source || (isReplay ? 'replay' : 'live');
        const list = (result.cameras || []).slice(0, 3);
        if (!list.length) {
          setCameras([]);
          setCameraStatus('error');
          setCameraReason('No ALERTCalifornia cameras near this pin');
          return;
        }
        const cams = await Promise.all(list.map(async (cam) => {
          const framePath = cam.frame
            || `/api/cameras/${encodeURIComponent(cam.id)}/frame?lat=${selected.lat}&lon=${selected.lon}`;
          let image = null;
          let reason = null;
          try {
            // Fetch with operator headers — <img src> cannot send Bearer tokens.
            const fr = await fetch(`${API}${framePath}`, { headers });
            if (fr.ok) {
              const blob = await fr.blob();
              if (blob.size > 800) {
                image = URL.createObjectURL(blob);
                objectUrls.push(image);
              } else {
                reason = 'Frame too small / empty';
              }
            } else {
              reason = fr.status === 503 ? 'Frames offline in mock' : `Frame HTTP ${fr.status}`;
            }
          } catch {
            reason = 'Frame fetch failed';
          }
          if (!image && cam.image) {
            image = cam.image;
            reason = null;
          }
          return {
            ...cam,
            frame: framePath,
            image,
            reason: image ? null : (reason || 'No frame'),
            frame_source: cam.frame_source || source,
          };
        }));
        if (!cancelled) {
          setCameras(cams);
          setCameraStatus('ready');
          setCameraReason(cams.every(c => !c.image) ? 'Stills unavailable — feed may be down' : '');
        }
      } catch (err) {
        if (!cancelled) {
          setCameras([]);
          setCameraStatus('error');
          setCameraReason(err?.message || 'Camera request failed');
        }
      }
    })();
    return () => {
      cancelled = true;
      objectUrls.forEach(u => URL.revokeObjectURL(u));
    };
  }, [selected?.id, selected?.lat, selected?.lon, headers, isReplay]);

  useEffect(() => {
    if (!selected?.id) {
      setEvidence([]);
      setWhyLine('');
      return;
    }
    fetch(`${API}/api/incidents/${selected.id}/evidence`, { headers })
      .then(r => (r.ok ? r.json() : { rows: [], why_line: selected.why_line }))
      .then(result => {
        setEvidence(result.rows || []);
        if (result.first_mention || result.landmark_chip) {
          setState(current => ({
            ...current,
            incidents: (current.incidents || []).map(inc => {
              if (inc.id !== selected.id) return inc;
              return {
                ...inc,
                ...(result.first_mention ? { first_mention: result.first_mention } : {}),
                ...(result.landmark_chip ? { landmark_chip: result.landmark_chip } : {}),
              };
            }),
          }));
        }
        const fromEvidence = result.why_line || '';
        const fromIncident = selected.why_line || '';
        // Prefer the longer human-readable line (evidence helper can truncate mid-word)
        setWhyLine(
          fromIncident.length >= fromEvidence.length ? fromIncident : fromEvidence,
        );
      })
      .catch(() => {
        setEvidence([]);
        setWhyLine(selected.why_line || '');
      });
  }, [selected?.id, selected?.why_line, headers, state.last_seq]);

  const markSeen = id => {
    if (!id) return;
    const next = { ...seen, [id]: state.last_seq || 0 };
    setSeen(next);
    localStorage.setItem('agni.lastSeen', JSON.stringify(next));
  };

  useEffect(() => {
    if (selectedId) markSeen(selectedId);
  }, [selectedId, state.last_seq]);

  const newBadge = item => {
    if (!item || selected?.id === item.id) return null;
    const baseline = seen[item.id] || 0;
    const delta = Math.max(0, (state.last_seq || 0) - baseline);
    return delta > 0 ? `NEW ${delta > 9 ? '' : delta}`.trim() : null;
  };

  const request = async (path, body, extra = {}) => {
    const response = await fetch(`${API}${path}`, {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json', ...extra },
      body: body ? JSON.stringify(body) : '{}',
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.detail || `Request failed (${response.status})`);
    return result;
  };

  const confirmFire = async () => {
    if (!selected || busy) return;
    if (selected.status === 'confirmed' || selected.status === 'dispatched') return;
    setBusy(true);
    try {
      await request(`/api/incidents/${selected.id}/confirm`, {
        actor: 'dispatcher',
        note: 'Confirmed by dispatcher',
      });
      setNotice('Fire confirmed — next: approve a unit');
      const options = await fetch(`${API}/api/incidents/${selected.id}/route`, { headers })
        .then(r => (r.ok ? r.json() : null))
        .catch(() => null);
      if (options) setRoute(options);
      await refresh();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  };

  const rejectFire = async () => {
    if (!selected || busy) return;
    setBusy(true);
    try {
      await request(`/api/incidents/${selected.id}/reject`, {
        actor: 'dispatcher',
        note: 'Not a fire',
      });
      setNotice('Marked not a fire');
      setSelectedId(null);
      await refresh();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  };

  const checkCamerasWithGemini = async () => {
    if (!selected?.lat || busy) return;
    setBusy(true);
    setNotice('Sending nearest camera stills to Gemini…');
    try {
      const result = await request(`/api/incidents/${selected.id}/triage-cameras`, null);
      const hits = result.smoke_hits ?? 0;
      setNotice(
        hits > 0
          ? `Gemini: ${hits} camera(s) may show smoke — you still Confirm`
          : `Gemini: ${result.detail || 'no clear smoke'} — you still Confirm`,
      );
      setEvidenceOpen(true);
      await refresh();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  };

  const loadRoute = async () => {
    if (!selected) return null;
    const options = await fetch(`${API}/api/incidents/${selected.id}/route`, { headers }).then(r => r.json());
    setRoute(options);
    return options;
  };

  const approveDispatch = async () => {
    if (!selected || selected.status !== 'confirmed' || busy) return;
    setBusy(true);
    try {
      const options = route?.units?.length ? route : await loadRoute();
      const unit = options?.units?.[0];
      if (!unit) throw new Error('No available unit');
      const unitId = unit.unit_id || unit.id;
      const result = await request(
        `/api/incidents/${selected.id}/dispatch`,
        { unit_id: unitId, approved_by: 'dispatcher' },
        { 'Idempotency-Key': crypto.randomUUID() },
      );
      const shelter = options?.shelter || route?.shelter || null;
      const refused = (options?.refused || route?.refused || [])[0] || null;
      // Seed climax immediately from the real dispatch response; SSE may also refresh it.
      setClimax({
        incident_id: selected.id,
        callsign: result.callsign || unit.callsign || unitId,
        unit_id: result.unit_id || unitId,
        eta_s: result.eta_s ?? unit.eta_s ?? null,
        shelter_name: shelter?.name || null,
        shelter_why: shelter
          ? (shelter.capacity_label || shelter.status || 'open · away from downwind')
          : null,
        refused_name: refused?.name || refused?.why || null,
        recipients: null,
        warned: false,
        at: Date.now(),
        source: 'unit.dispatched',
      });
      setNotice(`Dispatched · caller guided to safety · ${result.callsign || unit.callsign || unitId}`);
      await refresh();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  };

  const createRing = async () => {
    if (!selected || busy) return;
    setBusy(true);
    try {
      await request(`/api/incidents/${selected.id}/ring`, { minutes: 30, wind_to_deg: 135 });
      setNotice('30-min estimate ring ready');
      await refresh();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  };

  const sendWarning = async () => {
    if (!selected || busy) return;
    setBusy(true);
    try {
      const result = await request(
        `/api/warnings/${selected.id}`,
        { languages: ['en', 'es'], message_key: 'wildfire_targeted_warning' },
        { 'Idempotency-Key': crypto.randomUUID() },
      );
      setNotice(`${result.recipients ?? 0} warning calls queued`);
      await refresh();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  };

  const toggleOverflow = async () => {
    setBusy(true);
    try {
      const response = await fetch(`${API}/api/settings`, {
        method: 'PUT',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ overflow_enabled: !settings.overflow_enabled }),
      });
      if (!response.ok) throw new Error('Could not change overflow');
      setSettings(await response.json());
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  };

  const mergeAction = async action => {
    if (!relatedMerge || busy) return;
    setBusy(true);
    try {
      await request(`/api/merges/${relatedMerge.id}/${action}`, {});
      setNotice(
        action === 'accept' ? 'Merge accepted'
          : action === 'undo' ? 'Merge undone'
            : 'Kept apart',
      );
      await refresh();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  };

  const jumpIn = async (opts = {}) => {
    const callId = opts.callId || liveCall?.id || callPop?.call_id;
    const incidentId = opts.incidentId || selected?.id || callPop?.incident_id;
    if ((!callId && !incidentId) || busy) {
      setNotice('No live call to jump into');
      return;
    }
    if (settings.dispatcher_phone_set === false) {
      setNotice('Set DISPATCHER_PHONE_NUMBER in .env first — JUMP IN cannot ring a phone yet');
      return;
    }
    setBusy(true);
    try {
      const path = callId
        ? `/api/calls/${callId}/jump-in`
        : `/api/incidents/${incidentId}/jump-in`;
      const result = await request(path, { actor: 'dispatcher' });
      const iid = result.incident_id || incidentId;
      setHandoff({
        incident_id: iid,
        summary: result.summary,
        call_id: result.call_id || callId,
      });
      if (iid) setSelectedId(iid);
      setCallPop(null);
      setNotice("You're live with the caller");
      await refresh();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  };

  const handBack = async () => {
    if (!selected || busy) return;
    setBusy(true);
    try {
      const callId = handoff?.call_id || liveCall?.id;
      const path = callId
        ? `/api/calls/${callId}/hand-back`
        : `/api/incidents/${selected.id}/hand-back`;
      await request(path, { actor: 'dispatcher' });
      setHandoff(null);
      setNotice('Handed back · AGNI resumes via callback');
      await refresh();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  };

  const signClose = async () => {
    if (!selected || busy) return;
    setBusy(true);
    try {
      await request(`/api/incidents/${selected.id}/report/sign`, { actor: 'dispatcher', edits: '' });
      setNotice('After-action signed · incident closed');
      await refresh();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
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
      if (key === 'r') createRing();
      if (key === 'm') mergeAction('accept');
      if (key === 'n') mergeAction('keep-apart');
      if (key === 'u' && relatedMerge?.state === 'accepted') mergeAction('undo');
      if (key === 's') signClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const callerLines = callLines[selected?.id] || [];
  const lang = (
    callMeta[selected?.id]?.language
    || liveCall?.language
    || 'en'
  ).toUpperCase();
  const callersCount = (state.calls || []).filter(c => c.incident_id === selected?.id).length
    || (selected ? 1 : 0);
  // Live clock / silence detector keep ticking while a call is up.
  void tick;
  void connection;
  void liveCount;
  void lang;

  const evidenceRows = (() => {
    const bySource = {};
    for (const row of evidence) bySource[row.source] = row;
    if (bySource.caller_location && !bySource.callers) bySource.callers = bySource.caller_location;
    const framed = cameras.filter(c => c.image && !c.empty).length;
    const order = ['callers', 'cameras', 'posts', 'firms', 'nifc', 'wind'];
    return order.map(source => {
      const row = bySource[source];
      let detail = row?.detail;
      let state = row?.state || (source === 'firms' && !firmsKeySet ? 'unknown' : 'empty');
      if (source === 'firms' && !detail) {
        detail = firmsKeySet
          ? 'No detection yet; satellite data can lag hours'
          : 'Key not set · not checked';
      }
      if (source === 'cameras' && framed > 0
          && (!row || row.state === 'empty' || /not checked|not checked yet/i.test(String(row.detail || '')))) {
        detail = `${framed} nearest ALERTCalifornia stills · not triaged yet`;
        state = 'empty';
      }
      const status = evidenceStatus(state);
      return {
        source,
        label: EVIDENCE_LABEL[source],
        state,
        statusChip: status.chip,
        statusCls: status.cls,
        detail: plainEvidenceDetail(source, detail, state),
      };
    });
  })();

  const cameraItems = (() => {
    if (cameraStatus === 'ready' && cameras.length) {
      const tiles = cameras.slice(0, 3);
      while (tiles.length < 3) {
        tiles.push({
          id: `pad-${tiles.length}`,
          name: 'Camera',
          reason: cameraReason || 'No camera',
        });
      }
      return tiles;
    }
    if (cameraStatus === 'loading') {
      return [0, 1, 2].map(i => ({ id: `load-${i}`, name: 'Camera', loading: true }));
    }
    if (cameraStatus === 'error') {
      return [0, 1, 2].map(i => ({
        id: `err-${i}`,
        name: 'Camera',
        reason: cameraReason || 'Unavailable',
      }));
    }
    // idle / no pin — one calm tile message, not three fake loaders
    return [];
  })();

  const routeUnit = route?.units?.[0];
  const routeLabel = routeUnit
    ? `${routeUnit.callsign || routeUnit.unit_id || 'Unit'} · ETA ${
      routeUnit.eta_s != null ? `${Math.round(routeUnit.eta_s / 60)} min` : '—'
    }${routeUnit.via ? ` · via ${routeUnit.via}` : ''}`
    : null;
  const avoids = route?.avoids || routeUnit?.avoids || [];
  const measuredHeadline = proof.sim
    ? `${proof.sim.calls ?? proof.sim.n ?? '—'} calls → ${proof.sim.incidents ?? proof.sim.visible_incidents ?? '—'} fires`
    : '— not measured yet';

  const newsItems = useMemo(() => {
    // One Local news box: show latest crowd headlines even if the cache is older than
    // an hour (Bright Data never runs during a live call).
    const rows = (state.signals || [])
      .filter(s => s && (s.text || s.place_text))
      .map(s => {
        const scraped = s.scraped_at || s.posted_at || s.ts;
        const scrapedMs = scraped ? Date.parse(scraped) : NaN;
        return { ...s, scraped, scrapedMs: Number.isNaN(scrapedMs) ? 0 : scrapedMs };
      })
      .sort((a, b) => b.scrapedMs - a.scrapedMs)
      .slice(0, 4);
    void newsPulse;
    return rows;
  }, [state.signals, newsPulse]);

  const newsStale = (() => {
    if (!newsItems.length) return false;
    const newest = Math.max(...newsItems.map(s => s.scrapedMs || 0));
    if (!newest) return true;
    return (Date.now() - newest) > 15 * 60 * 1000;
  })();

  const anyLiveCall = (state.calls || []).find(callIsActive);
  const focusIncident = selected
    || incidents.find(i => i.id === anyLiveCall?.incident_id)
    || null;
  const focusLive = focusIncident
    ? (state.calls || []).find(c => c.incident_id === focusIncident.id && callIsActive(c))
    : anyLiveCall;
  const focusHuman = Boolean(
    focusLive?.state === 'human'
    || (handoff?.incident_id && focusIncident?.id && handoff.incident_id === focusIncident.id),
  );
  const focusStuckState = evaluateCallStuck({
    incidentId: focusIncident?.id,
    liveCall: focusLive,
    humanOnCall: focusHuman,
    stuckByIncident,
    liveStartedMs: focusLive?.started_at ? Date.parse(focusLive.started_at) : callStartedAt,
    callStartedAt,
    lastTranscriptAt,
  });
  const focusStuck = focusStuckState.stuck;
  const landmarkNow = (
    (focusIncident && callMeta[focusIncident.id]?.landmark_text)
    || focusLive?.landmark_text
    || focusIncident?.why_line
    || ''
  );

  const climaxForFocus = climax && focusIncident && climax.incident_id === focusIncident.id
    ? climax
    : (climax && !focusIncident ? climax : null);
  const pathForFocus = spokenPath && focusIncident && spokenPath.incident_id === focusIncident.id
    ? spokenPath
    : (spokenPath && !focusIncident ? spokenPath : null);
  const climaxEtaLabel = climaxForFocus?.eta_s != null
    ? `ETA ~${Math.max(1, Math.round(Number(climaxForFocus.eta_s) / 60))} min`
    : null;

  // Single mode model — answers "who is handling?" for anyone glancing at the screen.
  // Advances with real call / confirm / dispatch state — never a fake slideshow.
  const mode = (() => {
    if (focusHuman && focusLive) {
      return {
        id: 'human',
        who: 'You',
        tone: 'human',
        title: "You're on the call",
        body: 'Talk to the caller. Hand back (J) when AGNI should resume.',
        action: 'handback',
      };
    }
    if (focusStuck && focusLive) {
      return {
        id: 'stuck',
        who: 'Stuck → you',
        tone: 'stuck',
        title: 'AGNI is stuck — take over',
        body: settings.dispatcher_phone_set === false
          ? 'Needs a human, but DISPATCHER_PHONE_NUMBER is not set.'
          : 'Press Take over (J). Your phone rings; AGNI steps aside.',
        action: 'jump',
      };
    }
    // Jobs beat: ElevenLabs just spoke the Bright Data safe path (live on the phone).
    if (pathForFocus?.say && focusLive && !climaxForFocus) {
      return {
        id: 'path',
        who: 'AGNI',
        tone: 'path',
        title: 'Guiding them to safety',
        body: pathForFocus.shelter_name
          ? `Speaking the path to ${pathForFocus.shelter_name} · Bright Data capacity, not downwind.`
          : 'Speaking one safe direction from the Bright Data shelter cache.',
        action: 'watch',
      };
    }
    if (climaxForFocus?.source === 'unit.dispatched' || climaxForFocus?.source === 'warning.sent') {
      const unitBit = [
        climaxForFocus.callsign || climaxForFocus.unit_id,
        climaxEtaLabel,
      ].filter(Boolean).join(' · ');
      const warnBit = climaxForFocus.warned
        ? (climaxForFocus.recipients != null
          ? `Warning calls to ${climaxForFocus.recipients} opt-in home${climaxForFocus.recipients === 1 ? '' : 's'}.`
          : 'Warning calls to opt-in homes.')
        : 'Optional: R (ring) then W (warn opt-in homes).';
      return {
        id: 'help',
        who: 'Help',
        tone: 'help',
        title: pathForFocus?.shelter_name
          ? `Caller headed to ${pathForFocus.shelter_name}. Unit en route.`
          : 'Unit en route. Caller has a safe direction.',
        body: `${unitBit ? `${unitBit}. ` : ''}${warnBit}`,
        action: climaxForFocus.warned ? null : 'warn',
      };
    }
    if (focusLive) {
      return {
        id: 'agent',
        who: 'AGNI',
        tone: 'agent',
        title: 'AGNI is handling this call',
        body: landmarkNow
          ? `Listening · ${truncate(landmarkNow, 56)}. Your job: Confirm when the pin is real.`
          : 'Asking intake (what they see, where, can everyone walk). You watch the transcript.',
        action: 'watch',
      };
    }
    if (relatedMerge?.state === 'suggested') {
      return {
        id: 'merge',
        who: 'You decide',
        tone: 'decide',
        title: 'Same fire or two fires?',
        body: 'Two reports look close. Merge (M) or keep apart (N). You decide. AGNI only suggests.',
        action: 'merge',
      };
    }
    if (focusIncident && (focusIncident.status === 'possible' || focusIncident.status === 'unverified')) {
      return {
        id: 'confirm',
        who: 'You decide',
        tone: 'decide',
        title: 'Confirm this is a fire?',
        body: 'Press Confirm (↵) if the pin is real, or Not a fire. You decide. AGNI only suggests.',
        action: 'confirm',
      };
    }
    if (focusIncident && focusIncident.status === 'confirmed' && !focusIncident.assigned_unit) {
      return {
        id: 'dispatch',
        who: 'You decide',
        tone: 'decide',
        title: 'Approve a unit?',
        body: 'Fire confirmed. Send one engine when the route looks right (A). You decide. AGNI only suggests.',
        action: 'dispatch',
      };
    }
    if (focusIncident && (focusIncident.status === 'dispatched' || focusIncident.assigned_unit)) {
      return {
        id: 'warn',
        who: 'You decide',
        tone: 'decide',
        title: 'Help is en route — warn the path?',
        body: 'Optional. Grow the 30-min estimate ring (R), then Send to opt-in phones only (W). You decide. AGNI only suggests.',
        action: 'warn',
      };
    }
    return {
      id: 'calm',
      who: 'Waiting',
      tone: 'calm',
      title: settings.overflow_enabled ? '911 is busy. AGNI is standing by.' : 'Overflow is OFF',
      body: settings.overflow_enabled
        ? 'Public ears already listening. Dial AGNI → pin appears → you Confirm.'
        : 'Turn Overflow ON first. AGNI only answers when 911 is busy.',
      action: null,
    };
  })();

  // Demo stage rail — derived from live state, never a fake slideshow.
  const demoStages = [
    { id: 'standby', label: 'Standby' },
    { id: 'call', label: 'Call' },
    { id: 'path', label: 'Safe path' },
    { id: 'confirm', label: 'Confirm' },
    { id: 'dispatch', label: 'Approve' },
    { id: 'help', label: 'En route' },
  ];
  const demoStageId = (() => {
    if (mode.id === 'help' || climaxForFocus?.source === 'unit.dispatched' || climaxForFocus?.warned) {
      return 'help';
    }
    if (mode.id === 'dispatch' || mode.id === 'warn') return 'dispatch';
    if (mode.id === 'confirm' || mode.id === 'merge') return 'confirm';
    if (mode.id === 'path' || (pathForFocus?.say && focusLive)) return 'path';
    if (mode.id === 'agent' || mode.id === 'stuck' || mode.id === 'human' || focusLive) return 'call';
    if (focusIncident && (focusIncident.status === 'possible' || focusIncident.status === 'unverified')) {
      return 'confirm';
    }
    if (focusIncident && focusIncident.status === 'confirmed') return 'dispatch';
    if (focusIncident && (focusIncident.status === 'dispatched' || focusIncident.assigned_unit)) {
      return 'help';
    }
    return 'standby';
  })();
  const demoStageIndex = demoStages.findIndex(s => s.id === demoStageId);

  // Keyboard + action strip follow the same mode model.
  const nextStep = {
    title: mode.title,
    body: mode.body,
    action: mode.action, // watch | jump | handback | confirm | merge | dispatch | warn | null
  };
  void tick; // keep live call clock / silence detector fresh

  const callActive = Boolean(focusLive);
  const showFireList = !callActive || incidents.length > 1;
  const showDeepEvidence = !callActive || evidenceOpen || mode.id === 'confirm' || mode.id === 'dispatch';
  const pinHonesty = pinSourceLabel(
    focusIncident?.location_src || selected?.location_src,
    focusIncident?.landmark_chip || selected?.landmark_chip,
  );

  const supportingEvidence = evidenceRows.filter(r => r.state === 'agree');
  const waitingEvidence = evidenceRows.filter(r => r.state !== 'agree' && r.state !== 'disagree');
  const visibleEvidence = evidenceOpen ? evidenceRows : supportingEvidence.slice(0, 3);

  return (
    <div className="stage">
      <div className="map-host" ref={mapNode} />

      <div className="hud">
        <div className="brand">
          AGNI
          <small>911 overflow · not a replacement</small>
          {settings.mode !== 'live' && <span className="replay-tag">Practice · mock feeds</span>}
          {isReplay && settings.mode === 'live' && <span className="replay-tag">Replay frames on</span>}
        </div>

        <button
          className={`overflow-fab ${settings.overflow_enabled ? 'on' : ''}`}
          onClick={toggleOverflow}
          disabled={busy}
          title="Overflow answers only when 911 is busy — never a 911 replacement"
        >
          <i />
          <span className="overflow-fab-copy">
            <strong>Overflow {settings.overflow_enabled ? 'ON' : 'OFF'}</strong>
            <em>
              {settings.overflow_enabled
                ? 'Only answers when 911 is busy'
                : 'AGNI will not answer'}
            </em>
          </span>
        </button>

        <div className="map-loc-chip" role="note">
          <strong>Caller location</strong>
          <span>
            {pinHonesty
              || 'From landmark cache or GPS (never invented)'}
          </span>
        </div>

        <div
          className={`mode-banner glass tone-${mode.tone}`}
          role={mode.id === 'stuck' || mode.id === 'help' ? 'alert' : 'status'}
          aria-live="polite"
        >
          <div className="mode-who">
            <span className={`mode-dot ${mode.tone}`} />
            <span className="mode-who-label">{mode.who}</span>
            {callActive || mode.id === 'help' ? (
              <span className="mode-clock">{fmtClock(dispatchClock)}</span>
            ) : null}
          </div>
          <div className="mode-copy">
            <strong>{mode.title}</strong>
            <p>{mode.body}</p>
          </div>
          <div className="mode-cta">
            {mode.action === 'jump' ? (
              <button
                type="button"
                className="btn primary compact"
                disabled={busy || settings.dispatcher_phone_set === false}
                onClick={jumpIn}
              >
                <kbd>J</kbd> Take over
              </button>
            ) : null}
            {mode.action === 'handback' ? (
              <button type="button" className="btn primary compact" disabled={busy} onClick={handBack}>
                <kbd>J</kbd> Hand back
              </button>
            ) : null}
            {mode.action === 'watch' ? (
              <span className="mode-hint">AGNI on the line · you watch</span>
            ) : null}
            {mode.action === 'confirm' ? (
              <button type="button" className="btn primary compact" disabled={busy || !selected} onClick={confirmFire}>
                <kbd>↵</kbd> Confirm
              </button>
            ) : null}
            {mode.action === 'dispatch' ? (
              <button type="button" className="btn primary compact" disabled={busy} onClick={approveDispatch}>
                <kbd>A</kbd> Approve
              </button>
            ) : null}
            {mode.action === 'warn' && mode.id === 'help' ? (
              <span className="mode-hint">Optional · R then W</span>
            ) : null}
          </div>
        </div>

        <nav className="demo-stage" aria-label="Demo stage">
          {demoStages.map((stage, idx) => {
            const done = idx < demoStageIndex;
            const current = idx === demoStageIndex;
            return (
              <span
                key={stage.id}
                className={`demo-stage-item ${done ? 'done' : ''} ${current ? 'current' : ''}`}
              >
                <i />
                {stage.label}
              </span>
            );
          })}
        </nav>

        {pathForFocus?.say ? (
          <div className="jobs-reveal glass" role="status" aria-live="polite">
            <div className="jobs-reveal-kicker">
              {focusLive ? 'Caller hears this now' : 'Caller heard'}
              <span> · Bright Data shelter · not downwind</span>
            </div>
            <blockquote className="jobs-reveal-quote">
              “{pathForFocus.say}”
            </blockquote>
            <div className="jobs-reveal-meta">
              {pathForFocus.shelter_name ? (
                <span>{pathForFocus.shelter_name}</span>
              ) : null}
              {typeof pathForFocus.room === 'number' ? (
                <span>Room for ~{pathForFocus.room}</span>
              ) : null}
              {pathForFocus.refused_name ? (
                <span className="jobs-reveal-refused">
                  Refused {pathForFocus.refused_name}
                  {pathForFocus.refused_why ? ` · ${pathForFocus.refused_why}` : ''}
                </span>
              ) : null}
            </div>
            {climaxForFocus?.source === 'unit.dispatched' ? (
              <p className="jobs-reveal-unit">
                {[climaxForFocus.callsign || climaxForFocus.unit_id, climaxEtaLabel]
                  .filter(Boolean)
                  .join(' · ')}
                {' · en route to the fire'}
              </p>
            ) : null}
          </div>
        ) : null}

        {notice ? <div className="banner">{notice}</div> : null}

        <aside className="left-panel glass">
          <div className="panel-head">
            <strong>
              {callActive
                ? (focusHuman
                  ? "Live call · you're talking"
                  : focusStuck
                    ? 'Live call · AGNI stuck — take over'
                    : 'Live call · AGNI is asking intake')
                : 'Fires'}
            </strong>
            <span className="panel-head-actions">
              <button
                type="button"
                className="linkish slate-btn"
                disabled={busy}
                onClick={clearSlate}
                title="Wipe fires/calls for the next judge"
              >
                Clean slate
              </button>
              <span>{String(incidents.length).padStart(2, '0')}</span>
            </span>
          </div>
          <p className="panel-why">
            {callActive
              ? (focusHuman
                ? 'Your job: help the caller, then Hand back (J).'
                : focusStuck
                  ? 'Your job: Take over (J) — AGNI needs a human.'
                  : 'Your job: Confirm when the pin is real.')
              : 'One row per fire — not per call. Open a row to act.'}
          </p>

          {mode.id === 'calm' && !incidents.length ? (
            <div className="left-calm">
              <p className="left-calm-lead">This panel becomes the live call.</p>
              <p className="left-calm-body">
                Dial AGNI → transcript streams here → Confirm (↵) when the pin looks real.
              </p>
            </div>
          ) : null}

          {showFireList && incidents.length > 0 ? (
            <div className="fire-list">
              {incidents.map(item => {
                const mergeSuggested = (state.merges || []).some(
                  m => m.state === 'suggested' && (m.kept_id === item.id || m.merged_id === item.id),
                );
                const badge = newBadge(item);
                const callsFor = (state.calls || []).filter(c => c.incident_id === item.id).length;
                const liveHere = (state.calls || []).some(c => c.incident_id === item.id && callIsActive(c));
                return (
                  <button
                    key={item.id}
                    className={`fire-row ${selected?.id === item.id ? 'on' : ''} ${liveHere ? 'live' : ''}`}
                    onClick={() => setSelectedId(item.id)}
                  >
                    <span className={`dot ${item.status === 'possible' ? 'unverified' : item.status}`} />
                    <span>
                      <strong>
                        {item.title || 'Possible fire'}
                        {liveHere ? <span className="new">LIVE</span> : null}
                        {!liveHere && badge ? <span className="new">{badge}</span> : null}
                      </strong>
                      <em>
                        {item.why_line
                          || (callMeta[item.id]?.landmark_text
                            ? `Caller landmark · ${callMeta[item.id].landmark_text}`
                            : 'Waiting for landmark / evidence')}
                      </em>
                      <div className="meta">
                        {item.status}
                        {callsFor ? ` · ${callsFor} caller${callsFor === 1 ? '' : 's'}` : ''}
                        {item.location_src === 'estimate' ? ' · estimate' : ''}
                      </div>
                      {mergeSuggested ? <div className="merge-hint">Suggested merge · M accept · N keep</div> : null}
                    </span>
                    <span className="lvl">L{item.level || 3}</span>
                  </button>
                );
              })}
            </div>
          ) : !showFireList ? (
            <div className="live-fire-chip">
              <span className={`dot ${selected?.status === 'possible' ? 'unverified' : (selected?.status || 'possible')}`} />
              <div>
                <strong>{selected?.title || 'Live overflow call'}</strong>
                <em>
                  {landmarkNow
                    ? truncate(landmarkNow, 56)
                    : (selected?.lat != null ? 'Pin updating…' : 'Waiting for a spoken landmark…')}
                </em>
                {pinHonesty ? <em className="pin-src">{pinHonesty}</em> : null}
                {selected?.lat == null ? (
                  <em className="pin-miss">Location: not yet — no pin until landmark or GPS</em>
                ) : null}
              </div>
            </div>
          ) : null}

          <div className="detail">
            {selected ? (
              <>
                <h2>{selected.title || 'Incident'}</h2>
                <div className="sub">
                  {callersCount} call{callersCount === 1 ? '' : 's'}
                  {' · '}
                  {incidents.length} fire{incidents.length === 1 ? '' : 's'}
                  {' · '}
                  Headline {measuredHeadline}
                </div>
                <div className="chips">
                  {liveCall ? <span className="chip">Live · {lang}</span> : null}
                  {(callMeta[selected?.id]?.landmark_text || selectedCall?.landmark_text) ? (
                    <span className="chip">
                      {callMeta[selected?.id]?.landmark_text || selectedCall?.landmark_text}
                    </span>
                  ) : null}
                  {selected.immobile ? <span className="chip">Mobility issue</span> : null}
                  {(() => {
                    const label = pinSourceLabel(selected.location_src, selected.landmark_chip);
                    if (label) {
                      return (
                        <span className={`chip ${selected.location_src === 'landmark' ? 'chip-bd' : ''}`} title={label}>
                          {label}
                        </span>
                      );
                    }
                    if (selected.lat == null) return <span className="chip">Location: not yet</span>;
                    return null;
                  })()}
                  {selected.confirmed_by ? <span className="chip">Confirmed · {selected.confirmed_by}</span> : null}
                </div>
                {pinSourceLabel(selected.location_src, selected.landmark_chip) ? (
                  <p className="bd-honest">
                    {pinSourceLabel(selected.location_src, selected.landmark_chip)}
                    {' · Gemini never invents coordinates'}
                  </p>
                ) : selected.lat == null ? (
                  <p className="bd-honest">Location: not yet — no pin until a cached landmark or caller GPS</p>
                ) : null}
                {selected.first_mention?.lead_label ? (
                  <p className="bd-lead" title="Crowd posts are unverified — they raise priority only">
                    {selected.first_mention.lead_label}
                    <span> · unverified</span>
                  </p>
                ) : null}

                {(liveCall || callerLines.length || handoff) && (
                  <>
                    {handoff?.incident_id === selected.id && (
                      <div className="handoff">
                        <div className="eyebrow">YOU&apos;RE LIVE</div>
                        <p>{handoff.summary || 'Dispatcher on the call'}</p>
                        <p className="handoff-hint">Talk to the caller. Press J or Hand back when AGNI should resume.</p>
                      </div>
                    )}
                    {liveCall && !humanOnCall ? (
                      <p className="role-legend-hint">
                        AGNI is asking intake · you watch here · Confirm <kbd>↵</kbd> when the pin is real
                        {isStuck ? <> · Take over <kbd>J</kbd> if stuck</> : null}
                      </p>
                    ) : null}
                    <div className="section-label">
                      {liveCall ? <span className="live-dot" /> : null}
                      {liveCall ? 'Live transcript · what the caller is saying' : 'Transcript'}
                    </div>
                    <div className="transcript" aria-live="polite">
                      {callerLines.map((line, index) => (
                        <p key={`${line.ts || index}-${line.speaker || ''}-${index}`}>
                          <b>{line.speaker || 'caller'}</b>
                          {line.text}
                          {line.lang && line.lang !== 'en' ? <span className="lang">{String(line.lang).toUpperCase()}</span> : null}
                        </p>
                      ))}
                      {!callerLines.length && liveCall && (
                        <p className="transcript-wait">Listening… waiting for the next spoken line.</p>
                      )}
                      {!callerLines.length && !liveCall && (
                        <p className="transcript-wait">No transcript for this call yet.</p>
                      )}
                    </div>
                  </>
                )}

                {!callActive ? (
                  <div className="next-step">
                    <div className="eyebrow">Do this next</div>
                    <strong>{nextStep.title}</strong>
                    <p>{nextStep.body}</p>
                  </div>
                ) : null}

                {selected?.id && camByIncident[selected.id]?.url ? (
                  <div className="cam-code-panel optional">
                    <div className="eyebrow">Optional: caller camera</div>
                    {camByIncident[selected.id].sms_ok ? (
                      <>
                        <p className="cam-ready-title">Text sent to caller</p>
                        <p className="cam-help">They can tap the link and point at the smoke. Not required to Confirm.</p>
                      </>
                    ) : (
                      <>
                        <p className="cam-ready-title">Short link ready</p>
                        <p className="cam-help">Only if you want a photo. Not required to Confirm.</p>
                        <button
                          type="button"
                          className="btn ghost row"
                          onClick={() => {
                            const url = camByIncident[selected.id].url;
                            if (!url) return;
                            navigator.clipboard?.writeText(url).then(
                              () => setNotice('Link copied — text it to the caller if you want a photo'),
                              () => setNotice(url),
                            );
                          }}
                        >
                          Copy link for caller
                        </button>
                      </>
                    )}
                  </div>
                ) : null}

                <div className="section-label">Why this pin · evidence that agrees</div>
                <p className="why-line">
                  {whyLine || selected.why_line || 'Only a caller report so far — nothing else agrees yet.'}
                </p>

                {showDeepEvidence ? (
                  <>
                    <div className="section-label">
                      Evidence
                      <span className="section-count">
                        {supportingEvidence.length} support · {waitingEvidence.length} waiting
                      </span>
                    </div>
                    <div className="evidence">
                      {(visibleEvidence.length ? visibleEvidence : evidenceRows.slice(0, 1)).map(row => (
                        <div className={`ev-row ${row.statusCls}`} key={row.source}>
                          <span className={`ev-dot ${row.state || 'unknown'}`} aria-hidden />
                          <span className="ev-body">
                            <span className="ev-top">
                              <b>{row.label}</b>
                              <em className={`ev-chip ${row.statusCls}`}>{row.statusChip}</em>
                            </span>
                            {evidenceOpen ? <small>{row.detail}</small> : null}
                          </span>
                        </div>
                      ))}
                    </div>
                    <button
                      type="button"
                      className="linkish"
                      onClick={() => setEvidenceOpen(open => !open)}
                    >
                      {evidenceOpen
                        ? 'Hide full checklist'
                        : `Show full checklist (${evidenceRows.length})`}
                    </button>
                    {selected?.lat != null && cameras.some(c => c.image) && (
                      <button
                        type="button"
                        className="btn ghost row"
                        style={{ marginTop: 8 }}
                        disabled={busy}
                        onClick={checkCamerasWithGemini}
                      >
                        Ask Gemini about these cameras
                      </button>
                    )}
                  </>
                ) : (
                  <button type="button" className="linkish" onClick={() => setEvidenceOpen(true)}>
                    Show evidence checklist
                  </button>
                )}

                {relatedMerge?.state === 'suggested' && (
                  <div className="actions">
                    <div className="human-note">Two reports may be the same fire. You decide. AGNI only suggests.</div>
                    <button className="btn primary" disabled={busy} onClick={() => mergeAction('accept')}>
                      <kbd>M</kbd> Same fire — merge
                    </button>
                    <button className="btn ghost row" disabled={busy} onClick={() => mergeAction('keep-apart')}>
                      <kbd>N</kbd> Keep as two fires
                    </button>
                  </div>
                )}
                {relatedMerge?.state === 'accepted' && (
                  <button className="btn ghost row" disabled={busy} onClick={() => mergeAction('undo')}>
                    <kbd>U</kbd> Undo merge
                  </button>
                )}

                <div className="actions">
                  {nextStep.action === 'watch' && (
                    <>
                      <button
                        className="btn ghost row"
                        disabled={busy || !selected || ['confirmed', 'dispatched', 'closed'].includes(selected.status)}
                        onClick={confirmFire}
                      >
                        <kbd>↵</kbd> Confirm fire when ready
                      </button>
                      <p className="consequence agent-watch">
                        You decide. AGNI only suggests. Cameras are optional backup.
                      </p>
                    </>
                  )}
                  {nextStep.action === 'confirm' && (
                    <>
                      <button
                        className="btn primary"
                        disabled={busy || !selected || ['confirmed', 'dispatched', 'closed'].includes(selected.status)}
                        onClick={confirmFire}
                      >
                        <kbd>↵</kbd>
                        Confirm this is a fire
                      </button>
                      <p className="consequence">You decide. AGNI only suggests.</p>
                      <button className="btn ghost row" disabled={busy} onClick={rejectFire}>
                        Not a fire
                      </button>
                    </>
                  )}
                  {nextStep.action === 'jump' && (
                    <>
                      <button
                        className="btn primary"
                        disabled={busy || settings.dispatcher_phone_set === false}
                        onClick={jumpIn}
                      >
                        <kbd>J</kbd> Take over — AGNI is stuck
                      </button>
                      <p className="consequence">
                        {settings.dispatcher_phone_set === false
                          ? 'Blocked until DISPATCHER_PHONE_NUMBER is set in .env.'
                          : 'Your phone rings. AGNI steps aside. You decide.'}
                      </p>
                    </>
                  )}
                  {nextStep.action === 'handback' && (
                    <>
                      <button className="btn primary" disabled={busy} onClick={handBack}>
                        <kbd>J</kbd> Hand back to AGNI
                      </button>
                      <p className="consequence">You&apos;re live with the caller. Hand back when done.</p>
                    </>
                  )}
                  {nextStep.action === 'dispatch' && (
                    <>
                      <button className="btn primary" disabled={busy} onClick={approveDispatch}>
                        <kbd>A</kbd> Approve dispatch
                      </button>
                      <p className="consequence">You decide. AGNI only suggests. One unit — pressing twice won&apos;t send two.</p>
                    </>
                  )}
                  {nextStep.action === 'warn' && (
                    <>
                      <button className="btn ghost row" disabled={busy || !selected.lat} onClick={createRing}>
                        <kbd>R</kbd> Show 30-min estimate ring
                      </button>
                      <button
                        className="btn primary"
                        disabled={busy || !selectedRing}
                        onClick={sendWarning}
                        title={!selectedRing ? 'Grow the ring first' : 'Send warning'}
                      >
                        <kbd>W</kbd> Send warning
                      </button>
                      <p className="consequence">
                        {selectedRing
                          ? 'You decide. AGNI only suggests. Calls only opted-in numbers in the ring.'
                          : 'You decide. Grow the ring (R) first, then Send.'}
                      </p>
                    </>
                  )}
                  {['confirmed', 'dispatched', 'closed'].includes(selected.status)
                    && !['confirm', 'watch', 'jump', 'handback'].includes(nextStep.action || '') && (
                    <button className="btn ghost row" disabled={busy} onClick={signClose}>
                      <kbd>S</kbd> Sign & close
                    </button>
                  )}
                  <div className="human-note">You decide. AGNI only suggests.</div>
                </div>
              </>
            ) : mode.id !== 'calm' ? (
              <div className="empty calm">
                <p className="hint-line">Select a fire row, or wait for the next call.</p>
              </div>
            ) : null}
          </div>
        </aside>

        <div className="metrics glass">
          <div className="row">
            <span>Signal to dispatch</span>
            <b>{fmtClock(dispatchClock)}</b>
          </div>
          <div className="row">
            <span>Units free</span>
            <b>{unitsTotal ? `${unitsFree}/${unitsTotal}` : '—'}</b>
          </div>
          <div className="row">
            <span>Residents warned</span>
            <b>{residentsWarned == null ? (proof.sim ? '0' : '—') : residentsWarned}</b>
          </div>
        </div>

        <aside className={`news-box glass ${newsPulse ? 'pulse' : ''} ${callActive ? 'dimmed' : ''}`} key={`news-${newsPulse}`}>
          <div className="news-head">
            <strong>Public ears (Bright Data)</strong>
            <span className={newsStale ? 'stale' : ''}>
              {newsItems.length
                ? `${newsItems.length} · ${ageLabel(newsItems[0]?.scraped) || 'cache'}`
                : 'empty'}
            </span>
          </div>
          <p className="news-sub">
            Residents mentioned smoke earlier · raises priority only · never dispatches
          </p>
          {selected?.first_mention?.lead_label ? (
            <p className="news-lead">{selected.first_mention.lead_label}</p>
          ) : null}
          {newsItems.length ? (
            <ul className="news-list">
              {newsItems.slice(0, callActive ? 3 : 5).map(item => (
                <li key={item.id || item.signal_id || item.url || item.text}>
                  <span className={`src ${String(item.source || 'serp').toLowerCase()}`}>
                    {String(item.source || 'serp').toUpperCase()}
                  </span>
                  <span className="age">{ageLabel(item.scraped) || '—'}</span>
                  {item.url ? (
                    <a href={item.url} target="_blank" rel="noreferrer" title={item.text}>
                      {truncate(item.text || item.place_text, 88)}
                    </a>
                  ) : (
                    <span title={item.text}>{truncate(item.text || item.place_text, 88)}</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="news-empty">No cached public mentions yet — waiting for Bright Data cache.</p>
          )}
          <p className="news-foot">Cached ahead of calls · never runs during a live call</p>
        </aside>

        {selected?.status === 'confirmed' && routeUnit && !selected.assigned_unit && (
          <div className="route-card glass">
            <div className="route-card-head">
              <strong>Get them out of danger</strong>
              <span>Unit to the fire · caller to a safe shelter · you Approve once</span>
            </div>
            {route?.shelter?.name ? (
              <p className="escape-line">
                Caller path · AGNI will say: go toward <b>{route.shelter.name}</b>
                {route.refused?.[0]
                  ? ` · not ${route.refused[0].name || route.refused[0].why}`
                  : ' · not downwind'}
              </p>
            ) : (
              <p className="escape-line">Caller path · stay safe until a shelter route is ready</p>
            )}
            <h3>{routeLabel}</h3>
            {(route?.brightdata_chips || []).length ? (
              <div className="route-bd-chips">
                {(route.brightdata_chips || []).map(chip => (
                  <p key={chip.kind || chip.text} className="route-bd-chip" title={chip.detail || ''}>
                    {/closure|avoid/i.test(chip.kind || chip.text || '')
                      ? 'Bright Data closure · '
                      : /shelter|capacity/i.test(chip.kind || chip.text || '')
                        ? 'Bright Data shelter · '
                        : 'Bright Data · '}
                    {chip.text}
                    {chip.detail ? <span> · {truncate(chip.detail, 42)}</span> : null}
                  </p>
                ))}
              </div>
            ) : avoids.length ? (
              <p className="route-bd-chip">Bright Data closures · avoids {avoids.length} road block{avoids.length === 1 ? '' : 's'}</p>
            ) : null}
            {route?.shelter?.capacity_label || route?.shelter?.room != null || route?.shelter?.name ? (
              <p className="route-shelter">
                Bright Data shelter · {route.shelter.name}
                {route.shelter.room != null ? ` · ~${route.shelter.room} open` : ''}
                {route.shelter.capacity_label ? ` · ${route.shelter.capacity_label}` : ''}
                {route.shelter.status ? ` · ${route.shelter.status}` : ''}
              </p>
            ) : null}
            {route?.refused?.length ? (
              <p style={{ color: 'var(--mu)' }}>
                Not routing to {route.refused[0].name || route.refused[0].why}
                {route.refused[0].why && route.refused[0].name ? ` (${route.refused[0].why})` : ''}
              </p>
            ) : null}
            {route?.route_kind === 'estimate' || routeUnit?.route_kind === 'estimate' ? (
              <p>Straight-line estimate · road route unavailable</p>
            ) : null}
            <button className="btn primary" disabled={busy} onClick={approveDispatch}>
              Approve dispatch ↑
            </button>
            <p className="consequence route-consequence">You decide. AGNI only suggests. One unit.</p>
            <button className="alt" type="button" onClick={loadRoute}>Choose another unit</button>
          </div>
        )}

        <div className={`camera-strip ${callActive ? 'live-call' : ''}`}>
          <div className="camera-strip-head">
            <strong>Nearby cameras</strong>
            <span>Confirm the caller&apos;s report (ALERTCalifornia does discovery; we don&apos;t)</span>
          </div>
          {cameraStatus === 'idle' || !cameraItems.length ? (
            <div className="camera-idle glass">
              {selected?.lat != null && selected?.lon != null
                ? (cameraReason || 'Loading nearby cameras…')
                : 'Appear after a location pin'}
            </div>
          ) : (
            <div className="camera-tiles">
              {cameraItems.map((cam, index) => (
                <article className="cam-tile" key={cam.id || index}>
                  {cam.image ? (
                    <>
                      <img src={cam.image} alt={cam.name || 'Camera still'} />
                      <span className={`tag ${(cam.frame_source === 'replay' || isReplay) ? 'replay' : ''}`}>
                        {(cam.frame_source === 'replay' || isReplay) ? 'REPLAY' : 'LIVE'}
                      </span>
                    </>
                  ) : (
                    <div className="ph">
                      {cam.loading ? 'Loading still…' : (cam.reason || 'No frame')}
                      <br />
                      <span style={{ color: 'var(--dim)' }}>never means safe</span>
                    </div>
                  )}
                  <div className="cap">
                    <span>{cam.name || `Cam ${index + 1}`}</span>
                    <small>
                      {cam.km != null ? `${cam.km} km` : cam.site || 'ALERTCalifornia'}
                      {cam.online ? ` · ${cam.online}` : ''}
                    </small>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>

        <div className="footer-keys">
          {nextStep.action === 'confirm' && '↵ Confirm fire'}
          {nextStep.action === 'dispatch' && 'A Approve dispatch'}
          {nextStep.action === 'warn' && 'R Ring · W Warn'}
          {nextStep.action === 'merge' && 'M Merge · N Keep apart'}
          {nextStep.action === 'watch' && 'AGNI handling · J only if stuck'}
          {nextStep.action === 'jump' && 'J Take over — AGNI stuck'}
          {nextStep.action === 'handback' && 'J Hand back to AGNI'}
          {!nextStep.action && (settings.overflow_enabled ? 'Dial AGNI · wait for pin' : 'Turn Overflow ON')}
        </div>

        {(mode.id === 'stuck' || mode.id === 'human') && (
          <button
            className={`jump ${mode.id === 'human' ? 'handback' : ''} ${mode.id === 'stuck' ? 'urgent' : ''}`}
            disabled={busy || (mode.id !== 'human' && settings.dispatcher_phone_set === false)}
            onClick={() => (mode.id === 'human' ? handBack() : jumpIn())}
            title={
              mode.id === 'human'
                ? 'Return the caller to AGNI'
                : (settings.dispatcher_phone_set === false
                  ? 'Set DISPATCHER_PHONE_NUMBER in .env first'
                  : 'AGNI is stuck — take over')
            }
          >
            {mode.id === 'human' ? 'HAND BACK' : 'TAKE OVER'}
          </button>
        )}
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
