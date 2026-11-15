        CREATE TABLE IF NOT EXISTS incidents(
          id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'possible', level INTEGER NOT NULL DEFAULT 3,
          kind TEXT NOT NULL DEFAULT 'fire', title TEXT, lat REAL, lon REAL, location_src TEXT,
          estimate_m REAL, description TEXT, why_line TEXT, immobile INTEGER NOT NULL DEFAULT 0,
          confirmed_by TEXT, confirmed_at TEXT, merged_into TEXT,
          assigned_unit TEXT, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
          closed_at TEXT);
        CREATE TABLE IF NOT EXISTS units(
          id TEXT PRIMARY KEY, callsign TEXT NOT NULL, type TEXT, lat REAL, lon REAL,
          status TEXT NOT NULL DEFAULT 'available');
        CREATE TABLE IF NOT EXISTS hazards(
          id TEXT PRIMARY KEY, source TEXT NOT NULL, kind TEXT NOT NULL, title TEXT,
          geometry_json TEXT, lat REAL, lon REAL, observed_at TEXT, scraped_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS bearings(
          id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL, call_id TEXT,
  lat REAL, lon REAL, bearing_deg REAL, direction_words TEXT, source TEXT,
          created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
        CREATE TABLE IF NOT EXISTS evidence(
          incident_id TEXT NOT NULL, source TEXT NOT NULL, state TEXT NOT NULL, detail TEXT,
          age_s INTEGER, updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
          PRIMARY KEY(incident_id,source));
        CREATE TABLE IF NOT EXISTS decisions(
          id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT, actor TEXT NOT NULL,
          action TEXT NOT NULL, detail_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
        CREATE TABLE IF NOT EXISTS dispatches(
          id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL, unit_id TEXT NOT NULL,
          idempotency_key TEXT NOT NULL UNIQUE, approved_by TEXT NOT NULL, detail_json TEXT NOT NULL,
  route_kind TEXT, eta_s INTEGER,
          created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
        CREATE TABLE IF NOT EXISTS events(
          seq INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT NOT NULL, incident_id TEXT,
          ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), data_json TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS events_incident_idx ON events(incident_id,seq);
CREATE TABLE IF NOT EXISTS settings(
  id INTEGER PRIMARY KEY CHECK(id=1), overflow_enabled INTEGER NOT NULL DEFAULT 0,
  updated_by TEXT, updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
INSERT OR IGNORE INTO settings(id,overflow_enabled) VALUES(1,0);
CREATE TABLE IF NOT EXISTS calls(
  id TEXT PRIMARY KEY, incident_id TEXT, direction TEXT NOT NULL DEFAULT 'inbound',
  language TEXT, landmark_text TEXT, state TEXT NOT NULL DEFAULT 'live',
  needs_json TEXT NOT NULL DEFAULT '{}', started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  ended_at TEXT);
CREATE TABLE IF NOT EXISTS transcripts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT NOT NULL, speaker TEXT NOT NULL,
  text TEXT NOT NULL, lang TEXT, ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE IF NOT EXISTS rescues(
  id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT, call_id TEXT NOT NULL,
  digits TEXT, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE IF NOT EXISTS landmarks(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, aliases_json TEXT NOT NULL DEFAULT '[]', kind TEXT,
  lat REAL, lon REAL, source TEXT, scraped_at TEXT);
CREATE TABLE IF NOT EXISTS merges(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kept_id TEXT NOT NULL, merged_id TEXT NOT NULL,
  call_id TEXT, distance_m REAL NOT NULL, dt_s INTEGER NOT NULL,
  state TEXT NOT NULL DEFAULT 'suggested', decided_by TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  undone_at TEXT);
CREATE TABLE IF NOT EXISTS rings(
  id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL, minutes INTEGER NOT NULL,
  geom_json TEXT NOT NULL, wind_json TEXT NOT NULL, homes_est INTEGER,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE IF NOT EXISTS warnings(
  id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL, approved_by TEXT NOT NULL,
  recipients INTEGER NOT NULL, languages_json TEXT NOT NULL, message_key TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE IF NOT EXISTS signals(
  id TEXT PRIMARY KEY, source TEXT NOT NULL, url TEXT, text TEXT NOT NULL,
  about_fire INTEGER, place_text TEXT, confidence TEXT, lat REAL, lon REAL,
  incident_id TEXT, scraped_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE IF NOT EXISTS reports(
  id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL UNIQUE,
  draft TEXT NOT NULL, signed_by TEXT, signed_at TEXT, clock_json TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
