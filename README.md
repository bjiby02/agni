# AGNI

**When 911 is flooded, AGNI catches the calls that get dropped — finds the fire, guides the caller to safety, and keeps a human in charge of every decision.**

SanD Hacks · UC San Diego · Nov 14–15, 2026

> We don’t replace 911. We catch the calls that get dropped today.

---

## The problem

In the Eaton Fire, LA County 911 logs show fire reports arriving hours before the first evacuation order. The calls existed. Nobody fused them in time.

When every line is busy, overflow callers get a busy signal or a long hold. Those are the people AGNI is built for.

---

## What AGNI is

An **overflow layer** next to CAD — not in the 911 path.

| Who | What they get |
|-----|----------------|
| **Caller** | ElevenLabs answers in their language, asks at most 3 questions, then speaks **one safe direction** from a Bright Data shelter cache (capacity, not downwind — never invented coordinates). |
| **Dispatcher** | One row per fire (not per call), evidence stack, keyboard Confirm / Approve / JUMP IN / Warn. AI only suggests. |

**Hard product rules**

1. Overflow only — center turns it on/off (`overflow_enabled`).
2. A human Confirm / Approve / Send before fire status, dispatch, or warnings.
3. Bright Data never runs during a live call — cached tables only.
4. Unknown evidence is gray, never green.
5. On-screen metrics come from `sim.json` / `eval.json` or the event log — otherwise “not measured yet”.

---

## The 75-second demo (what judges should feel)

1. **Overflow ON** · dial the AGNI Twilio number  
2. Caller: *“Smoke behind the Vons on Carmel Valley Road.”* — three short questions  
3. **The product moment:** the voice speaks the Bright Data safe path; the console mirrors that exact line  
4. You **Confirm** → **Approve** — unit to the fire  
5. Optional: grow the 30‑min ring → targeted warning (opt-in phones only) · Press 1 → rescue pin  

Full beat sheet: [DEMO_FLOW.md](DEMO_FLOW.md)

---

## Stack (sponsors in the product)

| Layer | Role |
|-------|------|
| **ElevenLabs** | Overflow voice agent + tools + warning agent |
| **Gemini** | Landmarks (no invented coords), camera triage, same-event merge suggest, handoff summary |
| **Bright Data** | Cached posts, closures, **shelter capacity** — public ears that raise priority only |
| **Neon** | Incident / audit store + surge-sim branch (when wired) |
| **FIRMS / NWS / ALERTCalifornia / ORS** | Satellite, wind, cameras confirm reports, routing around closures |

---

## Run locally

Python 3.11+ · Node 20+ · Keys in `.env` only (never commit them).

```sh
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
make seed
make dev                    # API → http://127.0.0.1:8000
```

```sh
cd frontend && npm install && npm run dev
# Console → http://127.0.0.1:5173  (Vite proxies /api → :8000)
```

Live phone tools need a public tunnel (`PUBLIC_BASE_URL`) and the agent tools pointed at it. See [docs/LIVE_E2E.md](docs/LIVE_E2E.md).

**Mock / offline**

```sh
AGNI_MOCK=1 make test
AGNI_MOCK=1 make demo
make eval                   # → measured metrics in eval.json
```

---

## Repo map

| Path | What |
|------|------|
| `backend/agni/` | FastAPI core, tools, SSE events, services |
| `frontend/` | Dispatcher console (Leaflet + React) |
| `agent/` | ElevenLabs system prompt + webhook tool JSON |
| `seed/` | Landmarks, shelters, units, opt-in warn list |
| `AGENTS.md` | Full build spec + task list for agents |
| `STATUS.md` | What’s DONE / BLOCKED / LIVE-UNVERIFIED |

---

## Honesty

AGNI is a hackathon prototype. It is **not** connected to a real 911 center and must not be used for emergency response. Outbound calls only go to numbers on the opt-in list. Every confirm, dispatch, and warning is a human keypress.
