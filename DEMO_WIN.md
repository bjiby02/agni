# WIN THE DEMO — 90 seconds (do not freestyle)

## Pre-flight (30 seconds before judges)

1. Terminal: `curl -sf http://127.0.0.1:8000/health` → must show `"overflow_enabled":true`
2. Tunnel: `curl -sf "$PUBLIC_BASE_URL/health"` → **200** (if not: run `bash scripts/keep_live.sh`)
3. Browser: http://127.0.0.1:5173 → **Cmd-Shift-R**
4. Click **Clean slate** → confirm **Overflow ON** (top right)
5. Phone unlocked, dial pad ready. **Dial once. Do not hang up and redial.**

Dial: **+1 (743) 330-4352**

---

## Script (say exactly this)

| Who | Words |
|-----|--------|
| You | Dial. Wait for AGNI. |
| AGNI | “…helping 911 while lines are busy…” |
| You | **“Smoke behind the Vons on Carmel Valley Road.”** |
| AGNI | Asks which way / can everyone walk |
| You | **“Smoke to the north. Everyone can walk.”** |
| You | **Stop talking.** Let it give the safe path. |
| Console | Pin appears · quote “Caller hears this now” · shelter **not** the Vons |
| You (keyboard) | **Enter** = Confirm fire |
| You | **A** = Approve dispatch |
| You | Optional **R** then **W** only if time |
| You | Stop. Point at the quote + unit. One line: *“Human confirms. Voice gets them out. Bright Data shelter. We don’t replace 911.”* |

---

## Do NOT

- Redial (creates a second fire / re-asks intake)
- Say vague places (“UCSD”, “near campus”) — use **Vons on Carmel Valley**
- Talk over the safe-path line
- Demo JUMP IN / camera SMS unless judges ask
- Touch Overflow OFF

---

## If something breaks mid-demo

| Symptom | Fix in &lt;10s |
|---------|----------------|
| Call cuts instantly | Overflow OFF or ElevenLabs quota — check overflow pill; Creator plan |
| Pin never appears | You said a bad landmark — say “Vons on Carmel Valley Road” again once |
| No spoken path | Hang up once, Clean slate, dial **once**, use the Vons line |
| Console blank / Failed to fetch | API died — teammate runs `make dev` + keep_live |
| Shelter = same place as fire | Fixed (≥800 m away). If it happens, Confirm + Approve anyway |

---

## Pitch line (close)

> “911 was flooded. AGNI caught the overflow call, pinned the landmark without inventing coordinates, spoke a Bright Data shelter that isn’t downwind, and every dispatch decision stayed with a human.”
