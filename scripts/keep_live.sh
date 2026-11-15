#!/bin/bash
# Keep AGNI API + public tunnel alive for phone tools. Do not use uvicorn --reload.
set -u
ROOT=/Users/bijinjiby/AGNI
API_LOG=/tmp/agni-api.log
TUN_LOG=/tmp/agni-tunnel.log
WATCH_LOG=/tmp/agni-keep-live.log
VENV="$ROOT/.venv/bin/uvicorn"
export PATH="/opt/homebrew/bin:$PATH"

log() { echo "$(date -u +%H:%M:%S) $*" | tee -a "$WATCH_LOG"; }

ensure_api() {
  if curl -sf --max-time 2 http://127.0.0.1:8000/health >/dev/null; then
    return 0
  fi
  log "API down — starting"
  # Only kill listeners on 8000, not every uvicorn on the machine.
  for p in $(lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null || true); do
    kill "$p" 2>/dev/null || true
  done
  sleep 1
  cd "$ROOT/backend" || exit 1
  nohup "$VENV" agni.main:app --host 127.0.0.1 --port 8000 >>"$API_LOG" 2>&1 &
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

current_base() {
  grep -E '^PUBLIC_BASE_URL=' "$ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'
}

tunnel_ok() {
  local base="$1"
  [ -n "$base" ] || return 1
  local code
  code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 8 "$base/health" 2>/dev/null || echo 000)
  [ "$code" = "200" ]
}

repoint_agents() {
  local URL="$1"
  python3 - <<PY
from pathlib import Path
import re, json, urllib.request
ROOT = Path("$ROOT")
URL = "$URL".rstrip("/")
text = re.sub(r"^PUBLIC_BASE_URL=.*$", f"PUBLIC_BASE_URL={URL}", (ROOT / ".env").read_text(), flags=re.M)
(ROOT / ".env").write_text(text)
env = {}
for line in text.splitlines():
    if not line.strip() or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip().strip('"')
ek = env.get("ELEVENLABS_API_KEY")
if not ek:
    raise SystemExit("no EL key")
secret = env.get("ELEVENLABS_TOOL_SECRET") or "x"
tools = []
for path in sorted((ROOT / "agent" / "tools").glob("*.json")):
    tool = json.loads(path.read_text())
    name = tool.get("name") or path.stem
    tool.setdefault("api_schema", {})
    tool["api_schema"]["url"] = f"{URL}/api/tools/{name}"
    tool["api_schema"]["method"] = "POST"
    tool["api_schema"].setdefault("request_headers", {})
    tool["api_schema"]["request_headers"]["X-Agni-Tool-Secret"] = secret
    tool["api_schema"]["request_headers"]["Content-Type"] = "application/json"
    tools.append(tool)
prompt = (ROOT / "agent" / "system_prompt.md").read_text()
aid = env.get("ELEVENLABS_AGENT_ID")
body = {"conversation_config": {"agent": {"prompt": {"prompt": prompt, "tools": tools}}}}
req = urllib.request.Request(
    f"https://api.elevenlabs.io/v1/convai/agents/{aid}",
    data=json.dumps(body).encode(),
    method="PATCH",
    headers={"xi-api-key": ek, "Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=40) as r:
    print("agent", r.status, URL)
PY
}

ensure_tunnel() {
  ensure_api || return 1
  local base
  base=$(current_base)
  if tunnel_ok "$base"; then
    return 0
  fi
  # If an ssh forward already exists, do NOT kill it (that caused mid-call 502s).
  if pgrep -f 'ssh.*serveo.net' >/dev/null 2>&1; then
    log "Tunnel SSH alive but /health not 200 yet — waiting"
    for i in $(seq 1 15); do
      sleep 1
      base=$(current_base)
      tunnel_ok "$base" && return 0
      # Also accept newest URL from log
      local NEW
      NEW=$(grep -oE 'https://[a-z0-9.-]+(\.serveousercontent\.com|\.serveo\.net)' "$TUN_LOG" | tail -1 || true)
      if [ -n "$NEW" ] && tunnel_ok "$NEW"; then
        log "Tunnel OK $NEW — repointing agents"
        repoint_agents "$NEW" || log "repoint failed"
        return 0
      fi
    done
    log "Tunnel SSH up but unhealthy — leaving it alone"
    return 1
  fi
  log "No tunnel SSH — starting serveo"
  : >"$TUN_LOG"
  nohup ssh -o StrictHostKeyChecking=accept-new \
    -o ServerAliveInterval=10 \
    -o ServerAliveCountMax=6 \
    -o ExitOnForwardFailure=yes \
    -o TCPKeepAlive=yes \
    -R 80:127.0.0.1:8000 serveo.net >>"$TUN_LOG" 2>&1 &
  local NEW=""
  for i in $(seq 1 30); do
    sleep 1
    NEW=$(grep -oE 'https://[a-z0-9.-]+(\.serveousercontent\.com|\.serveo\.net)' "$TUN_LOG" | tail -1 || true)
    [ -n "$NEW" ] && break
  done
  if [ -z "$NEW" ]; then
    log "No tunnel URL"
    return 1
  fi
  local code=000
  for i in $(seq 1 25); do
    code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 8 "$NEW/health" 2>/dev/null || echo 000)
    [ "$code" = "200" ] && break
    sleep 1
  done
  if [ "$code" != "200" ]; then
    log "Tunnel $NEW still $code"
    return 1
  fi
  log "Tunnel OK $NEW — repointing agents"
  repoint_agents "$NEW" || log "repoint failed"
}

# one-shot bootstrap then loop
ensure_tunnel
while true; do
  ensure_api
  base=$(current_base)
  if ! tunnel_ok "$base"; then
    ensure_tunnel
  fi
  sleep 8
done
