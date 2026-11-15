#!/bin/bash
# API-only watchdog for live dial demos. Does NOT touch tunnels (avoids mid-call 502 thrash).
set -u
ROOT=/Users/bijinjiby/AGNI
API_LOG=/tmp/agni-api.log
WATCH_LOG=/tmp/agni-api-watch.log
VENV="$ROOT/.venv/bin/uvicorn"
LOCKDIR=/tmp/agni-api-watch.lock.dir
export PATH="/opt/homebrew/bin:$PATH"

if ! mkdir "$LOCKDIR" 2>/dev/null; then
  if pgrep -f 'scripts/api_watch.sh' >/dev/null 2>&1; then
    echo "$(date -u +%H:%M:%S) api_watch already running — exit" >>"$WATCH_LOG"
    exit 0
  fi
  rmdir "$LOCKDIR" 2>/dev/null || true
  mkdir "$LOCKDIR" 2>/dev/null || true
fi
trap 'rmdir "$LOCKDIR" 2>/dev/null || true' EXIT

log() { echo "$(date -u +%H:%M:%S) $*" | tee -a "$WATCH_LOG"; }

ensure_api() {
  if curl -sf --max-time 2 http://127.0.0.1:8000/health >/dev/null; then
    return 0
  fi
  if lsof -tiTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    sleep 2
    curl -sf --max-time 2 http://127.0.0.1:8000/health >/dev/null && return 0
  fi
  log "API down — starting (no tunnel restart)"
  for p in $(lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null || true); do
    kill "$p" 2>/dev/null || true
  done
  sleep 1
  cd "$ROOT/backend" || exit 1
  nohup "$VENV" agni.main:app --host 127.0.0.1 --port 8000 >>"$API_LOG" 2>&1 </dev/null &
  for i in $(seq 1 30); do
    sleep 1
    if curl -sf --max-time 2 http://127.0.0.1:8000/health >/dev/null; then
      log "API up"
      return 0
    fi
  done
  log "API failed to start"
  return 1
}

ensure_api
while true; do
  ensure_api
  sleep 5
done
