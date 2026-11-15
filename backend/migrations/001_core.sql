-- AGNI schema for Postgres / Neon. Generated from the *.sqlite.sql migrations so both
-- databases have the same tables and columns; the app's SQL runs on either (backend/agni/pg.py).
-- Times are ISO-8601 UTC text in both, so the event log hashes the same on SQLite and Neon.
CREATE TABLE IF NOT EXISTS incidents(
id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'possible', level INTEGER NOT NULL DEFAULT 3,
kind TEXT NOT NULL DEFAULT 'fire', title TEXT, lat REAL, lon REAL, location_src TEXT,
estimate_m REAL, description TEXT, why_line TEXT, immobile INTEGER NOT NULL DEFAULT 0,
confirmed_by TEXT, confirmed_at TEXT, merged_into TEXT,
assigned_unit TEXT, created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')),
closed_at TEXT);
CREATE TABLE IF NOT EXISTS units(
id TEXT PRIMARY KEY, callsign TEXT NOT NULL, type TEXT, lat REAL, lon REAL,
status TEXT NOT NULL DEFAULT 'available');
CREATE TABLE IF NOT EXISTS hazards(
id TEXT PRIMARY KEY, source TEXT NOT NULL, kind TEXT NOT NULL, title TEXT,
geometry_json TEXT, lat REAL, lon REAL, observed_at TEXT, scraped_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS bearings(
id BIGSERIAL PRIMARY KEY, incident_id TEXT NOT NULL, call_id TEXT,
  lat REAL, lon REAL, bearing_deg REAL, direction_words TEXT, source TEXT,
created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')));
CREATE TABLE IF NOT EXISTS evidence(
incident_id TEXT NOT NULL, source TEXT NOT NULL, state TEXT NOT NULL, detail TEXT,
age_s INTEGER, updated_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')),
PRIMARY KEY(incident_id,source));
CREATE TABLE IF NOT EXISTS decisions(
id BIGSERIAL PRIMARY KEY, incident_id TEXT, actor TEXT NOT NULL,
action TEXT NOT NULL, detail_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')));
CREATE TABLE IF NOT EXISTS dispatches(
id BIGSERIAL PRIMARY KEY, incident_id TEXT NOT NULL, unit_id TEXT NOT NULL,
idempotency_key TEXT NOT NULL UNIQUE, approved_by TEXT NOT NULL, detail_json TEXT NOT NULL,
  route_kind TEXT, eta_s INTEGER,
created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')));
CREATE TABLE IF NOT EXISTS events(
seq BIGSERIAL PRIMARY KEY, type TEXT NOT NULL, incident_id TEXT,
ts TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')), data_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS events_incident_idx ON events(incident_id,seq);
CREATE TABLE IF NOT EXISTS settings(
  id INTEGER PRIMARY KEY CHECK(id=1), overflow_enabled INTEGER NOT NULL DEFAULT 0,
  updated_by TEXT, updated_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')));
INSERT INTO settings(id,overflow_enabled) VALUES(1,0) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS calls(
  id TEXT PRIMARY KEY, incident_id TEXT, direction TEXT NOT NULL DEFAULT 'inbound',
  language TEXT, landmark_text TEXT, state TEXT NOT NULL DEFAULT 'live',
  needs_json TEXT NOT NULL DEFAULT '{}', started_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')),
  ended_at TEXT);
CREATE TABLE IF NOT EXISTS transcripts(
  id BIGSERIAL PRIMARY KEY, call_id TEXT NOT NULL, speaker TEXT NOT NULL,
  text TEXT NOT NULL, lang TEXT, ts TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')));
CREATE TABLE IF NOT EXISTS rescues(
  id BIGSERIAL PRIMARY KEY, incident_id TEXT, call_id TEXT NOT NULL,
  digits TEXT, created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')));
CREATE TABLE IF NOT EXISTS landmarks(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, aliases_json TEXT NOT NULL DEFAULT '[]', kind TEXT,
  lat REAL, lon REAL, source TEXT, scraped_at TEXT);
CREATE TABLE IF NOT EXISTS merges(
  id BIGSERIAL PRIMARY KEY, kept_id TEXT NOT NULL, merged_id TEXT NOT NULL,
  call_id TEXT, distance_m REAL NOT NULL, dt_s INTEGER NOT NULL,
  state TEXT NOT NULL DEFAULT 'suggested', decided_by TEXT,
  created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')),
  undone_at TEXT);
CREATE TABLE IF NOT EXISTS rings(
  id BIGSERIAL PRIMARY KEY, incident_id TEXT NOT NULL, minutes INTEGER NOT NULL,
  geom_json TEXT NOT NULL, wind_json TEXT NOT NULL, homes_est INTEGER,
  created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')));
CREATE TABLE IF NOT EXISTS warnings(
  id BIGSERIAL PRIMARY KEY, incident_id TEXT NOT NULL, approved_by TEXT NOT NULL,
  recipients INTEGER NOT NULL, languages_json TEXT NOT NULL, message_key TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')));

-- JUMP IN, after-action, ops and mock outbox. Phone numbers live in call_contacts only,
-- so nothing that builds prompts for Gemini ever reads them.
CREATE TABLE IF NOT EXISTS call_contacts(
  call_id TEXT PRIMARY KEY, phone TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS handoffs(
  id BIGSERIAL PRIMARY KEY, call_id TEXT NOT NULL, incident_id TEXT,
  summary TEXT NOT NULL, transfer_status TEXT NOT NULL, actor TEXT NOT NULL,
  started_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')),
  ended_at TEXT, resumed_by TEXT);
CREATE TABLE IF NOT EXISTS transfer_requests(
  call_id TEXT PRIMARY KEY, requested_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')));
CREATE TABLE IF NOT EXISTS reports(
  incident_id TEXT PRIMARY KEY, draft TEXT NOT NULL, clock_json TEXT NOT NULL,
  log_sha256 TEXT NOT NULL, event_count INTEGER NOT NULL, signed_by TEXT, signed_at TEXT,
  anchor_status TEXT NOT NULL DEFAULT 'not_anchored',
  created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')));
CREATE TABLE IF NOT EXISTS outbox(
  id BIGSERIAL PRIMARY KEY, channel TEXT NOT NULL, target TEXT NOT NULL,
  payload_json TEXT NOT NULL, status TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')));
CREATE TABLE IF NOT EXISTS ops_state(
  id INTEGER PRIMARY KEY CHECK(id=1), mode TEXT NOT NULL DEFAULT 'calm',
  safe_mode INTEGER NOT NULL DEFAULT 0, replay_label TEXT,
  updated_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')));
INSERT INTO ops_state(id) VALUES(1) ON CONFLICT DO NOTHING;

-- Caller camera links, public signals, satellite hits and wind observations.
CREATE TABLE IF NOT EXISTS cam_tokens(
  token TEXT PRIMARY KEY, incident_id TEXT NOT NULL, call_id TEXT,
  expires_at TEXT NOT NULL, used_at TEXT,
  created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')));
CREATE TABLE IF NOT EXISTS camera_frames(
  id BIGSERIAL PRIMARY KEY, camera_id TEXT, source TEXT NOT NULL, incident_id TEXT,
  token TEXT, heading_deg REAL, lat REAL, lon REAL, accuracy_m REAL, verdict_json TEXT NOT NULL,
  fetched_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')));
CREATE TABLE IF NOT EXISTS signals(
  id TEXT PRIMARY KEY, source TEXT NOT NULL, url TEXT NOT NULL UNIQUE, text TEXT NOT NULL,
  place_text TEXT, lat REAL, lon REAL, confidence TEXT NOT NULL, is_fire_report INTEGER NOT NULL DEFAULT 0,
  classifier TEXT NOT NULL, incident_id TEXT, posted_at TEXT, scraped_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS satellite_hits(
  id TEXT PRIMARY KEY, lat REAL NOT NULL, lon REAL NOT NULL, acq_time TEXT, confidence TEXT,
  source TEXT NOT NULL, checked_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wind_obs(
  station TEXT NOT NULL, ts TEXT NOT NULL, dir_deg REAL, speed_mps REAL, fetched_at TEXT NOT NULL,
  PRIMARY KEY(station, ts));
CREATE TABLE IF NOT EXISTS poll_runs(
  name TEXT PRIMARY KEY, status TEXT NOT NULL, detail TEXT, ran_at TEXT NOT NULL);
-- PostGIS (Neon has it): geography columns computed from lat/lon, plus GiST indexes,
-- for ST_DWithin merges and the nearest-unit query. Skipped where PostGIS is not installed.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'postgis') THEN
    CREATE EXTENSION IF NOT EXISTS postgis;
    ALTER TABLE incidents ADD COLUMN IF NOT EXISTS geom geography(Point,4326)
      GENERATED ALWAYS AS (CASE WHEN lat IS NULL OR lon IS NULL THEN NULL
                           ELSE ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography END) STORED;
    ALTER TABLE units ADD COLUMN IF NOT EXISTS geom geography(Point,4326)
      GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography) STORED;
    ALTER TABLE signals ADD COLUMN IF NOT EXISTS geom geography(Point,4326)
      GENERATED ALWAYS AS (CASE WHEN lat IS NULL OR lon IS NULL THEN NULL
                           ELSE ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography END) STORED;
    CREATE INDEX IF NOT EXISTS incidents_geom_idx ON incidents USING gist(geom);
    CREATE INDEX IF NOT EXISTS units_geom_idx ON units USING gist(geom);
    CREATE INDEX IF NOT EXISTS signals_geom_idx ON signals USING gist(geom);
  END IF;
END $$;
