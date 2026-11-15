# AGNI

**911 overflow for wildfire calls.** When every line is busy, AGNI answers, finds the fire from what callers say, and keeps a human in charge of every decision.

> We don’t replace 911. We catch the calls that get dropped today.

**SanD Hacks · UC San Diego · Nov 14–15, 2026**  
Repo: [github.com/bjiby02/agni](https://github.com/bjiby02/agni)

---

## Status: complete for the hackathon demo

Build Spec v2 scope (**T0–T14**) is **shipped** for the SanD Hacks demo — offline `make test` / `AGNI_MOCK=1`, full dispatcher console, voice tools, evidence → confirm → route → dispatch → spread ring → opt-in warning, ops reset, and after-action report.

| | |
|--|--|
| **DONE offline** | T0 skeleton + SSE · T6 merge + undo · T11 spread ring · T14 after-action / proof panel |
| **Shipped, live path ready** | Voice intake · landmarks · camera wall · evidence + Confirm · routing + dispatch · JUMP IN UI · warnings (opt-in) · Bright Data pollers (cached) · surge / ops |
| **LIVE-UNVERIFIED** | Some sponsor APIs need a measured live check with keys (see `STATUS.md`) |
| **BLOCKED / cut** | T16 stretch (Tiger/Solana) cut · Twilio trial cannot SMS freeform camera links (Copy-link workaround) |

Honest detail: [`STATUS.md`](STATUS.md) · live dial checklist: [`docs/LIVE_E2E.md`](docs/LIVE_E2E.md)

---

## Data → Brain → Action

```
DATA                         BRAIN                         ACTION
Bright Data posts/closures   Gemini landmark + triage      ElevenLabs voice (overflow)
ALERTCalifornia CCTV         Neon / SQLite incident store  Twilio phone + warning calls
NASA FIRMS · NWS wind        Evidence stack + why_line     ORS / OSRM route + shelter
NIFC perimeter (cached)      Merge suggest (human M/N)     Serial → station buzz (optional)
        └──────────── AI only suggests · HUMAN confirms fire, dispatch, warning ────────────┘
```

Crowds and cameras **raise priority**. They never dispatch a unit.

---

## What works

| Capability | What you get |
|------------|----------------|
| **Voice intake** | Overflow agent · ≤3 questions · tools under 800 ms · language detect |
| **Landmarks first** | Gemini extracts place words · match against cached landmark list · **never invents coordinates** |
| **Merge + Undo** | Suggest only · Accept (M) / Keep apart (N) · one-key Undo |
| **Confirm** | Evidence stack (callers, cams, posts, FIRMS, NIFC, wind) · gray = unknown · Enter confirms |
| **Route + dispatch** | Nearest unit · avoid closures · downwind shelter refusal · Idempotency-Key · serial bridge |
| **Spread ring** | 30-min estimate from wind · labeled “estimate” |
| **Warnings** | Targeted, opt-in list only · Press 1 → rescue pin |
| **Live area report** | After-action draft from the event clock · human Sign & close |
| **Ops** | Overflow toggle · Clean slate / reset · surge path · proof panel |
| **Mock mode** | `AGNI_MOCK=1` — full product with fixtures, no keys |

Demo beat sheet: [`DEMO_FLOW.md`](DEMO_FLOW.md)

---

## How to run

Python 3.11+ · Node 20+ · secrets only in local `.env` (never commit).

```sh
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
make seed
make dev                    # API → http://127.0.0.1:8000
```

```sh
cd frontend && npm install && npm run dev
# Console → http://127.0.0.1:5173  (proxies /api → :8000)
```

**Offline / judges without keys**

```sh
AGNI_MOCK=1 make test       # under 60 s, no network
AGNI_MOCK=1 make demo       # 5-minute script in mock
make eval                   # writes measured n’s to eval.json (or “not measured yet”)
```

**Live phone demo** — public tunnel + `PUBLIC_BASE_URL` pointed at tool webhooks; dial the AGNI Twilio overflow number (team / `STATUS.md`). Console stays at `http://127.0.0.1:5173`.

---

## Honesty rules (product law)

1. **Overflow only** — center switch `overflow_enabled`; off → “hang up and dial 911.”
2. **A human decides** — Confirm, Approve, Send warning, JUMP IN. AI never turns a pin red alone.
3. **No invented metrics** — headlines read `sim.json` / `eval.json` / the event log, else **“— not measured yet”**.
4. **Bright Data never during a call** — pollers write cache; the agent reads tables only.
5. **Gemini never invents coordinates** — landmarks from a cached list; bearings are a bonus ellipse labeled “estimate.”
6. **Unknown is gray, never green.**
7. Outbound calls only to phones on the opt-in warn list.

AGNI is a hackathon prototype. It is **not** wired into a real 911 center and must not be used for emergency response.

---

## Sponsors in the product

**ElevenLabs** · **Gemini** · **Bright Data** · **Neon** · Twilio · NASA FIRMS · OpenRouteService · ALERTCalifornia · NWS / NIFC

Ceremony credit map: [`docs/CEREMONY_SPONSOR_CREDITS.md`](docs/CEREMONY_SPONSOR_CREDITS.md)

---

## Repo map

| Path | What |
|------|------|
| `backend/` | FastAPI, tools, SSE, services, mock fakes |
| `frontend/` | Dispatcher console (map, fire rows, keyboard) |
| `agent/` | ElevenLabs prompt + webhook tool JSON |
| `seed/` | Landmarks, shelters, units, opt-in warn list |
| `AGENTS.md` | Full Build Spec v2 + agent task list |
| `STATUS.md` | DONE / LIVE-UNVERIFIED / BLOCKED |
