#!/bin/bash
# agni-tunnel-watch
while true; do
  BASE=$(grep -E "^PUBLIC_BASE_URL=" /Users/bijinjiby/AGNI/.env | head -1 | cut -d= -f2- | tr -d '"')
  code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 8 "$BASE/health" || echo 000)
  echo "$(date -u +%H:%M:%S) $code $BASE" >> /tmp/agni-tunnel-watch.log
  sleep 30
done
