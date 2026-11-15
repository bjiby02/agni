-- JUMP IN, after-action, ops and mock outbox. Phone numbers live in call_contacts only,
-- so nothing that builds prompts for Gemini ever reads them.
CREATE TABLE IF NOT EXISTS call_contacts(
  call_id TEXT PRIMARY KEY, phone TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS handoffs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT NOT NULL, incident_id TEXT,
  summary TEXT NOT NULL, transfer_status TEXT NOT NULL, actor TEXT NOT NULL,
  started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  ended_at TEXT, resumed_by TEXT);
CREATE TABLE IF NOT EXISTS transfer_requests(
  call_id TEXT PRIMARY KEY, requested_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE IF NOT EXISTS reports(
  incident_id TEXT PRIMARY KEY, draft TEXT NOT NULL, clock_json TEXT NOT NULL,
  log_sha256 TEXT NOT NULL, event_count INTEGER NOT NULL, signed_by TEXT, signed_at TEXT,
  anchor_status TEXT NOT NULL DEFAULT 'not_anchored',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE IF NOT EXISTS outbox(
  id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT NOT NULL, target TEXT NOT NULL,
  payload_json TEXT NOT NULL, status TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE IF NOT EXISTS ops_state(
  id INTEGER PRIMARY KEY CHECK(id=1), mode TEXT NOT NULL DEFAULT 'calm',
  safe_mode INTEGER NOT NULL DEFAULT 0, replay_label TEXT,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
INSERT OR IGNORE INTO ops_state(id) VALUES(1);
