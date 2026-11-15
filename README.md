# AGNI

**911 overflow for wildfire calls.** When every line is busy, AGNI answers, finds the fire from what callers say, and keeps a human in charge of every decision.

> We don’t replace 911. We catch the calls that get dropped today.

In the Eaton fire, reports of smoke in west Altadena sat in the logs for hours before an evacuation order. AGNI is built so those calls don’t wait in a dead queue — overflow picks them up, fuses them into one picture, and a dispatcher decides.

**SanD Hacks · UC San Diego · Nov 14–15, 2026** · [github.com/bjiby02/agni](https://github.com/bjiby02/agni)

---

## What it does

- **Answers overflow** — ElevenLabs voice agent, ≤3 questions, any language, under a second
- **Pins from landmarks** — “behind the Vons, Carmel Valley” → match a cached place list (no made-up coordinates)
- **One row per fire** — duplicate callers become a *suggested* merge; Accept / Keep apart / Undo
- **Cameras confirm** — nearest ALERTCalifornia stills check the report; they don’t invent fires
- **Evidence stack** — callers · cams · posts · FIRMS · NIFC · wind → one “why this pin” line
- **Safe route + dispatch** — nearest unit, avoid closures, refuse downwind shelters; human Approves
- **JUMP IN** — warm transfer to the dispatcher with a Gemini handoff summary
- **30-min spread ring** — estimate from wind, labeled as estimate
- **Targeted warning** — opt-in phones only; Press 1 → rescue pin
- **After-action** — measured clock from the event log; human signs and closes

Crowds and cameras raise priority. They never send a unit.

---

## Data → Brain → Action

Sponsors mapped to what AGNI actually does. Everything still waits on a human.

![Data → Brain → Action](docs/pitch/data-brain-action.png)

| | Layer | What it is |
|--|-------|------------|
| **Data** | Cached ahead · never during a live call | **Bright Data** — crowd, closures, landmarks · **CCTV · ALERTCalifornia** — confirm callers, don’t discover · **NASA FIRMS** — honest if empty · can lag hours |
| **FEEDS → Brain** | What AGNI understands | **Gemini** — landmarks, camera triage, same-fire, handoff · **Neon** — incident memory + audit · **Evidence stack** — “why this pin” |
| **SPEAKS → Action** | What the caller hears | **ElevenLabs** — voice · **Twilio** — number into ElevenLabs · **OpenRouteService** — safe routes · spoken only from a real route |

**HUMAN GATE** — Confirm fire · Approve dispatch · Send warning — AI never does these alone.

**Rule:** Overflow only · Bright Data never on a live call · Gemini never invents coordinates.

---

## Try it

```sh
cp .env.example .env
pip install -r backend/requirements.txt && make seed
AGNI_MOCK=1 make demo          # 5-minute mock, no keys
make dev                       # API :8000 · frontend :5173
```

Full status: [`STATUS.md`](STATUS.md) · live dial: [`docs/LIVE_E2E.md`](docs/LIVE_E2E.md) · demo beats: [`DEMO_FLOW.md`](DEMO_FLOW.md)

---

## Repo

| Path | What |
|------|------|
| `backend/` | FastAPI · tools · SSE · services · mock fakes |
| `frontend/` | Dispatcher console (map, fire rows, keyboard) |
| `agent/` | ElevenLabs prompt + webhook tools |
| `seed/` | Landmarks, shelters, units, opt-in warn list |
| `AGENTS.md` | Build Spec v2 |
| `docs/pitch/` | Pitch slides + architecture image |

**Sponsors in the product:** ElevenLabs · Gemini · Bright Data · Neon · Twilio · NASA FIRMS · OpenRouteService · ALERTCalifornia · NWS / NIFC
