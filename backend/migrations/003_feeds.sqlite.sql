-- Caller camera links, public signals, satellite hits and wind observations.
CREATE TABLE IF NOT EXISTS cam_tokens(
  token TEXT PRIMARY KEY, incident_id TEXT NOT NULL, call_id TEXT,
  expires_at TEXT NOT NULL, used_at TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE IF NOT EXISTS camera_frames(
  id INTEGER PRIMARY KEY AUTOINCREMENT, camera_id TEXT, source TEXT NOT NULL, incident_id TEXT,
  token TEXT, heading_deg REAL, lat REAL, lon REAL, accuracy_m REAL, verdict_json TEXT NOT NULL,
  fetched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
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
