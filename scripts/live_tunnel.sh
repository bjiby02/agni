#!/bin/bash
# One-shot: ensure API up, open ONE public tunnel, require tool POST, write PUBLIC_BASE_URL, repoint BOTH agents.
# Prefer *.serveousercontent.com. Reject console.serveo.net. Cloudflare fallback with long wait.
set -u
ROOT=/Users/bijinjiby/AGNI
TUN_LOG=/tmp/agni-tunnel.log
CF_LOG=/tmp/agni-cf.log
export PATH="/opt/homebrew/bin:$PATH"

log() { echo "$(date -u +%H:%M:%S) $*"; }

if ! curl -sf --max-time 3 http://127.0.0.1:8000/health >/dev/null; then
  log "API not up on :8000 — start scripts/api_watch.sh first"
  exit 1
fi

SECRET=$(python3 - <<'PY'
from pathlib import Path
env = {}
for line in Path("/Users/bijinjiby/AGNI/.env").read_text().splitlines():
    if not line.strip() or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip().strip('"')
print(env.get("ELEVENLABS_TOOL_SECRET", ""))
PY
)

tunnel_ok() {
  local base="$1"
  [ -n "$base" ] || return 1
  case "$base" in *console.serveo.net*) return 1 ;; esac
  local h p
  h=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "$base/health" 2>/dev/null || echo 000)
  [ "$h" = "200" ] || return 1
  p=$(curl -sS -o /tmp/live_tun_rf.json -w "%{http_code}" --max-time 20 -X POST "$base/api/tools/report_fire" \
    -H "Content-Type: application/json" -H "X-Agni-Tool-Secret: $SECRET" \
    -d "{\"conversation_id\":\"tun_ok_$(date +%s)\",\"landmark_text\":\"behind the Vons on Carmel Valley\",\"what_seen\":\"smoke\",\"language\":\"en\"}" 2>/dev/null || echo 000)
  [ "$p" = "200" ]
}

repoint_both() {
  local URL="$1"
  python3 - <<PY
from pathlib import Path
import re, json, urllib.request, urllib.error
ROOT = Path("$ROOT")
URL = "$URL".rstrip("/")
text = re.sub(r"^PUBLIC_BASE_URL=.*$", f"PUBLIC_BASE_URL={URL}", ROOT.joinpath(".env").read_text(), flags=re.M)
ROOT.joinpath(".env").write_text(text)
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
body = {"conversation_config": {"agent": {"prompt": {"prompt": prompt, "tools": tools}}}}
ids = [env.get("ELEVENLABS_AGENT_ID"), env.get("ELEVENLABS_WARN_AGENT_ID")]
for aid in ids:
    if not aid:
        continue
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/convai/agents/{aid}",
        data=json.dumps(body).encode(),
        method="PATCH",
        headers={"xi-api-key": ek, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=40) as r:
        print("agent", aid[:12], r.status, URL)
PY
}

# Reuse existing healthy base
CUR=$(grep -E '^PUBLIC_BASE_URL=' "$ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"')
if tunnel_ok "$CUR"; then
  log "Existing tunnel OK $CUR"
  repoint_both "$CUR"
  echo "$CUR"
  exit 0
fi

# Do not kill a healthy SSH that just needs URL sync
WORKING=""

if ! pgrep -f 'ssh.*serveo.net' >/dev/null 2>&1; then
  log "Starting Serveo"
  : >"$TUN_LOG"
  nohup ssh -o RequestTTY=no -o StrictHostKeyChecking=accept-new \
    -o ServerAliveInterval=15 -o ServerAliveCountMax=6 \
    -o ExitOnForwardFailure=yes -o TCPKeepAlive=yes \
    -R 80:127.0.0.1:8000 serveo.net >>"$TUN_LOG" 2>&1 </dev/null &
  disown
fi

for i in $(seq 1 40); do
  sleep 1
  NEW=$(grep -oE 'https://[a-z0-9.-]+\.serveousercontent\.com' "$TUN_LOG" 2>/dev/null | tail -1 || true)
  # Reject console if that is all we got
  if grep -q 'console.serveo.net' "$TUN_LOG" 2>/dev/null && [ -z "$NEW" ]; then
    log "Got console.serveo.net — rejecting, will try Cloudflare"
    break
  fi
  if [ -n "$NEW" ]; then
    log "Serveo URL $NEW — probing tools ($i)"
    if tunnel_ok "$NEW"; then
      WORKING=$NEW
      break
    fi
  fi
done

if [ -z "$WORKING" ]; then
  log "Serveo tool POST failed — Cloudflare fallback"
  pkill -f 'cloudflared tunnel --url' 2>/dev/null || true
  sleep 1
  : >"$CF_LOG"
  nohup cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate >>"$CF_LOG" 2>&1 </dev/null &
  disown
  for i in $(seq 1 90); do
    sleep 1
    NEW=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$CF_LOG" 2>/dev/null | grep -v api.trycloudflare | tail -1 || true)
    [ -n "$NEW" ] || continue
    log "CF URL $NEW — probing ($i)"
    if tunnel_ok "$NEW"; then
      WORKING=$NEW
      # Prefer single tunnel: keep CF, leave Serveo SSH alone if still up (optional kill)
      break
    fi
  done
fi

if [ -z "$WORKING" ]; then
  log "NO working tunnel (tool POST never 200)"
  exit 1
fi

log "Tunnel OK $WORKING — writing .env + repointing agents"
repoint_both "$WORKING"
echo "$WORKING"
