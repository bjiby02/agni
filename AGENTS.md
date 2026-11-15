# AGENTS.md: AGNI, operating manual for a coding agent with no prior context

**Read this whole part before you write any code.** Part A tells you how to work: the rules, what only Bijin can do, how to build without keys, the task list with a test for each task, and when to stop. Part B is the full technical spec (Build Spec v2). If the two disagree, Part A wins on process and Part B wins on contracts (schema, routes, events, prompts).

## A0. Can you finish this without supervision? Read this honestly

You can build and test all of the software on your own, in **mock mode**, with no keys. You **cannot** finish the job end to end alone. About 10 steps need Bijin's accounts, money, a phone or his hands (A2). Some API details in Part B come from docs and were never tested on a live call (A9). Work through the tasks below. Mark each one DONE, BLOCKED (waiting on Bijin) or LIVE-UNVERIFIED. Don't claim something works live until a live check has passed.

## A1. Hard rules (breaking any of these can disqualify the team or harm someone)

1. **Commit window.** Git commits are allowed only from **Sat Nov 14, 2026, 10:30 AM PT to Sun Nov 15, 12:00 PM PT**. Never commit outside it, never rewrite commit dates, and before each push run `git log --format=%ci` to check.
2. **Don't fork the old repo.** Don't fork `bjiby02/ares`. Clone it locally, copy the modules you need (`swarm.py`, `geo.py`, `feeds` and the camera helpers) into the new repo, and never push to Ares. Ares runs on Python's built-in `http.server`. AGNI is a **new FastAPI app** that imports or copies those modules.
3. **Keys stay out of git.** Secrets go only in `.env`, which is gitignored. Commit `.env.example` with variable names only. Never paste a key into a doc, a commit, a log or a chat.
4. **Only call phones on the opt-in list.** Warning and outbound calls may only go to numbers in `seed/warn_list.json`, which holds team phones and judges who agreed. The code must check every outbound number against that list and refuse anything else.
5. **A human decides.** Nothing turns a pin red, dispatches a unit or sends a warning without a human key press (Confirm, Approve or Send). The AI only suggests.
6. **Never invent numbers.** Any metric on screen ("calls → incidents", accuracy, minutes to warning) must come from a file a script produced (`eval.json`, `sim.json`). If that file doesn't exist, show "not measured yet".
7. **Don't spend money.** Use free tiers and the hackathon credits only. If something needs a payment (for example a Twilio number beyond trial credit, or a paid Bright Data dataset over the $100 credit), stop and ask Bijin.
8. **Overflow only.** AGNI is pitched and built as the overflow line for 911. It only takes calls that would otherwise get a busy signal, it has an on/off switch (`overflow_enabled`), and it never claims to replace 911.

## A2. Steps only Bijin can do, about 30 minutes in total

Do these first, or write `BLOCKED: needs Bijin – <item>` in `STATUS.md` and keep building in mock mode.

| # | What | Where | What it gives the agent |
|---|---|---|---|
| H1 | Create the new GitHub repo (inside the window) and give the agent push access | GitHub | repo URL |
| H2 | ElevenLabs account and the Creator month through the SanD Hacks Discord, then create an API key | [ElevenLabs](https://elevenlabs.io/app/settings/api-keys) | `ELEVENLABS_API_KEY` (the agent can then create both agents through the API) |
| H3 | Get a phone number (Twilio trial) and import it into ElevenLabs | [Twilio console](https://console.twilio.com/), [ElevenLabs Twilio integration](https://elevenlabs.io/docs/agents-platform/phone-numbers/twilio-integration/native-integration) | `TWILIO_*`, `ELEVENLABS_PHONE_NUMBER_ID` |
| H4 | Gemini API key | [Google AI Studio API keys](https://aistudio.google.com/api-keys) | `GEMINI_API_KEY` |
| H5 | Bright Data account with promo code `sandhacks26`. Create a SERP zone and a Browser API zone, get the API token, and copy the Reddit and X scraper dataset IDs from the control panel | [Bright Data](https://brightdata.com/cp) | `BRIGHTDATA_*` |
| H6 | Neon account with promo code `hackonneon`, create a project and an API key | [Neon console](https://console.neon.tech/) | `NEON_API_KEY`, `NEON_PROJECT_ID`, `DATABASE_URL` (the agent creates the branches) |
| H7 | NASA FIRMS map key, free by email | [FIRMS map key](https://firms.modaps.eosdis.nasa.gov/api/map_key/) | `FIRMS_MAP_KEY` |
| H8 | OpenRouteService key, free | [ORS sign-up](https://openrouteservice.org/dev/#/signup) | `ORS_API_KEY` |
| H9 | Plug in the Arduino Uno and flash `hardware/uno_station/uno_station.ino` with the Arduino IDE | laptop | `SERIAL_PORT` |
| H10 | Fill `seed/warn_list.json` with opt-in phones, set `DISPATCHER_PHONE_NUMBER`, and **answer the test calls** | his phone | live call checks |
| H11 | Submit Devpost: the first version before **Sun 11:00 AM**, the final before **12:00 PM** | Devpost | – |

Keys go into `.env` on the build machine only, typed there by Bijin. Never ask for a key in a group chat.

## A3. Mock mode (build everything without keys)

- Set `AGNI_MOCK=1` and every outside service uses a fake that returns fixture files from `backend/tests/fixtures/`. The services are ElevenLabs, Gemini, Bright Data, Neon API, FIRMS, NWS, NIFC, ALERTCalifornia, ORS/OSRM, Twilio, serial and Solana.
- Each service in `backend/app/services/*.py` exposes one small interface. It picks the real client or the fake through `config.MOCK`, and nothing else in the app knows which one is in use.
- Use SQLite (`sqlite:///agni.db`) until the Neon task. Write SQL that runs on both, with PostGIS-only parts guarded, as Part B §7 describes.
- Free public feeds with no key (NWS, NIFC, ALERTCalifornia, OSRM) may be called live for the `make live-check` targets. Unit tests must never touch the network.
- `make test` runs every unit and integration test offline in under 60 seconds. `make live-check` runs one real request per service whose key is set, skips the rest with `SKIP: <VAR> not set`, and saves each real response to `backend/tests/fixtures/live/` so you can fix the fakes when the real shape differs.

## A4. How to work

1. Read Part B §1–§9 once, then do the tasks in A5 in order.
2. After every task, update `STATUS.md` with one line per task: DONE, BLOCKED or LIVE-UNVERIFIED, and the test that proves it. Also update `DECISIONS.md` with any choice Part B didn't settle, and why you made it.
3. Commit small, tested steps with messages like `C6: merge suggest + undo (tests pass)`.
4. When a live response doesn't match Part B, don't guess. Save the real response, change the adapter and the fake to match it, note it in `DECISIONS.md`, and keep going.
5. Keep the UI to Part B's screen specs. Dark map with CARTO `dark_matter` tiles, one row per fire, a "why this pin" line on each row, unknown evidence shown as a gray dot (never green), and single-key actions: A approve, J jump in, W warn, U undo, C confirm.

## A5. Task list (each one is finished only when its test passes)

| Task | Build (Part B section) | Proves it works | Needs Bijin |
|---|---|---|---|
| T0 | Repo skeleton, `Makefile`, `.env.example`, config, mock switch, `db.py` + migrations, `bus.py` + SSE (§5, §6, §7, §9) | `make test`: an emitted event shows up on `/api/events` and a reconnect with `since=` replays with no duplicates | H1 |
| T1 | Voice intake tools: `report_fire`, `get_guidance`, `add_bearing`, `set_needs` and the post-call webhook, using the tool secret (C2, §12) | Tests post each tool payload from §12 and get a 200 in under 800 ms, with the right events emitted. `scripts/create_agents.py` builds both agents from §12 through the API | H2, H3, H10 for the live call |
| T2 | Console shell: map, fire list, live call card from events, keyboard shortcuts (C2/C5 UI) | Playwright test: a fake `call.started` plus transcript shows the card within 1 s | – |
| T3 | Caller location: landmark to pin through Gemini and a cached landmark list, bearings with `swarm.py` (C3) | Two fixture bearings give an "estimate" ellipse, and the landmark "behind the Vons, Carmel Valley" gives a pin from the list (Gemini never makes up coordinates) | H4 for live |
| T4 | Camera wall and triage: ALERTCalifornia nearest 3, Gemini smoke verdict with cache, honest live/replay labels (C4, §11, §13.1) | Fixture frames give the schema from §13.1, a timeout gives `cant_tell`, and a cache hit makes no second call | H4 |
| T5 | Evidence stack, the "why this pin" line, Confirm/Reject (C5) | With the FIRMS key missing, the row shows a gray "Key not set" dot, and Confirm writes a `decisions` row | H7 for live |
| T6 | Incident store, duplicate merge (suggest only) and Undo (C6) | Replaying 6 scripted calls gives 2 incidents, Undo restores 3, and no unit is sent twice | – |
| T7 | Nearest unit, routing around closures, safe shelter with `geo.py` downwind refusal (C7) | A closure fixture makes the route avoid it, Torrey Pines HS is refused with its reason, and the fallback line is labeled "estimate" | H8 for live |
| T8 | Dispatch with idempotency key, plus the serial bridge (C8) | Approving twice gives one dispatch, one event and one serial write. The serial fake records the bytes | H9 for the buzz |
| T9 | Bright Data pollers and post classifier, cached and never called during a call (C1, §13) | A fixture SERP gives `signal.new` gray "unverified" rows. A test checks that no Bright Data request happens while a call is active | H5 |
| T10 | JUMP IN: transfer, Gemini handoff summary, hand-back by **calling the caller back**, because the agent is off the line after a transfer (C9) | Fake transfer gives `handoff.started`, and hand-back gives `handoff.ended resumed_by agent` | H10 live phone test |
| T11 | Spread ring, NumPy, 100 m cells, 10 km grid, 30-minute run (C10) | NW wind moves the ring downwind and labels it "30-min estimate" | – |
| T12 | Targeted warning call with Press 1, opt-in list only (C11) | A number not on the opt-in list is refused. A press-1 fake gives a `rescue.requested` pin within 2 s | H10 |
| T13 | Move to Neon plus the `surge-sim` branch, 75-call surge to `sim.json`, /ops panel, Reset to Calm (C12, C14) | 75 calls in 90 s on surge-sim leave main untouched, `sim.json` is written, and Reset finishes in under 5 s | H6 |
| T14 | After-action report: Gemini draft, measured clock, human sign-off, proof panel reads `eval.json`/`sim.json` (C13, §11) | Report times match the events table, and with `eval.json` missing it shows "not measured yet" | – |
| T15 | Eval harness: 25 frames, 30 posts, about 20 merges, plus 10 caller personas × 3 runs (§11) | `make eval` writes `eval.json` with n for every metric | labels need a human check |
| T16 | Stretch, only if T0–T14 pass: Tiger Data counter and Solana devnet memo (C15) | Part B C15 tests | – |
| T17 | README, `make demo`, rehearsal checklist (§15, §19) | Every item in §19 is ticked or marked BLOCKED with a reason | H11 |

## A6. Stop and ask Bijin (write it in `STATUS.md` as `NEEDS BIJIN:`, then keep working on other tasks)

- A key or ID in A2 is missing, and the task needs it live.
- Anything that costs money or goes over a free credit.
- An outbound call or SMS to any number not on the opt-in list.
- Any commit that would fall outside the commit window, or a push to anything other than the new repo.
- Deleting a Neon branch other than `surge-sim` or practice, or dropping data on main.
- A live check showing a feature can't work as specified, for example warm transfer not working on the plan's tier. Propose the fallback from Part B §18 and don't quietly drop the feature.

## A7. What finished looks like

Every task is DONE, or is BLOCKED or LIVE-UNVERIFIED with one line saying what's needed. `make test` passes offline, and `make demo` runs the 5-minute script in Part B §15 in mock mode with no errors. With Bijin's keys added, `make live-check` passes for every service, the phone rings and talks back, and the Part B §19 checklist is green.

## A8. If time runs out, cut in this order

Remove these from the end first: Solana, then Tiger Data, Vultr, the text-message fallback, the after-action draft (keep the measured clock), and Bright Data's Browser API (keep SERP). **Never cut** the voice call, merge with Undo, human Confirm, safe-shelter refusal, or the Press 1 warning.

## A9. Not checked live yet (verify early with `make live-check`)

- ElevenLabs webhook tool field names and the `transfer_to_number` behavior.
- The Gemini smoke-box coordinate format, since Gemini's native `box_2d` is [ymin, xmin, ymax, xmax] on a 0 to 1000 scale. Convert it to 0 to 1 [x0, y0, x1, y1] in one place.
- OpenRouteService `avoid_polygons`.
- Bright Data Reddit and X dataset IDs and the Caltrans QuickMap page selectors, which are left blank on purpose.

---

# Part B: Build Spec v2 (full technical contract)

*Converted from the team's Build Spec v2 so you get one plain-text source. "(image: …)" marks a concept mockup. Its numbers are placeholders, not data.*

SAND HACKS · UC SAN DIEGO · NOV 14–15, 2026

# AGNI Build Spec v2

“When 911 is flooded, AGNI listens to every report, finds the fire, and warns the people in its path, while a human makes every call.”
“We don't replace 911. We catch the calls that get dropped today.”
**What this is.** One document an engineer or a coding agent can follow to build AGNI end to end: every screen, route, table, event, API call, prompt, and test.

**Repo.** Fresh public repo `agni`, seeded from `bjiby02/ares` (no fork, no old history). Commits only Sat 11/14 10:30 AM – Sun 11/15 12:00 PM PT. Initial Devpost submit before Sun 11:00 AM PT.

**Version.** v2 · Sat Nov 14, 2026, ~1:30 PM PT · updated after the team brainstorm (1:20 PM). v1 stays at `AGNI-Build-Spec.pdf`. Written by the Staff Engineer persona with Andrej's ML spec (Section 11). Screens come from prototype v1 (`agni_proto`) and prototype v2 (`agni-proto`, Elon).

**No secrets.** This PDF lists env var names only. Keys go in your local `.env`, never in a chat room or in git.

## What changed in v2 (team brainstorm, Nov 14, 1:20 PM PT)

The team simulated users from first principles and agreed on the points below. Every section of this spec now follows them. Where v1 and v2 disagree, v2 wins.

| # | Change | Where it lands |
|---|---|---|
| 1 | **Overflow layer, not a 911 replacement.** AGNI takes only calls that would hit a busy signal or a long hold. The 911 center turns it on and off (`overflow_enabled`). It never answers a call a human could take. It sits beside CAD/ALI, never in the 911 path. Stage line: “We don't replace 911. We catch the calls that get dropped today.” | §2, §6, C2, C14, deployment note in §2 |
| 2 | **Users and what they need** (simulated personas, not research). | New §2B |
| 3 | **Dispatcher UI: one row per fire, not per call.** “New since you looked” badge. A `why_line` per fire (e.g. “4 callers · cam K-12 smoke · wind NE 25 mph”). Confirm = one key. Merge only **suggests**: new event `incident.merge_suggested`; `incident.merged` now means a human accepted. Undo = one click. Satellite and Reddit are lines in the evidence stack, not panels. Unknown is gray, never green. Any panel slower than 5 s shows a placeholder. | §2B, §7, §8, §9, C5, C6 |
| 4 | **Caller location is landmark-first.** At most 3 questions. Gemini extracts landmark text; we geocode it against a landmark list cached ahead by Bright Data. Gemini never invents coordinates. Compass bearing is a bonus. Callback on dropped call. Spoken ETA only from a real route. People who can't move get a priority flag. | C2, C3, §12, §13 |
| 5 | **Cameras confirm caller reports. They do not discover fires.** ALERTCalifornia already runs AI smoke detection. We don't pitch “AI detects smoke”. | C4, §15, §16 |
| 6 | **Warning call is targeted and two-way.** Only after a human confirms. Only to addresses in the spread ring + downwind zone. (The county already has AlertSanDiego for mass alerts; our new part is targeted + two-way.) Slow, short, names direction and shelter, ends “Press 1 or say help if you need help getting out” → `rescue.requested`. Voice first. | C11, §12 |
| 7 | **Sponsors refocused.** ElevenLabs is the product. Gemini: landmarks, camera checks, post classifier, handoff summary, after-action draft. Bright Data: posts, closures, shelter capacity, landmark list (cached, never during a call). Neon: incident store + audit log + surge-sim/practice branches. Tiger only if the surge counter needs it. **Solana is cut** (Appendix: Cut ideas). Vultr optional. | §16, C15, Appendix |
| 8 | **New Proof and testing section.** Andrej's 10-persona caller harness × 3 runs; Staff's 75-call surge script writing `sim.json`; a 5-minute real check with a fire/EMS/government mentor. **All made-up demo numbers removed.** Headline “N calls → M incidents” reads only from `sim.json`/`eval.json`, else “— not measured yet”. | New §14B, C12, C13, §15 |
| 9 | **Demo script:** overflow opener after Eaton; headline number slot from `sim.json`; warning call is the climax; “one more thing” stays the Press-1 rescue. | §15 |
| 10 | **Build order:** same team checkpoints (voice 2 PM, route+dispatch 5 PM, JUMP IN 8 PM). Real deadlines: initial Devpost Sun 11 AM, final + last commit Sun 12 PM, judging 12:30–2:30 PM. Harness + surge script right after the 2 PM gate. Solana removed. | §14 |

The measured-number rule.
No number appears on a slide, on the console headline, or in the pitch unless it comes from
sim.json
,
eval.json
, or the live event log. Missing file → “— not measured yet”. Screenshots in this PDF are mocks; their numbers are placeholders.

## Contents

What changed in v2
1. How to use this spec
2. Product, users, and the rules
2B. Users and what they need (simulated)
3. System architecture
4. User flows (caller and dispatcher)
5. Repo layout
6. Config: .env.example and credits
7. Database schema (Postgres/PostGIS + SQLite notes)
8. REST API
9. Event contract (SSE, 21 events)
10. Components C1–C16
11. ML spec (Andrej)
12. ElevenLabs agent: prompt and tools
13. Gemini prompts and schemas
14. Build order and checkpoints
14B. Proof and testing
15. 5-minute demo script
16. Sponsor map
17. Honesty rules
18. Risks and fallbacks
19. Acceptance checklist
20. Links and verification status
Appendix: Cut ideas

## 1. How to use this spec

- Build in the order of Section 14. Each checkpoint has a test. Don't start the next block until the test passes.
- Each component in Section 10 has the same seven parts: **(a) UI**, **(b) backend**, **(c) external API**, **(d) events**, **(e) build steps + acceptance test**, **(f) connects to**, **(g) time budget + fallback**.
- The event contract (Section 9) is the glue. The console only draws what arrives as events. Every component writes a row, then emits an event.
- Code is short Python. It shows the shape, not every edge case. Names in `monospace` are the real names to use.
- Where Ares already does the job, keep it. File names from Ares (checked in the public repo): `feeds.py` (wind, cameras, fires, hotspots), `swarm.py` (bearings), `geo.py` (safe destination choice), `store.py`, `server.py`, `bridge.py`, `voice.py`, `web/console.html`, `web/talk.html`.
- Note: Ares `server.py` uses Python's stdlib `http.server`, not FastAPI. AGNI adds a FastAPI app and imports the Ares modules as services.

Golden rules.
(0) AGNI is an overflow layer. It answers only calls 911 cannot pick up, only while the center has it switched on. (1) AI and crowd signals only raise priority. A human confirms the fire, approves dispatch, and sends warnings. (2) The voice agent never calls Bright Data during a call. It reads cached tables. (3) Every estimate is labeled “estimate”. (4) Empty and failed states are shown honestly with a reason. (5) A number appears on screen only after we measured it (
sim.json
,
eval.json
, event log). (6) Unknown is gray, never green.

## 2. Product, users, and the rules

### Why this matters

In the Eaton fire, LA County 911 logs show at least 14 reports of fire in west Altadena before its first evacuation order at 3:25 AM on Jan 8, 2025. All but one of the 18 deaths were in west Altadena (LA Times, [911 logs story](https://www.latimes.com/california/story/2025-04-16/911-logs-west-altadena-eaton-fire-evacuations); [Jan 20 story](https://www.latimes.com/california/story/2025-01-20/in-much-of-altadena-evacuation-orders-came-hours-after-the-fire-arrived)). The reports existed. Nobody fused them in time.

### What AGNI is (and is not)

Overflow layer.
AGNI picks up only the calls that would hit a busy signal or a long hold. The 911 center turns it on and off. It never answers a call a human dispatcher could take. It sits beside the existing CAD (computer-aided dispatch) and ALI (caller location) systems. It is never in the 911 call path.
Stage line:
“We don't replace 911. We catch the calls that get dropped today.”
Deployment note (not part of the demo).
A real center would route overflow to AGNI from its phone system: when all call-takers are busy or the queue wait passes a set limit, the center's call manager forwards the call over a SIP trunk (or plain call forwarding) to the AGNI number on ElevenLabs. ElevenLabs supports SIP trunking (
SIP trunking docs
). The center keeps control: if it turns overflow off, nothing is forwarded. Whether a given 911 center's equipment and rules allow this is a question for that center; we do not claim it. In the demo, judges simply dial our Twilio number.
**Config.** `overflow_enabled` (env `OVERFLOW_ENABLED`, stored in a `settings` row, toggled in /ops). When off, the agent's first tool call `report_fire` returns `{"overflow":false,"say":"Please hang up and dial 911."}` and the console shows “Overflow OFF”.

### Two users on the phone and the screen

| User | Where | What they need | What AGNI gives them |
|---|---|---|---|
| **Caller / resident** | Any phone. No app. Any language. | Be heard now. Know where to go. Not be put on hold. | Only when 911 is busy: ElevenLabs voice agent answers at once, in their language, asks at most 3 questions, takes landmarks, gives one safe direction only from a real route. Calls back if the line drops. Later: a targeted warning call ending “Press 1 or say help if you need help getting out.” |
| **Dispatcher** | Web console (Leaflet map), protected URL + operator token. | One true picture. Fewer duplicate units. Control. | One row per fire (not per call) with a “why this pin” line and a “new since you looked” badge. One-key Confirm, Approve dispatch, Send warning, JUMP IN. Merge suggestions with one-click Accept/Undo. Measured clock. |

### Onboarding (prototype v2, state 1)

First run shows a 2-minute card: “AGNI sits next to your dispatch software. It never sends a unit on its own.” Buttons: **Play a practice incident** (runs on a Neon branch, Section C12/C14) and **Skip**. Callers get no onboarding: they just call.

(image: )

Prototype v2 · state 1 · first-run card. Practice mode badge in the top pill.
Numbers in mocks are placeholders, not measurements.
(image: )

Prototype v2 · state 0 · Calm. 28 cameras, wind, Station 42 (Arduino) marker, JUMP IN disabled.
Numbers in mocks are placeholders, not measurements.

## 2B. Users and what they need (simulated)

These are simulated personas from the team brainstorm, not user research.
They guide design choices. Section 14B(c) is the first real check.
| Persona | Situation | What they need | What AGNI does | Spec |
|---|---|---|---|---|
| **Rosa / María**, older Spanish speaker | Lost, on a landline, can't name a street, scared. 911 line busy. | Be heard in Spanish. Not be asked for an address she doesn't know. | Answers in Spanish. Asks: what do you see, which way is the smoke, is anyone with you and can everyone walk. Takes landmarks (“behind the Vons, near the church”). Landline: no camera link, no compass. | C2, C3 |
| **Dev**, driver | Moving on SR-56, clear line of sight to the plume. | Report fast, hands-free, keep driving. | Short turns. Uses his moving position + “smoke to the north” as a bonus bearing. Never asks him to tap a link while driving. | C2, C3 |
| **Dispatcher with 40 calls** (the real customer) | Queue full. Many callers describe the same fire. | See fires, not calls. Know why each pin exists. Stay in control. | One row per fire, “why this pin” line, “new since you looked” badge. Merge suggestions only, Accept = one key, Undo = one click. Confirm = one key. | C5, C6, console |
| **Mr. Okafor**, 78, hard of hearing, in the path, never called | Home alone downwind. Doesn't watch the news. | A warning he can hear and act on. A way to ask for help. | Targeted warning call after human confirm: slow, short, repeats direction and shelter, ends “Press 1 or say help…”. Press 1 → rescue pin. | C10, C11 |
| **Battalion chief** | On a tablet in the truck. | Where the fire is now vs in 30 min, closures, where units are. | Read-only tablet map view: now vs 30-min estimate ring, closures, units. No buttons that change state. | C7, C10 |
| **County admin** | Sets AGNI up before fire season. | Load units, set the region, set the phone number, practice. | Setup page: upload units CSV, draw/choose region, enter the overflow number, run a practice incident on a Neon practice branch. | C14, Neon |
| **County buyer** | Decides whether to pay. | “Does it touch my 911 lines?” “Who is liable?” | No: it only takes forwarded overflow and sits beside CAD. A human confirms every fire, dispatch and warning; every decision is in the audit log and the after-action report. | §2, C13 |

### Dispatcher console, v2 layout (target)

The prototype mocks show one card per call. v2 changes the left rail to one row per fire. Build this layout:

```
┌─ AGNI ── Overflow ON · 3 live calls ──────────────────────────── Bright Data 2 min · Cams 0:42 ─┐
│ FIRES                         [3]  │                                                         │
│ ● L1  Torrey Pines        NEW 2    │                    (Leaflet map)                        │
│   4 callers · cam K-12 smoke ·     │         fire pins only; calls fold into them           │
│   wind NE 25 mph                   │                                                         │
│   [Enter] Confirm   ↶ Undo merge   │                                                         │
│ ◐ L2  Mira Mesa  (suggested merge) │                                                         │
│   2 callers · no camera yet ·      │                                                         │
│   wind NE 25 mph                   │                                                         │
│   [M] Accept merge  [N] Keep apart │                                                         │
│ ○ L3  Del Mar           unverified │                                                         │
│   1 post (Reddit) · no callers     │                                                         │
│                                    │  Headline: — not measured yet  (reads sim.json)         │
└────────────────────────────────────┴───────────────────────────────── [ J  JUMP IN ] ────────┘
```

- **Badge “NEW n”**: count of calls/evidence added since the dispatcher last opened that row (per-user `last_seen_seq`).
- **why_line**: built by `evidence.why_line()` from the evidence stack, only from sources in state `agree`. Max ~60 characters. Example: “4 callers · cam K-12 smoke · wind NE 25 mph”.
- **Evidence stack** (open a row): callers, cameras, crowd posts (Reddit/X), satellite (FIRMS), perimeter (NIFC), wind. Satellite and Reddit are lines here, not separate panels.
- **Colors**: green = agrees, gray = unknown or no data (never green), red = disagrees.
- **Slow panels**: anything not loaded in 5 s shows a gray placeholder “Loading camera… (5 s+)”, never a blank or a spinner forever.
- **Keys**: Enter Confirm, M accept merge, N keep apart, U undo merge, J JUMP IN.

## 3. System architecture

Caller phone
overflow only (911 busy)
PSTN call · optional cam link
ElevenLabs Agent
voice, language detect,
DTMF, transfer_to_number
Twilio number
native ElevenLabs integration
Bright Data pollers
SERP last hour · Reddit/X
Browser API: QuickMap, shelters
Public feeds
ALERTCalifornia cams · NWS
FIRMS · NIFC WFIGS
FastAPI core (backend/app)
routers: tools, incidents, dispatch,
warnings, cameras, events, ops
services: merge, swarm, evidence,
routing, geo(safe shelter), spread,
gemini, brightdata, eleven, serial
event bus → SSE GET /api/events
Gemini 2.5 Flash
smoke verdict · post classifier
same-event · summary · report
OpenRouteService / OSRM
route with avoid_polygons
Incident store
SQLite now → Neon Postgres + PostGIS
branches: main · surge-sim · practice-*
Stretch (only if needed)
Tiger Data hypertable
for the surge counter
Dispatcher console (web/)
Leaflet map · cards · camera wall
Confirm · Approve · Send warning
JUMP IN · /ops (hidden)
Arduino Uno
USB serial 9600
buzzer + red LED at “station”
Dispatcher phone
receives warm transfer
(JUMP IN)
voice
webhook tools
cached upsert
poll + cache
SSE events
REST actions
serial bytes
transfer
batch calls (warn)
Overflow only: the 911 center forwards calls it cannot answer; AGNI sits beside CAD/ALI, never in the 911 path.
Rule: the agent reads only cached tables during a call. Bright Data, FIRMS, NIFC refresh on background timers.
Every write → one row → one event (incident_id, seq, ts). Console renders events only. Reconnect replays from last seq.

### Backend flow (one report, start to finish)

```
[signal]   Bright Data poller ──► signals table ──► Gemini classify ──► signal.new (dashed pin, "unverified")
[call]     911 busy → overflow → ElevenLabs agent ──► tool report_fire ──► calls row ──► call.started / call.transcript
[locate]   landmark words ──► Gemini extract ──► geocode vs cached landmark list ──► pin  (bearing = bonus ──► ellipse)
[merge]    new call within 800 m & 20 min? ──► Gemini same_event ──► incident.merge_suggested  (or incident.created)
[HUMAN]    dispatcher presses M (accept) ──► incident.merged   ·   U = undo ──► incident.created
[confirm]  pick 3 cams near the reported pin ──► cameras.selected ──► Gemini check ──► triage.result (cameras confirm, never discover)
[sources]  NWS wind, FIRMS, NIFC, posts (cached) ──► satellite.result ──► evidence.updated (why_line; gray if unknown)
[HUMAN]    dispatcher presses Confirm fire ──► incident.status = confirmed ──► evidence.updated{confirmed_by}
[route]    nearest units ──► ORS avoid closures ──► geo.choose() safe shelter ──► route.ready
[HUMAN]    Approve dispatch (Idempotency-Key) ──► unit.dispatched ──► serial "D42\n" ──► Uno buzzes
[talk]     JUMP IN ──► Gemini summary ──► transfer_to_number ──► handoff.started … handoff.ended{resumed_by:"agent"}
[spread]   spread.py (wind) ──► ring.updated (30-min estimate)
[HUMAN]    Send warning (ring + downwind addresses only) ──► POST /api/warnings/{id} ──► batch call ──► warning.sent
[press 1]  DTMF "1" or says "help" ──► tool request_rescue ──► rescue.requested (red rescue pin)
[close]    Gemini draft report ──► human signs ──► incident.closed{report, clock}
```

## 4. User flows

### 4.1 Caller / resident (phone)

```
 Dials 911 ─► all call-takers busy ─► center forwards overflow ─► AGNI answers < 1 s
        │   "This is AGNI, helping 911 while lines are busy. What do you see?"   (Q1)
        │   (language auto-detected; switches to Spanish etc.)
        ▼
 "Smoke behind the Vons on Carmel Valley" ─► Gemini extracts landmark text
        │      ─► geocode vs cached landmark list ─► tool report_fire (pin; never invented)
        ▼
 Q2 "Which way is the smoke from you?" ─► "north" ─► tool add_bearing (bonus only)
        ▼
 Q3 "Is anyone with you? Can everyone walk?" ─► "Grandma can't walk"
        │      ─► tool set_needs (immobile = priority flag, raises level)
        ▼
 (optional, smartphone + not driving) camera link /sos/cam/{id} ─► frame + compass
        ▼
 Agent gives ONE safe direction only from the route result: "Go east on Genesee to RIMAC."
        │   (never a downwind shelter; geo.py refuses it; no route → "stay where you are safe")
        │   ETA spoken only if a unit was dispatched and the route gave an ETA
        ▼
 Dispatcher may JUMP IN ─► caller hears "Connecting you to a dispatcher" ─► human talks
        │
        ▼
 Call drops ─► AGNI calls back automatically within 30 s with context (C9 callback path)

 WARNING CALL (only after a human confirms; only addresses in ring + downwind zone):
 Phone rings "AGNI Alert, San Diego County" ─► slow, short, their language, direction + shelter
 ─► "Press 1 or say help if you need help getting out" ─► rescue.requested pin ─► "Help is noted."
```

### 4.2 Dispatcher (web console)

```
 Open /console?token=… ─► S0 Calm: "28 cameras live · Wind NW 14 mph"
        │  (first run: practice card, Neon branch practice-<id>)
        ▼
 Fire list: rows appear per FIRE; "NEW n" badge; posts show as gray "unverified" rows
        ▼
 Open a row: why_line + live call transcript, language chip, landmark pin
        ▼
 More callers ─► "Suggested merge" on the row ─► [M] accept  /  [N] keep apart  /  [U] undo
        ▼
 Cameras near the pin CONFIRM (or say "Can't tell"); bearings ellipse if available
        ▼
 S14/v2-6 Evidence stack ─► [Confirm fire]  or  [Not a fire]          ◄── HUMAN
        ▼
 v2-8 Route: Engine 42, 7 min, avoids closure; "Not routing to Torrey Pines HS (downwind)"
        ▼
 [Approve dispatch ⏎] ─► S6 Engine 42 en route, Uno buzzing          ◄── HUMAN
        ▼
 [JUMP IN] ─► summary read first ─► talk ─► [Hand back to AGNI]       ◄── HUMAN
        ▼
 S9 Spread ring "30-min estimate" ─► [Send warning to N homes]        ◄── HUMAN
        ▼
 S10 Calls ringing; each "pressed 1 / said help" becomes a rescue pin
        ▼
 S12 After-action draft ─► dispatcher edits + [Sign and close]        ◄── HUMAN
```

### 4.3 Keyboard map (console)

| Key | Action | Guard |
|---|---|---|
| Enter | Primary button on the card (Confirm / Approve / Send) | Disabled until evidence or route is ready |
| M / N | Accept suggested merge / keep apart | Only on a row with a suggestion |
| J | JUMP IN / Hand back | Only during a live call |
| U | Undo merge (one click or key) | Any accepted merge |
| Esc | Close card | — |
| Shift+O | Open /ops (hidden) | Operator token required |

## 5. Repo layout

```
agni/
├── README.md                  # one-liner, run steps, demo GIF
├── .env.example               # names only (Section 6)
├── Makefile                   # make dev | make seed | make eval | make demo
├── backend/
│   ├── requirements.txt       # fastapi uvicorn httpx pydantic google-genai psycopg[binary]
│   │                          # numpy shapely pyserial python-dotenv playwright
│   ├── app/
│   │   ├── main.py            # FastAPI app, CORS, mounts routers, starts pollers
│   │   ├── config.py          # reads env vars, feature flags (USE_NEON, DEMO_REPLAY)
│   │   ├── db.py              # SQLite or Postgres connection, migrations runner
│   │   ├── auth.py            # operator token check, ElevenLabs tool secret check
│   │   ├── bus.py             # emit(type, incident_id, data) → events table + SSE fan-out
│   │   ├── models.py          # pydantic models for events and requests
│   │   ├── routers/
│   │   │   ├── events.py      # GET /api/events (SSE), GET /api/state
│   │   │   ├── tools.py       # POST /api/tools/* (ElevenLabs webhook tools)
│   │   │   ├── calls.py       # post-call webhook, transcript ingest
│   │   │   ├── incidents.py   # list/get, confirm, reject, merge accept/keep-apart/undo, close/sign
│   │   │   ├── signals.py     # GET signals, POST refresh (ops only)
│   │   │   ├── cameras.py     # GET cameras near point, POST triage
│   │   │   ├── sos.py         # /sos/cam/{id} page + POST frame + bearing
│   │   │   ├── dispatch.py    # GET route options, POST dispatch (Idempotency-Key)
│   │   │   ├── handoff.py     # POST jump-in, POST hand-back
│   │   │   ├── warnings.py    # POST /api/warnings/{incident_id}, GET status
│   │   │   ├── report.py      # GET draft, POST sign
│   │   │   ├── settings.py    # overflow_enabled, region, units CSV upload (admin)
│   │   │   └── ops.py         # replay, surge, grow ring, reset, overflow toggle
│   │   ├── services/
│   │   │   ├── brightdata.py  # SERP, Scraper API (Reddit, X), Browser API (QuickMap, shelters)
│   │   │   ├── gemini.py      # all Gemini calls, schemas, timeouts, cache
│   │   │   ├── eleven.py      # outbound + batch calls, agent config helpers
│   │   │   ├── merge.py       # duplicate-call merge + undo
│   │   │   ├── swarm.py       # from Ares (bearings → estimate)
│   │   │   ├── feeds.py       # from Ares (wind, cameras, fires, hotspots)
│   │   │   ├── geo.py         # from Ares (safe destination, downwind refusal)
│   │   │   ├── evidence.py    # builds the evidence stack
│   │   │   ├── routing.py     # nearest unit, ORS/OSRM, straight-line fallback
│   │   │   ├── spread.py      # NumPy wind spread ring
│   │   │   ├── serial_bridge.py # pyserial → Arduino
│   │   │   ├── surge.py       # 75-call replay generator
│   │   │   ├── neon.py        # branch create/reset via Neon API
│   │   │   ├── clock.py       # measured timestamps (first signal → human dispatch)
│   │   │   ├── landmarks.py   # landmark list (Bright Data, cached) + geocode match
│   │   │   └── tiger.py       # stretch, only if surge counter needs it
│   │   └── pollers.py         # asyncio timers for Bright Data, NWS, FIRMS, NIFC, cameras
│   ├── migrations/
│   │   ├── 001_core.sql       # Postgres + PostGIS (Section 7)
│   │   └── 001_core.sqlite.sql
│   ├── ml/                    # Andrej (Section 11)
│   │   ├── triage.py  posts.py  spread.py
│   │   └── eval/ frames.csv posts.csv merges.csv run_eval.py eval.json
│   ├── sim/                   # Staff: surge.py (75 calls) → sim.json; Andrej: harness.py (10 personas) → eval.json
│   ├── seed/                  # units.json, shelters.json, cached_signals.json, replay/*.json
│   └── tests/                 # test_merge.py test_routing.py test_events.py test_tools.py
├── frontend/                  # static, served by FastAPI at /console
│   ├── console.html  console.css  console.js   # Leaflet map, cards, SSE client
│   ├── js/ map.js cards.js camera_wall.js evidence.js events.js ops.js
│   ├── sos.html  sos.js       # caller camera page (getUserMedia + DeviceOrientation)
│   ├── ops.html               # hidden panel
│   ├── chief.html             # read-only tablet map (now vs 30 min + closures)
│   └── setup.html             # county admin: units CSV, region, number, practice run
├── hardware/uno_station/uno_station.ino
└── agent/                     # ElevenLabs agent prompt + tool JSON (Section 12)
    ├── system_prompt.md
    └── tools/*.json
```

## 6. Config: .env.example and credits

Names only. Never commit values. Keys arrive in a 1:1 chat or a password manager, not in a group room.

```
# core
OPERATOR_TOKEN=
PUBLIC_BASE_URL=
DATABASE_URL=                 # sqlite:///agni.db now; Neon postgres URL tonight
USE_NEON=
OVERFLOW_ENABLED=             # 1 = AGNI may answer forwarded overflow calls
DEMO_REPLAY=                  # 1 = smoke frames come from labeled replay files
# neon
NEON_API_KEY=
NEON_PROJECT_ID=
NEON_MAIN_BRANCH_ID=
NEON_SURGE_BRANCH_ID=
# elevenlabs
ELEVENLABS_API_KEY=
ELEVENLABS_AGENT_ID=
ELEVENLABS_WARN_AGENT_ID=
ELEVENLABS_PHONE_NUMBER_ID=
ELEVENLABS_TOOL_SECRET=       # shared header value on webhook tools
ELEVENLABS_WEBHOOK_SECRET=    # post-call webhook HMAC
DISPATCHER_PHONE_NUMBER=      # JUMP IN target
# twilio (number imported into ElevenLabs)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
# gemini
GEMINI_API_KEY=
GEMINI_MODEL=                 # gemini-2.5-flash
# bright data
BRIGHTDATA_API_TOKEN=
BRIGHTDATA_SERP_ZONE=
BRIGHTDATA_BROWSER_WS=        # wss://…@brd.superproxy.io:9222 (Browser API zone)
BRIGHTDATA_REDDIT_DATASET_ID=
BRIGHTDATA_X_DATASET_ID=
BRIGHTDATA_LANDMARKS_SOURCE=   # which cached landmark list to load
# feeds and routing
FIRMS_MAP_KEY=
ORS_API_KEY=
OSRM_BASE_URL=                # https://router.project-osrm.org
NWS_USER_AGENT=               # "agni-sandhacks (contact email)" – NWS asks for one
# hardware
SERIAL_PORT=                  # /dev/ttyACM0 or COM3
SERIAL_BAUD=                  # 9600
# stretch
TIGER_DATABASE_URL=           # only if the surge counter needs it
# optional hosting
VULTR_API_KEY=
```

### Credits and signup

Codes below were posted by Bijin in the team room (relayed by Andrej, Elon, Rannvijay). They are event promo codes, not keys. Slots marked yellow still need Bijin's exact link.

| Sponsor | Hackathon credit (from Bijin) | Public signup | Docs home |
|---|---|---|---|
| ElevenLabs | 1 free month Creator plan. Claim in the SanD Hacks Discord. Bijin's credit link: ____ | [https://elevenlabs.io/app/sign-up](https://elevenlabs.io/app/sign-up) | [https://elevenlabs.io/docs/eleven-agents/overview](https://elevenlabs.io/docs/eleven-agents/overview) |
| Gemini (MLH) | Free tier key at [https://aistudio.google.com/api-keys](https://aistudio.google.com/api-keys) | [https://aistudio.google.com/api-keys](https://aistudio.google.com/api-keys) | [https://ai.google.dev/gemini-api/docs/quickstart](https://ai.google.dev/gemini-api/docs/quickstart) |
| Bright Data | Promo code `sandhacks26` = $100 credit. Impact / Tech for Good prizes $1,000 / $750 / $500. Bijin's credit link: ____ | [https://brightdata.com/cp/start](https://brightdata.com/cp/start) | [https://docs.brightdata.com/introduction](https://docs.brightdata.com/introduction) |
| Neon | Promo code `hackonneon`. Bijin's credit link: ____ | [https://neon.com/signup](https://neon.com/signup) | [https://neon.com/docs/introduction/branching](https://neon.com/docs/introduction/branching) |
| Tiger Data (only if needed) | None shared. Bijin's credit link: ____ | [https://console.cloud.timescale.com/signup](https://console.cloud.timescale.com/signup) | [https://docs.tigerdata.com/use-timescale/latest/hypertables/](https://docs.tigerdata.com/use-timescale/latest/hypertables/) |
| Vultr | None shared. Bijin's credit link: ____ | [https://www.vultr.com/register/](https://www.vultr.com/register/) [site blocks bots; open in browser] | [https://docs.vultr.com/](https://docs.vultr.com/) |
| Twilio | Trial number (needed for phone calls). Bijin's credit link: ____ | [https://www.twilio.com/try-twilio](https://www.twilio.com/try-twilio) | [https://www.twilio.com/docs/voice](https://www.twilio.com/docs/voice) |
| NASA FIRMS | Free MAP_KEY | [https://firms.modaps.eosdis.nasa.gov/api/map_key/](https://firms.modaps.eosdis.nasa.gov/api/map_key/) | [https://firms.modaps.eosdis.nasa.gov/api/area/](https://firms.modaps.eosdis.nasa.gov/api/area/) |
| OpenRouteService | Free key | [https://openrouteservice.org/dev/#/signup](https://openrouteservice.org/dev/#/signup) | [https://giscience.github.io/openrouteservice/api-reference/](https://giscience.github.io/openrouteservice/api-reference/) |

## 7. Database schema

One schema. Postgres + PostGIS on Neon is the target. SQLite works today with the notes at the end. All times are UTC `timestamptz`; the console shows Pacific time.

```
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE incidents (
  id            TEXT PRIMARY KEY,                -- 'inc_' + short id
  status        TEXT NOT NULL DEFAULT 'possible',-- possible|confirmed|dispatched|closed|rejected
  level         INT  NOT NULL DEFAULT 3,         -- 1 critical … 5 low
  kind          TEXT NOT NULL DEFAULT 'fire',
  title         TEXT,
  location      GEOGRAPHY(Point,4326),           -- best point (confirmed or estimate)
  location_src  TEXT,                            -- caller|estimate|camera|human
  estimate_m    REAL,                            -- ellipse radius, meters
  confirmed_by  TEXT, confirmed_at TIMESTAMPTZ,
  merged_into   TEXT REFERENCES incidents(id),
  why_line      TEXT,                            -- '4 callers · cam K-12 smoke · wind NE 25 mph'
  immobile      BOOLEAN DEFAULT false,           -- someone can't move → priority
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at     TIMESTAMPTZ
);
CREATE INDEX ON incidents USING GIST (location);

CREATE TABLE signals (                           -- Bright Data crowd posts (cached)
  id          TEXT PRIMARY KEY,                  -- sha1(url)
  source      TEXT NOT NULL,                     -- serp|reddit|x
  url         TEXT NOT NULL, text TEXT NOT NULL,
  posted_at   TIMESTAMPTZ, scraped_at TIMESTAMPTZ NOT NULL,
  about_fire  BOOLEAN, place_text TEXT, confidence TEXT,  -- Gemini
  location    GEOGRAPHY(Point,4326),             -- geocoded place_text (never from Gemini)
  incident_id TEXT REFERENCES incidents(id)
);
CREATE INDEX ON signals USING GIST (location);

CREATE TABLE hazards (                           -- road closures, perimeters (cached)
  id TEXT PRIMARY KEY, source TEXT NOT NULL,     -- caltrans_quickmap|nifc|manual
  kind TEXT NOT NULL,                            -- road_closure|fire_perimeter
  title TEXT, geom GEOGRAPHY(Geometry,4326) NOT NULL,
  observed_at TIMESTAMPTZ, scraped_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX ON hazards USING GIST (geom);

CREATE TABLE shelters (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT DEFAULT 'R',   -- R refuge, H hospital
  location GEOGRAPHY(Point,4326) NOT NULL,
  capacity INT, occupancy INT, status TEXT,     -- open|full|closed|unknown
  source_url TEXT, scraped_at TIMESTAMPTZ
);

CREATE TABLE calls (
  id TEXT PRIMARY KEY,                           -- ElevenLabs conversation_id
  incident_id TEXT REFERENCES incidents(id),
  direction TEXT NOT NULL,                       -- inbound|outbound_warning|callback
  phone_hash TEXT,                               -- sha256(number+salt), never raw on screen
  phone_last4 TEXT, language TEXT,
  location GEOGRAPHY(Point,4326), address_text TEXT,
  needs JSONB DEFAULT '{}',                      -- {"mobility":true,"people":2}
  state TEXT DEFAULT 'live',                     -- live|human|ended|dropped
  started_at TIMESTAMPTZ DEFAULT now(), ended_at TIMESTAMPTZ
);

CREATE TABLE transcripts (
  id BIGSERIAL PRIMARY KEY, call_id TEXT REFERENCES calls(id),
  speaker TEXT, text TEXT, lang TEXT, ts TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE bearings (
  id BIGSERIAL PRIMARY KEY, call_id TEXT REFERENCES calls(id), incident_id TEXT,
  origin GEOGRAPHY(Point,4326) NOT NULL, bearing_deg REAL NOT NULL,
  source TEXT,                                   -- compass|words
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE cameras (
  id TEXT PRIMARY KEY, name TEXT, site TEXT, image_url TEXT,
  location GEOGRAPHY(Point,4326), online TEXT, updated_at TIMESTAMPTZ
);

CREATE TABLE triage_results (
  id BIGSERIAL PRIMARY KEY, incident_id TEXT, camera_id TEXT,
  frame_source TEXT,                             -- live|replay|caller
  captured_at TIMESTAMPTZ, label TEXT,           -- smoke|no_smoke|cant_tell
  flames_visible BOOLEAN, box JSONB, reason TEXT, latency_ms INT,
  UNIQUE (camera_id, captured_at)
);

CREATE TABLE evidence (
  incident_id TEXT REFERENCES incidents(id), source TEXT,  -- callers|cameras|wind|firms|nifc
  state TEXT,                                    -- agree|empty|disagree|error
  detail TEXT, age_s INT, updated_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (incident_id, source)
);

CREATE TABLE units (
  id TEXT PRIMARY KEY, callsign TEXT, type TEXT, station TEXT,
  location GEOGRAPHY(Point,4326), status TEXT DEFAULT 'available'
);

CREATE TABLE dispatches (
  id BIGSERIAL PRIMARY KEY, incident_id TEXT, unit_id TEXT,
  idempotency_key TEXT UNIQUE NOT NULL, approved_by TEXT,
  route_geojson JSONB, route_kind TEXT,          -- road|estimate
  eta_s INT, created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE merges (
  id BIGSERIAL PRIMARY KEY, kept_id TEXT, merged_id TEXT, call_id TEXT,
  distance_m REAL, dt_s INT, gemini_same BOOLEAN, gemini_reason TEXT,
  state TEXT NOT NULL DEFAULT 'suggested',      -- suggested|accepted|kept_apart|undone
  decided_by TEXT, undone_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE rings (
  id BIGSERIAL PRIMARY KEY, incident_id TEXT, minutes INT,
  geom GEOGRAPHY(Polygon,4326), wind JSONB, homes_est INT, created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE warnings (
  id BIGSERIAL PRIMARY KEY, incident_id TEXT, approved_by TEXT,
  batch_id TEXT, recipients INT, languages TEXT[], status TEXT,
  idempotency_key TEXT UNIQUE, created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE rescues (
  id BIGSERIAL PRIMARY KEY, incident_id TEXT, call_id TEXT,
  location GEOGRAPHY(Point,4326), digits TEXT, created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE decisions (                         -- audit log: who decided what (feeds report)
  id BIGSERIAL PRIMARY KEY, incident_id TEXT, actor TEXT,  -- human:<name>|agent|system
  action TEXT, detail JSONB, ts TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE landmarks (                         -- cached ahead (Bright Data + OSM), used to geocode speech
  id TEXT PRIMARY KEY, name TEXT NOT NULL, aliases TEXT[], kind TEXT,  -- store|school|park|church|road
  location GEOGRAPHY(Point,4326) NOT NULL, source TEXT, scraped_at TIMESTAMPTZ
);
CREATE INDEX ON landmarks USING GIST (location);

CREATE TABLE settings (                          -- one row
  id INT PRIMARY KEY DEFAULT 1, overflow_enabled BOOLEAN NOT NULL DEFAULT false,
  region GEOGRAPHY(Polygon,4326), overflow_number TEXT, updated_by TEXT, updated_at TIMESTAMPTZ
);

CREATE TABLE user_seen (                         -- for the "new since you looked" badge
  operator TEXT, incident_id TEXT, last_seen_seq BIGINT, PRIMARY KEY (operator, incident_id)
);

CREATE TABLE events (                            -- the SSE log; seq is global
  seq BIGSERIAL PRIMARY KEY, type TEXT NOT NULL, incident_id TEXT,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(), data JSONB NOT NULL
);
CREATE INDEX ON events (seq);

CREATE TABLE reports (
  incident_id TEXT PRIMARY KEY, draft TEXT, final TEXT, signed_by TEXT,
  signed_at TIMESTAMPTZ, clock JSONB
);
```

Nearest units in PostGIS.
```
SELECT id, callsign, ST_Distance(location, ST_MakePoint(:lon,:lat)::geography) AS m
FROM units WHERE status = 'available'
ORDER BY location <-> ST_MakePoint(:lon,:lat)::geography LIMIT 3;
```

SQLite notes.
Use
TEXT
for ids,
REAL lat, REAL lon
columns instead of
GEOGRAPHY
,
TEXT
JSON instead of
JSONB
,
INTEGER PRIMARY KEY AUTOINCREMENT
for
seq
, ISO strings for times. Distance and nearest-unit run in Python (haversine from
geo.py
). Keep all SQL behind
db.py
functions so the switch to Neon is one env var (
USE_NEON=1
).

## 8. REST API

All console routes need `Authorization: Bearer $OPERATOR_TOKEN`. Tool routes need header `X-Agni-Tool-Secret`. Responses are JSON. Every write emits an event.

| Method + path | Who calls | Body / query | Returns | Emits |
|---|---|---|---|---|
| GET /api/events?since=seq | console | since (int) | SSE stream | — |
| GET /api/state | console | — | incidents, units, hazards, shelters, last seq | — |
| GET /api/signals?since_min=60 | console | — | signals list | — |
| POST /api/tools/report_fire | ElevenLabs | conversation_id, landmark_text, what_seen, language | {incident_id, overflow, say} | call.started, incident.created \| incident.merge_suggested |
| POST /api/tools/add_bearing | ElevenLabs / sos page | conversation_id, direction_words or bearing_deg | {estimate?, say} | bearing.added, estimate.updated |
| POST /api/tools/set_needs | ElevenLabs | conversation_id, mobility, people, notes | {say} | triage.result |
| POST /api/tools/send_cam_link | ElevenLabs | conversation_id | {say} | — |
| POST /api/tools/get_guidance | ElevenLabs | conversation_id | {say, shelter, eta_s} | — |
| POST /api/tools/request_rescue | ElevenLabs (warning agent) | conversation_id, digits | {say} | rescue.requested |
| POST /api/calls/transcript | ElevenLabs / bridge | conversation_id, speaker, text, lang | ok | call.transcript |
| POST /api/calls/postcall | ElevenLabs webhook | post-call payload (HMAC) | ok | — |
| GET /sos/cam/{incident_id} | caller phone | t (signed short token) | HTML page | — |
| POST /api/sos/{incident_id}/frame | caller phone | JPEG multipart | {label} | triage.result |
| POST /api/sos/{incident_id}/bearing | caller phone | lat, lon, heading_deg | ok | bearing.added |
| GET /api/cameras?lat&lon&n=3 | console | — | nearest cams | cameras.selected |
| POST /api/incidents/{id}/triage-cameras | console / auto | — | verdicts | triage.result, evidence.updated |
| POST /api/incidents/{id}/confirm | console (human) | note | incident | evidence.updated, triage.result |
| POST /api/incidents/{id}/reject | console (human) | reason | incident | evidence.updated |
| POST /api/merges/{merge_id}/accept | console (human, key M) | — | incident | incident.merged |
| POST /api/merges/{merge_id}/keep-apart | console (human, key N) | — | incidents | incident.created |
| POST /api/merges/{merge_id}/undo | console (human, one click) | — | incidents | incident.created |
| POST /api/incidents/{id}/seen | console | seq | ok | — |
| GET /api/settings · PUT /api/settings | admin / ops | overflow_enabled, region, overflow_number | settings | — |
| POST /api/admin/units.csv | admin | CSV: id,callsign,type,station,lat,lon | count | — |
| GET /chief | battalion chief tablet | token | read-only map | — |
| GET /api/incidents/{id}/route | console | — | units[3], route, shelter, refused[] | route.ready |
| POST /api/incidents/{id}/dispatch | console (human) | unit_id; header Idempotency-Key | dispatch | unit.dispatched |
| POST /api/calls/{call_id}/jump-in | console (human) | — | {summary} | handoff.started |
| POST /api/calls/{call_id}/hand-back | console (human) | — | ok | handoff.ended |
| POST /api/incidents/{id}/ring | console / timer | minutes=30 | ring | ring.updated |
| POST /api/warnings/{incident_id} | console (human) | languages[], message_key; Idempotency-Key | {batch_id, recipients} | warning.sent |
| GET /api/incidents/{id}/report | console | — | draft + clock | — |
| POST /api/incidents/{id}/close | console (human) | final_text, signed_by | report | incident.closed |
| POST /api/ops/replay-signals | ops | — | ok | signal.new… |
| POST /api/ops/surge | ops | n=75, seconds=90 | ok | surge.stats… |
| POST /api/ops/grow-ring | ops | minutes | ok | ring.updated |
| POST /api/ops/reset | ops | branch=main\|surge-sim | ok | (stream reset marker) |
| POST /api/ops/overflow | ops | enabled: bool | settings | — |
| GET /api/proof | console / slide | — | sim.json + eval.json, or nulls | — |
| GET /health | anyone | — | {ok, db, serial, feeds ages} | — |

## 9. Event contract (SSE)

**Transport.** `GET /api/events?since=<seq>`, `text/event-stream`. Each message has `id: <seq>`, `event: <type>`, `data: <json>`. The browser's EventSource sends `Last-Event-ID` on reconnect; the server replays every row with `seq > since` from the `events` table, then streams live. Heartbeat comment every 15 s.

**Envelope.** Every event: `{"type","incident_id","seq","ts","data"}`. `incident_id` is `null` only for global events (`surge.stats`, `signal.new` before a match).

**Count.** 21 events. The original plan had 19; v1 added `rescue.requested`; v2 adds `incident.merge_suggested` because merge now only suggests. `incident.merged` now means a human accepted the suggestion.

**Example values** below show format only. They are not results and must never be shown as results.

**Budgets.** transcript on screen < 1 s · tool call reply < 800 ms · route < 2 s · Gemini 5 s.

```
# backend/app/bus.py
import asyncio, json
from datetime import datetime, timezone
subscribers: set[asyncio.Queue] = set()

def emit(type_, incident_id, data):
    ts = datetime.now(timezone.utc).isoformat()
    seq = db.insert_event(type_, incident_id, ts, data)   # returns new seq
    ev = {"type": type_, "incident_id": incident_id, "seq": seq, "ts": ts, "data": data}
    for q in list(subscribers):
        q.put_nowait(ev)
    return ev

# backend/app/routers/events.py  (FastAPI >= 0.135 has fastapi.sse; sse-starlette also works)
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
router = APIRouter()

def fmt(ev):
    return f"id: {ev['seq']}\nevent: {ev['type']}\ndata: {json.dumps(ev)}\n\n"

@router.get("/api/events")
async def events(request: Request, since: int = 0):
    last = int(request.headers.get("last-event-id", since))
    q = asyncio.Queue(); bus.subscribers.add(q)
    async def gen():
        try:
            for ev in db.events_after(last):
                yield fmt(ev)
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), 15)
                    if ev["seq"] > last:
                        yield fmt(ev)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            bus.subscribers.discard(q)
    return StreamingResponse(gen(), media_type="text/event-stream")
```

```
// frontend/js/events.js
let last = +localStorage.agniSeq || 0;
function connect() {
  const es = new EventSource(`/api/events?since=${last}&token=${TOKEN}`);
  es.onmessage = null;
  TYPES.forEach(t => es.addEventListener(t, e => {
    const ev = JSON.parse(e.data);
    if (ev.seq <= last) return;            // dedupe on replay
    last = ev.seq; localStorage.agniSeq = last;
    render(ev);                            // cards.js / map.js switch on ev.type
  }));
  es.onerror = () => showBanner("Reconnecting… catching up from " + last);
}
```

| # | Event | Emitted by | Console effect |
|---|---|---|---|
| 1 | `signal.new` | Bright Data poller after Gemini says about_fire | Dashed pin, card S1 |
| 2 | `call.started` | tool report_fire (first call per conversation) | Call line under its fire row |
| 3 | `call.transcript` | transcript ingest | Streaming lines in card |
| 4 | `incident.created` | merge.py when no match, keep-apart, or undo | New fire row |
| 5 | `incident.merge_suggested` | merge.py on match (never auto-joins) | Row shows “Suggested merge” + M / N keys |
| 6 | `incident.merged` | POST accept (human, key M) | Rows fold; Undo link |
| 7 | `triage.result` | camera verdict, caller frame, needs, or human confirm | Level chip, camera tile |
| 8 | `route.ready` | routing.py | Route line + unit card S5 / v2-8 |
| 9 | `unit.dispatched` | POST dispatch (human) | Unit moves, Uno buzz chip S6 |
| 10 | `handoff.started` | POST jump-in (human) | Card S7 ‘You are on the call’ |
| 11 | `handoff.ended` | POST hand-back or call end | Card returns to agent view |
| 12 | `ring.updated` | spread.py | Orange ring S9 ‘30-min estimate’ |
| 13 | `warning.sent` | POST /api/warnings (human) | Warning list S10 |
| 14 | `surge.stats` | surge.py every 1 s | Banner S11 |
| 15 | `incident.closed` | POST close (human signs) | Report S12 |
| 16 | `bearing.added` | add_bearing tool or sos compass | White ray from caller S13 |
| 17 | `estimate.updated` | swarm.py after ≥2 bearings | Dashed ellipse ‘estimate ± 450 m’ |
| 18 | `cameras.selected` | cameras near estimate | Camera wall + view cones v2-5 |
| 19 | `satellite.result` | FIRMS check | Evidence row (empty dot + reason) |
| 20 | `evidence.updated` | evidence.py or human confirm | Evidence stack S14 / v2-6 |
| 21 | `rescue.requested` | request_rescue tool (DTMF 1) | Red rescue pin + count |

### Example payloads

Shown as the full envelope for the first one; the rest show `data` only.

```
{
  "type": "signal.new",
  "incident_id": null,
  "seq": 101,
  "ts": "2026-11-15T20:12:05.120Z",
  "data": {
    "signal_id": "sig_9f2c",
    "source": "reddit",
    "text": "Anyone else see smoke off Carmel Valley?",
    "url": "https://www.reddit.com/r/sandiego/...",
    "posted_at": "2026-11-15T20:12:00Z",
    "place_text": "Carmel Valley",
    "lat": 32.93,
    "lon": -117.22,
    "confidence": "medium",
    "label": "unverified"
  }
}
```

#### call.started

```
{"call_id": "conv_01J...", "direction": "inbound_overflow", "language": "en", "phone_last4": "4471", "lat": 32.915, "lon": -117.236, "landmark_text": "behind the Vons on Carmel Valley Rd", "location_src": "landmark"}
```

#### call.transcript

```
{"call_id": "conv_01J...", "speaker": "caller", "text": "Mi abuela no puede caminar.", "lang": "es", "final": true}
```

#### incident.created

```
{"status": "possible", "level": 3, "lat": 32.915, "lon": -117.236, "location_src": "landmark", "landmark": "Vons, Carmel Valley Rd", "title": "Possible fire, Torrey Pines", "why_line": "1 caller · no camera yet · wind NE 25 mph", "immobile": false, "reporters": {"calls": 1, "signals": 0}}
```

#### incident.merge_suggested

```
{"merge_id": 42, "kept_id": "inc_a1", "merged_id": "inc_b7", "call_id": "conv_02K...", "distance_m": 420, "dt_s": 180, "gemini_same": true, "confidence": "high", "reason": "Both describe smoke behind Torrey Pines HS"}
```

#### incident.merged

```
{"merge_id": 42, "kept_id": "inc_a1", "merged_id": "inc_b7", "decided_by": "dispatcher:bijin", "why_line": "2 callers · cam K-12 smoke · wind NE 25 mph"}
```

#### triage.result

```
{"source": "camera", "camera_id": "cam_tp1", "frame_source": "live", "label": "no_smoke", "flames_visible": false, "box": null, "reason": "Clear hillside, no plume", "suggested_level": null, "latency_ms": 2310}
```

#### route.ready

```
{"unit_id": "E42", "callsign": "Engine 42", "eta_s": 420, "route_kind": "road", "geojson": {"type": "LineString", "coordinates": [[-117.2, 32.95], [-117.23, 32.92]]}, "avoids": ["Carmel Valley Rd (Caltrans)"], "shelter": {"id": "rimac", "name": "RIMAC", "status": "open"}, "refused": [{"name": "Torrey Pines HS", "why": "1.2 km downwind"}]}
```

#### unit.dispatched

```
{"dispatch_id": 7, "unit_id": "E42", "approved_by": "dispatcher:bijin", "idempotency_key": "7b1c-...", "serial": "sent"}
```

#### handoff.started

```
{"call_id": "conv_02K...", "summary": "Spanish speaker near the golf course. Smoke to the north. Grandmother can't walk. Engine 42 assigned.", "to": "dispatcher", "mode": "warm_transfer"}
```

#### handoff.ended

```
{"call_id": "conv_02K...", "resumed_by": "agent", "duration_s": 38, "mode": "callback"}
```

#### ring.updated

```
{"minutes": 30, "label": "estimate", "wind": {"from_deg": 315, "kph": 22, "station": "KNKX", "age_s": 540}, "geojson": {"type": "Polygon", "coordinates": [["..."]]}, "homes_est": 3, "homes_label": "approx."}
```

#### warning.sent

```
{"batch_id": "btch_...", "recipients": 3, "targeting": "ring+downwind", "languages": ["en", "es"], "approved_by": "dispatcher:bijin", "status": "in_progress"}
```

#### surge.stats

```
{"calls": 12, "fires": 2, "duplicate_units_sent": 0, "false_merges": 0, "branch": "surge-sim", "elapsed_s": 15, "sim": true}
```

#### incident.closed

```
{"report": "Vegetation fire, Torrey Pines. First public signal 20:12 …", "signed_by": "dispatcher:bijin", "clock": {"first_signal": "20:12:04Z", "first_call": "20:13:11Z", "human_confirm": "20:13:24Z", "human_dispatch": "20:13:56Z", "signal_to_dispatch_s": 112}}
```

#### bearing.added

```
{"call_id": "conv_01J...", "lat": 32.91, "lon": -117.25, "bearing_deg": 45, "source": "words", "words": "northeast"}
```

#### estimate.updated

```
{"lat": 32.928, "lon": -117.231, "radius_m": 450, "support": 2, "label": "estimate"}
```

#### cameras.selected

```
{"cameras": [{"id": "cam_tp1", "name": "Torrey Pines", "lat": 32.955, "lon": -117.255, "km": 2.1, "image_age_s": 42}]}
```

#### satellite.result

```
{"source": "firms", "detections": 0, "reason": "No detection yet; satellite data can lag hours", "checked_at": "2026-11-15T20:13:30Z"}
```

#### evidence.updated

```
{"rows": [{"source": "callers", "state": "agree", "detail": "2 bearings cross"}, {"source": "cameras", "state": "agree", "detail": "2 of 3 see smoke"}, {"source": "posts", "state": "empty", "detail": "no public posts in last hour"}, {"source": "wind", "state": "agree", "detail": "NE 25 mph"}, {"source": "firms", "state": "empty", "detail": "no heat yet, normal delay"}, {"source": "nifc", "state": "empty", "detail": "none mapped yet"}], "status": "possible", "confirmed_by": null, "why_line": "2 callers · cam K-12 smoke · wind NE 25 mph", "colors": "agree=green, unknown=gray, disagree=red"}
```

#### rescue.requested

```
{"call_id": "conv_w_88", "phone_last4": "9022", "lat": 32.905, "lon": -117.21, "digits": "1", "said_help": false, "language": "es"}
```

## 10. Components

16 components. C1–C14 are the demo. C15 is stretch. C16 is optional hosting. Screens: “v1 Sn” = `/workspace/agni_proto/index.html#s=n`; “v2 n” = Elon's `/workspace/agni-proto/index.html` step n.

| # | Component | Sponsor | Prototype state |
|---|---|---|---|
| C1 | Crowd signals | Bright Data, Gemini | v2 2 (v1 S1) |
| C2 | Voice intake | ElevenLabs | v1 S2, v2 3 |
| C3 | Caller location: landmarks first, bearings as bonus | Gemini, Bright Data | v2 4 (v1 S13) |
| C4 | Camera wall: cameras confirm reports | Gemini | v2 5 |
| C5 | Evidence stack + Confirm | — | v2 6 (v1 S14) |
| C6 | Incident store + merge suggestions | Neon, Gemini | v1 S8 |
| C7 | Nearest unit + routing + safe shelter | Bright Data (closures, shelters) | v2 8 (v1 S5) |
| C8 | Dispatch + Arduino | — | v1 S6, v2 9 |
| C9 | JUMP IN | ElevenLabs, Gemini | v2 10 (v1 S7) |
| C10 | Spread ring | — | v2 11 (v1 S9) |
| C11 | Reverse 911 warning | ElevenLabs | v1 S10, v2 12 |
| C12 | Surge replay | Neon | v1 S11 |
| C13 | After-action report + audit trail | Gemini, Neon | v2 13 (v1 S12) |
| C14 | /ops panel + overflow toggle | Neon | none (wireframe) |
| C15 | Stretch: Tiger counter (only if needed) | Tiger Data | — |
| C16 | Optional hosting | Vultr | — |

## C1. Crowd signals (Bright Data → signals → Gemini)

Owner: Staff (poller) · Andrej (classifier)

(image: )

Prototype v2 · step 2 · Signal card “Possible smoke, Torrey Pines”, chips “Reddit, X via Bright Data” and “Confidence: medium”. Dashed pins on map.
Numbers in mocks are placeholders, not measurements.

#### (a) UI

- Left card: label **Signal, unverified**; title “Possible smoke, <place>”; chips for source and confidence; up to 3 quoted posts with age (“12 min ago”), each linking to its URL.
- Footer line, always: “Crowd signals can raise priority. They never dispatch.”
- Map: grey dashed pins. No red. Pins fade after 60 min.
- Top pill shows freshness: “Bright Data · updated 2 min ago”. If older than 15 min: amber “stale 23 min”.
- **Empty:** no card; pill reads “No public reports in the last hour”. **Error:** pill “Crowd feed offline · using cache from 20:05”.

#### (b) Backend

- `services/brightdata.py`: `serp_last_hour(q)`, `reddit_posts(urls)`, `x_posts(query)`, `quickmap_closures()`, `shelter_capacity()`, `landmark_list(region)`.
- **New in v2: landmark list.** Before the event, pull local landmark names people actually say (grocery stores, schools, churches, parks, trailheads, gas stations) for the region, plus OpenStreetMap names, into `landmarks` with aliases (“the Vons”, “Vons Carmel Valley”). Refresh daily. C3 geocodes speech against this table.
- In the console, posts are **one line in the evidence stack** (“3 posts, last 12 min”), not a separate panel. A post-only row stays gray “unverified”.
- `pollers.py`: every 5 min (SERP, Reddit, X), every 10 min (QuickMap, shelters). Each run upserts into `signals`, `hazards`, `shelters` with `scraped_at`. Writes a JSON snapshot to `seed/cached_*.json` for offline demo.
- New signal rows go to `ml/posts.py` (Gemini classifier, Section 13). Only `about_fire=true` rows are geocoded (Nominatim/Photon via Ares `geo.search`) and emitted.
- Dedupe by `sha1(url)`. A signal within 1.5 km and 30 min of a possible incident attaches to it (`signals.incident_id`).
- Queries: `"smoke" OR "fire" (Torrey Pines OR "Carmel Valley" OR "La Jolla" OR "Mira Mesa")`; subreddits r/sandiego, r/UCSD.

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| `POST https://api.brightdata.com/request` body `{zone, url:"https://www.google.com/search?q=…&tbs=qdr:h&brd_json=1", format:"raw"}` (tbs=qdr:h is Google's last-hour filter; brd_json=1 asks for parsed JSON) | `BRIGHTDATA_API_TOKEN`, `BRIGHTDATA_SERP_ZONE` | [SERP first request](https://docs.brightdata.com/products/serp-api/send-your-first-request) [Parsed JSON](https://docs.brightdata.com/products/serp-api/parsed-json-results) | Promo `sandhacks26` ($100) · Bijin's credit link: ____ · [https://brightdata.com/cp/start](https://brightdata.com/cp/start) |
| `POST https://api.brightdata.com/datasets/v3/scrape?dataset_id=…` (sync) or `/datasets/v3/trigger` + snapshot (async) for Reddit and X | `BRIGHTDATA_API_TOKEN`, `BRIGHTDATA_REDDIT_DATASET_ID`, `BRIGHTDATA_X_DATASET_ID` | [Scraper API sync](https://docs.brightdata.com/api-reference/scrapers/synchronous-requests) [async](https://docs.brightdata.com/api-reference/rest-api/scraper/asynchronous-requests) [Reddit scraper](https://brightdata.com/products/web-scraper/reddit) · [X scraper](https://brightdata.com/products/web-scraper/twitter) | same |
| Browser API: Playwright `chromium.connect_over_cdp("wss://…@brd.superproxy.io:9222")` → [Caltrans QuickMap](https://quickmap.dot.ca.gov/) and shelter pages | `BRIGHTDATA_BROWSER_WS` | [Browser API](https://docs.brightdata.com/products/scraping-browser/introduction) [code examples](https://docs.brightdata.com/products/scraping-browser/code-examples) | same |
| Gemini classifier (Section 13) | `GEMINI_API_KEY` | [Structured output](https://ai.google.dev/gemini-api/docs/structured-output) | [https://aistudio.google.com/api-keys](https://aistudio.google.com/api-keys) (free tier) |

#### (d) Events

Emits
signal.new
.
Consumes
nothing. Hazards/shelters are read by C7 via tables, not events.

#### (e) Build steps + acceptance test

1. Create SERP zone and Browser API zone in the Bright Data panel; put token + zone names in `.env`.
2. Write `serp_last_hour()`; print 10 results for “smoke Torrey Pines”.
3. Pick Reddit and X scrapers in the Scraper library; copy their dataset IDs into env. Call sync `/datasets/v3/scrape`.
4. Browser API: Playwright `connect_over_cdp` to QuickMap; read closure list; store as LineStrings buffered 30 m.
5. Classifier + geocode; emit `signal.new`.
6. **Test:** run poller once with network on → ≥1 row in `signals`, ≥1 `signal.new` in `/api/events`; run with network off → console shows cached rows and “using cache from …”. A tool call during a live call never triggers a Bright Data request (assert with a mock that fails if called).

#### (f) Connects to

C6 (signals attach to incidents, raise level by at most one step), C7 (closures and shelter capacity), C13 (report lists first public signal time), C14 (replay signals).

#### (g) Time budget + fallback

Poller runs off the call path, so no live budget. Gemini classify 5 s per batch of 20.
Fallback:
cached snapshot from
seed/
, clearly labeled with its time.

#### C1 code sketch

```
# services/brightdata.py
import httpx, os, urllib.parse
TOKEN = os.environ["BRIGHTDATA_API_TOKEN"]

def serp_last_hour(q):
    url = "https://www.google.com/search?" + urllib.parse.urlencode({"q": q, "tbs": "qdr:h", "brd_json": 1})
    r = httpx.post("https://api.brightdata.com/request",
                   headers={"Authorization": f"Bearer {TOKEN}"},
                   json={"zone": os.environ["BRIGHTDATA_SERP_ZONE"], "url": url, "format": "raw"},
                   timeout=30)
    return r.json().get("organic", [])

def scrape(dataset_id, inputs):
    r = httpx.post("https://api.brightdata.com/datasets/v3/scrape",
                   params={"dataset_id": dataset_id, "format": "json"},
                   headers={"Authorization": f"Bearer {TOKEN}"}, json=inputs, timeout=90)
    return r.json()

async def quickmap_closures():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(os.environ["BRIGHTDATA_BROWSER_WS"])
        page = await b.new_page()
        await page.goto("https://quickmap.dot.ca.gov/", timeout=60000)
        # turn on the Lane Closures layer, then read the list panel; selectors found by hand
        rows = await page.locator("text=Closure").all_inner_texts()
        await b.close()
        return rows
```

## C2. Voice intake, overflow only (ElevenLabs agent + webhook tools)

Owner: Staff

(image: )

Prototype v1 · S2 · live call card. Transcript streams; language chip “Auto-switched to Spanish”; island “Live call · English → Spanish”.
Numbers in mocks are placeholders, not measurements.
(image: )

Prototype v2 · step 3 · caller 1 points the phone camera; phone inset shows the /sos/cam page with compass.
Numbers in mocks are placeholders, not measurements.

#### (a) UI

- **v2:** the call is a line under its fire row, not its own card. Opening it shows: label **Live call n**, title = first caller sentence in quotes, language chip, streaming transcript (speaker in grey, ES tag on Spanish lines), needs chips (“can't walk”, “2 people”).
- Island pill turns live (red dot) with “Live call · <lang>”. Pill also shows “Overflow ON/OFF”.
- Caller phone (/sos/cam): full-screen camera, compass arrow, big text “Help is on the way. Point your camera at the smoke.”, buttons **I'm safe to leave** and **Call me back**.
- **Empty:** “No live calls”. **Error:** “Voice line down · calls go to backup number” (Twilio forwards to `DISPATCHER_PHONE_NUMBER`). Transcript gap > 3 s shows “…listening”.

#### (b) Backend

- **Overflow only.** In a real center, calls arrive only when 911 call-takers are busy (see deployment note, §2). In the demo, judges dial the Twilio number directly. If `overflow_enabled` is off, `report_fire` returns `overflow:false` and the agent says “Please hang up and dial 911.”
- **At most 3 questions:** (1) What do you see, and where are you? (2) Which way is the smoke from you? (3) Is anyone with you, and can everyone walk? Anything else is optional.
- **Dropped call:** post-call webhook with an early end and no goodbye → wait 20 s → AGNI calls back via Twilio outbound with the incident context (`{{resume_context}}`). Emits `call.started` with `direction:"callback"`.
- **Immobile:** “can’t walk / trapped / wheelchair / oxygen” → `set_needs(mobility=true)` → `incidents.immobile=true`, level up one, red “can’t move” chip on the row.
- Inbound: Twilio number imported into ElevenLabs (native integration). The agent calls our webhook tools (Section 12) at `PUBLIC_BASE_URL/api/tools/*`.
- `routers/tools.py`: check `X-Agni-Tool-Secret`; upsert `calls` by `conversation_id`; reply in <800 ms with `{"say": "…"}` (≤ 20 words, in the caller's language).
- All slow work (merge Gemini check, camera triage, route) runs in `asyncio.create_task` after the reply. The agent gets results on its next tool call (`get_guidance`).
- Transcript: use ElevenLabs post-call webhook for the full record; for live lines, the console subscribes to the agent's conversation events through a small bridge (`services/eleven.py`) or the agent calls `log_line`; pick whichever shows lines <1 s in testing. Ares `bridge.py` already streams live transcript; reuse its structure.
- Language: enable the language detection system tool; store detected `language` on `calls`.
- Keypad: enable DTMF input (`dtmf_input_settings`) so “Press 1” works on warning calls (C11).
- /sos/cam page (optional bonus; never for landlines or drivers): `getUserMedia` rear camera, one JPEG every 3 s to `POST /api/sos/{id}/frame`; `DeviceOrientationEvent` heading to `/bearing`. Link is texted by the `send_cam_link` tool through Twilio SMS.

```
# routers/tools.py
@router.post("/api/tools/report_fire")
async def report_fire(body: ReportFire, x_agni_tool_secret: str = Header()):
    check_secret(x_agni_tool_secret)
    call = db.upsert_call(body.conversation_id, language=body.language,
                          landmark_text=body.landmark_text)
    asyncio.create_task(landmarks.locate(call))   # Gemini extract + cached list; pin comes as an event
    if call.is_new:
        bus.emit("call.started", None, call.public())
    if not settings.overflow_enabled():
        return {"overflow": False, "say": say(body.language, "dial_911")}
    inc = merge.attach_or_suggest(call)         # never auto-joins; suggests only
    return {"incident_id": inc.id, "overflow": True, "say": say(body.language, "which_way")}
```

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| Agent + tools configured in ElevenLabs dashboard or API; tools call our HTTPS endpoints | `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`, `ELEVENLABS_TOOL_SECRET` | [Agents overview](https://elevenlabs.io/docs/eleven-agents/overview) [Server/webhook tools](https://elevenlabs.io/docs/eleven-agents/customization/tools/webhook-tools) [Language detection](https://elevenlabs.io/docs/eleven-agents/customization/tools/system-tools/language-detection) [DTMF input](https://elevenlabs.io/docs/eleven-agents/customization/multimodal-input) | Creator month via Discord · Bijin's credit link: ____ · [https://elevenlabs.io/app/sign-up](https://elevenlabs.io/app/sign-up) |
| Phone: Twilio native integration | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `ELEVENLABS_PHONE_NUMBER_ID` | [Twilio native](https://elevenlabs.io/docs/eleven-agents/phone-numbers/twilio-integration/native-integration) [Twilio Voice](https://www.twilio.com/docs/voice) | [https://www.twilio.com/try-twilio](https://www.twilio.com/try-twilio) |
| Post-call webhook (HMAC) | `ELEVENLABS_WEBHOOK_SECRET` | [Post-call webhooks](https://elevenlabs.io/docs/eleven-agents/workflows/post-call-webhooks) | — |
| Caller camera + compass (browser) | — | [DeviceOrientationEvent](https://developer.mozilla.org/en-US/docs/Web/API/DeviceOrientationEvent) | — |

#### (d) Events

Emits
call.started
,
call.transcript
, and via tools
incident.created
/
incident.merged
,
bearing.added
,
triage.result
.
Consumes
route.ready
(to answer
get_guidance
),
unit.dispatched
(to speak the ETA).

#### (e) Build steps + acceptance test

1. Create agent; paste system prompt; add 6 webhook tools; enable language detection, DTMF, transfer_to_number.
2. Run FastAPI behind a tunnel (Ares `tunnel.sh`) and set `PUBLIC_BASE_URL`.
3. Import Twilio number; assign to agent.
4. **Test (2 PM gate):** call the number from a phone → agent answers <2 s → say “smoke near Torrey Pines, Calle Mar de Mariposa” → `call.started` + pin on console within 1 s of the tool call; agent asks no more than 3 questions; hang up mid-call → callback within 30 s; switch to Spanish → agent replies in Spanish, chip says ES. Tool latency p95 < 800 ms in server logs.

#### (f) Connects to

C3 (bearings), C4 (caller frames), C6 (merge on report), C7 (guidance), C9 (JUMP IN), C11 (same agent stack, warning agent).

#### (g) Time budget + fallback

Tool reply 800 ms (return cached data only). Transcript <1 s.
Fallback:
browser voice widget (ElevenLabs web SDK,
web/talk.html
from Ares) if the phone line fails; demo still shows the same events.

## C3. Caller location: landmarks first, bearings as a bonus

Owner: Staff + Andrej

(image: )

Prototype v2 · step 4 · two callers' rays cross; dashed ellipse “Estimate from 2 callers”. In v2 this is a bonus layer on top of landmark pins.
Numbers in mocks are placeholders, not measurements.

#### (a) UI

- Each caller gets a pin from their **landmark** (“behind the Vons on Carmel Valley Rd”) with a small label of the matched name and a gray “approx.” tag.
- If no landmark matched: no pin, the row says “Location: not yet”, and the agent keeps asking Q1 in simpler words. Never a guessed pin.
- Bonus: when ≥2 bearings exist, dashed white rays and a dashed ellipse labeled “Estimate ± n m”. Card text: “An estimate from caller reports. Not a confirmed location.”
- **Error / rays parallel:** no ellipse; landmark pins stand alone.

#### (b) Backend

- `services/landmarks.py`:
- Step 1: Gemini extracts landmark text from the caller's words (Section 13.6): `{landmarks:["Vons","Carmel Valley Rd"], relation:"behind"}`. Gemini never returns coordinates.
- Step 2: match against the cached `landmarks` table (fuzzy name + alias match, limited to the region and to the area near other callers). Fallback: Ares `geo.search` (Photon/Nominatim) restricted to the region box.
- Step 3: if exactly one good match → pin with `location_src='landmark'`. If several → the agent asks one short follow-up (“The Vons on Carmel Valley or on Del Mar Heights?”). If none → no pin.
- Bonus: keep Ares `swarm.py` (`Report`, `Source`, `source()`, `infer()`, `project()`) for bearings from words or the phone compass. A bearing never overrides a landmark pin; it only narrows the camera search and draws the ellipse.
- On a new pin or estimate: update `incidents.location` and trigger C4 camera confirmation.

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| Gemini landmark extraction (structured output) | `GEMINI_API_KEY` | [Structured output](https://ai.google.dev/gemini-api/docs/structured-output) | [https://aistudio.google.com/api-keys](https://aistudio.google.com/api-keys) (free tier) |
| Landmark list cached ahead by Bright Data (C1) + OSM | `BRIGHTDATA_API_TOKEN` | see C1 | Promo `sandhacks26` ($100) · Bijin's credit link: ____ · [https://brightdata.com/cp/start](https://brightdata.com/cp/start) |
| Browser compass (bonus) | — | [DeviceOrientationEvent](https://developer.mozilla.org/en-US/docs/Web/API/DeviceOrientationEvent) | — |

#### (d) Events

Emits
incident.created
/
incident.merge_suggested
(via C6),
bearing.added
,
estimate.updated
.
Consumes
nothing (called by tools).

#### (e) Build steps + acceptance test

1. Seed `landmarks` for the demo region; unit tests for 20 spoken phrases (“behind the Vons”, “by Torrey Pines High”).
2. Gemini extract + match; ambiguous → follow-up question text.
3. Port `tests/test_swarm.py` from Ares; keep green.
4. **Test:** “humo detrás del Vons en Carmel Valley” → pin at the Vons within 1 s of the tool call; “near the big tree” → no pin and a follow-up question; no test ever produces a pin without a landmark or a caller GPS fix.

#### (f) Connects to

C1 (landmark list), C2 (input), C4 (where to look), C5 (callers line), C6 (incident location).

#### (g) Time budget + fallback

Extract ≤1.5 s (off the 800 ms tool reply: the tool returns a holding line first, the pin arrives as an event).
Fallback:
Gemini timeout → plain text match on the transcript against
landmarks
.

## C4. Camera wall (ALERTCalifornia): cameras confirm caller reports

Owner: Andrej (triage) · Staff (feed)

(image: )

Prototype v2 · step 5 · “Checking cameras”. Three selected cameras with view cones; camera film strip at the bottom with SMOKE boxes or “Can't tell, haze”. Stills in the prototype are placeholders.
Numbers in mocks are placeholders, not measurements.

#### (a) UI

- **Role (v2):** cameras **confirm** what callers report. They do not discover fires. ALERTCalifornia already runs its own AI smoke detection, so we never pitch “AI detects smoke”. We point the 3 nearest cameras at the reported pin and ask “does this image support the report?”
- Map: all 28 cameras as small grey squares; the 3 selected near the estimate turn white with a view cone.
- Bottom strip: 3 tiles (180×96). Each tile: still, red box if smoke, label (“Smoke visible” / “No smoke visible” / “Can't tell, haze”), camera name, image age (“0:42 old”).
- **Live mode:** real still from the feed. On a calm day it will say “No smoke visible”. That is correct and stays on screen.
- **Replay mode** (`DEMO_REPLAY=1`): smoke frames from a past real fire, tile watermark “REPLAY · <date>”.
- **Pending:** gray placeholder “Checking camera…” up to 5 s, then “not counted”. **Error:** “Camera offline” or “Gemini timeout · not counted”.

#### (b) Backend

- Ares `feeds.cameras(lat, lon, radius_m)` queries the ArcGIS layer and returns id, name, image URL, lat/lon, km. `feeds.camera_jpeg()` fetches the still. Cache 120 s (layer's own `cacheMaxAge` is 120).
- `routers/cameras.py`: pick 3 nearest online cams to the estimate; emit `cameras.selected`; run `ml/triage.py` on each in parallel; write `triage_results`; emit `triage.result` per camera.
- Cache by `(camera_id, captured_at)`, so the same frame is never paid for twice.
- Caller frames from /sos/cam go through the same triage with `frame_source='caller'`.

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| `GET https://services8.arcgis.com/X84q166Srnyl4JMV/ArcGIS/rest/services/ALERTCalifornia_Camera_Feed/FeatureServer/0/query?geometry=lon,lat&distance=40000&units=esriSRUnit_Meter&outFields=*&f=json` (from Ares; layer name “ALERTCalifornia Cameras”, checked live) | none | [ALERTCalifornia cameras](https://cameras.alertcalifornia.org/) [alertcalifornia.org](https://www.alertcalifornia.org/) | free |
| Gemini `generate_content` with image part + `response_schema` | `GEMINI_API_KEY`, `GEMINI_MODEL` | [Image understanding](https://ai.google.dev/gemini-api/docs/image-understanding) [Structured output](https://ai.google.dev/gemini-api/docs/structured-output) [google-genai SDK](https://googleapis.github.io/python-genai/) | [https://aistudio.google.com/api-keys](https://aistudio.google.com/api-keys) (free tier) |

#### (d) Events

Emits
cameras.selected
,
triage.result
.
Consumes
estimate.updated
.

#### (e) Build steps + acceptance test

1. Lift `feeds.cameras` + `camera_jpeg`.
2. Write `ml/triage.py` (Section 11/13).
3. Label 25 real San Diego stills into `ml/eval/frames.csv`; run `run_eval.py`.
4. **Test:** live call to `/api/cameras?lat=32.92&lon=-117.23&n=3` returns 3 cameras with image URLs; triage on a clear frame returns `no_smoke` or `cant_tell`, never `smoke`; replay smoke frame returns `smoke` with a box; each in <5 s.

#### (f) Connects to

C3 (estimate), C5 (cameras row), C6 (raises level suggestion), C11/C13 (report cites cameras).

#### (g) Time budget + fallback

Gemini 5 s per frame, 3 in parallel.
Fallback:
timeout → tile “not counted”; feed down → last cached stills with age.

## C5. Evidence stack, why_line, and human Confirm

Owner: Staff

(image: )

Prototype v2 · step 6 · Evidence card: filled dots for Callers, Cameras, Wind; empty dots for Satellite (FIRMS) “No detection yet, can lag hours” and Perimeter (NIFC) “None mapped, doesn't rule out fire”. Buttons Confirm fire / Not a fire.
Numbers in mocks are placeholders, not measurements.
(image: )

Prototype v1 · S14 · same stack, with ALERTCalifornia stills in the side panel.
Numbers in mocks are placeholders, not measurements.

#### (a) UI

- **why_line** on the fire row: one line built only from sources that agree, e.g. “4 callers · cam K-12 smoke · wind NE 25 mph”.
- Stack rows, fixed order: Callers, Cameras, Posts (Reddit/X), Satellite (FIRMS), Perimeter (NIFC), Wind (NWS). Satellite and posts are **lines here**, not separate panels. Green dot = agrees; **gray = unknown or no data (never green)**, with reason; red = disagrees.
- Each row has a one-line detail and age: “2 of 3 see smoke, newest 0:42 old”.
- Primary button **Confirm fire** (one key: Enter), secondary **Not a fire**. Disabled until at least callers or cameras agree.
- Right panel: measured clock “first signal → human confirm” (from events), callers, cameras agreeing, residents asking for help. Any panel not loaded in 5 s shows a gray placeholder.
- Rule shown under buttons: “AGNI suggests. You decide.”

#### (b) Backend

- `services/evidence.py:build(incident_id)` → 6 rows into `evidence`; `why_line(rows)` → `incidents.why_line`, sent in `evidence.updated` and on every incident event.
- Callers agree: ≥2 bearings cross or ≥2 calls merged. Cameras agree: ≥1 `smoke` verdict within 3 km and 10 min. Wind: NWS observation exists (it supports the spread direction; it never proves a fire). FIRMS: any VIIRS detection within 2 km in 24 h, else empty with “can lag hours”. NIFC: perimeter contains point, else empty with “none mapped yet”.
- `POST /api/incidents/{id}/confirm`: sets `status='confirmed'`, `level=1`, `confirmed_by`, writes `decisions` row, starts measured clock mark `human_confirm`, then asks C7 for a route.
- `reject`: `status='rejected'`, keeps the log.

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| NWS: `GET https://api.weather.gov/points/{lat},{lon}` → `observationStations` → `{station}/observations/latest` (Ares `feeds.wind`) | `NWS_USER_AGENT` header | [NWS API](https://www.weather.gov/documentation/services-web-api) | free |
| FIRMS: `GET https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/VIIRS_SNPP_NRT/{w,s,e,n}/{days}` (and VIIRS_NOAA20_NRT) | `FIRMS_MAP_KEY` | [FIRMS area API](https://firms.modaps.eosdis.nasa.gov/api/area/) | [MAP_KEY signup](https://firms.modaps.eosdis.nasa.gov/api/map_key/) |
| NIFC WFIGS: `GET https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0/query` | none | [WFIGS perimeters](https://data-nifc.opendata.arcgis.com/datasets/nifc::wfigs-current-interagency-fire-perimeters) | free |

#### (d) Events

Emits
satellite.result
,
evidence.updated
(with
why_line
; and
triage.result
with level 1 on confirm).
Consumes
estimate.updated
,
triage.result
,
incident.merged
.

#### (e) Build steps + acceptance test

1. Lift `feeds.wind`, `feeds.hotspots`, `feeds.fire_rings`.
2. Write `evidence.build` + unit tests for each row state.
3. Card + keyboard Enter.
4. **Test:** with FIRMS key missing, row shows “Satellite: key not set” (honest), not a crash; Confirm writes a `decisions` row with the human's name and emits `evidence.updated` with `confirmed_by`; nothing dispatches without a later Approve.

#### (f) Connects to

C3, C4, C6 (inputs); C7 (route starts on confirm); C13 (report cites evidence).

#### (g) Time budget + fallback

Build <300 ms from cached feeds.
Fallback:
any feed down → row “error · last good 12 min ago”.

## C6. Incident store + duplicate-call merge (suggest only)

Owner: Staff

(image: )

Prototype v1 · S8 · merge card with per-caller distance/time and “↶ Undo merge”. v2 changes it: the merge is a suggestion on the fire row until a human accepts.
Numbers in mocks are placeholders, not measurements.

#### (a) UI

- Fire row shows **“Suggested merge: caller 2 · 420 m · 3 min · same fire?”** with keys **M** accept and **N** keep apart. Gemini's reason in gray under it.
- After accept: the call folds into the fire row, NEW badge +1, and a one-click **↶ Undo merge** link (key U) stays on the row.
- Never a silent auto-join. A far caller (e.g. several km away) simply becomes its own row.
- Right panel counters come from events only: calls, fires, duplicate units sent. In the headline slot: the measured value from `sim.json`, else “— not measured yet”.
- **Uncertain** (Gemini confidence low): suggestion shown in gray with “Maybe same fire?”; still needs M or N.

#### (b) Backend

- `services/merge.py`:
- Fast rule on every `report_fire`: candidate = open incident with distance ≤ 800 m and |Δt| ≤ 20 min. If none → `incident.created`.
- If candidate: create the call's own incident AND a `merges` row with `state='suggested'`; run the Gemini same-event check (Section 13.3); emit `incident.merge_suggested` with reason and confidence.
- Accept (`POST /api/merges/{id}/accept`, key M) → `state='accepted'`, `merged_into` set, `decisions` row, emit `incident.merged`.
- Keep apart (key N) → `state='kept_apart'`. Undo (one click) → `state='undone'`, call returns to its own incident, emit `incident.created`.
- Dispatch guard: C8 refuses a second unit for the same incident unless the human ticks “send another”. With a pending suggestion, the Approve button warns “Possible duplicate of Torrey Pines fire”.
- Store: SQLite now; Neon Postgres + PostGIS tonight via `DATABASE_URL`. The `decisions` table is the audit log. Practice incidents run on a Neon branch.

```
def attach_or_suggest(call):
    inc = db.create_incident(call)                       # every call gets its own row first
    bus.emit("incident.created", inc.id, inc.public())
    for other in db.open_incidents(exclude=inc.id):
        d = haversine_m(call.lat, call.lon, other.lat, other.lon)
        dt = abs((call.started_at - other.created_at).total_seconds())
        if d <= 800 and dt <= 20 * 60:
            m = db.add_merge(kept_id=other.id, merged_id=inc.id, call_id=call.id,
                             distance_m=d, dt_s=int(dt), state="suggested")
            asyncio.create_task(suggest_with_gemini(m))  # emits incident.merge_suggested
            break
    return inc
```

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| Neon Postgres (connection string) + PostGIS extension | `DATABASE_URL` | [Neon PostGIS](https://neon.com/docs/extensions/postgis) [Branching](https://neon.com/docs/introduction/branching) | Promo `hackonneon` · Bijin's credit link: ____ · [https://neon.com/signup](https://neon.com/signup) |
| Gemini same-event check | `GEMINI_API_KEY` | [Structured output](https://ai.google.dev/gemini-api/docs/structured-output) | [https://aistudio.google.com/api-keys](https://aistudio.google.com/api-keys) (free tier) |

#### (d) Events

Emits
incident.created
,
incident.merge_suggested
,
incident.merged
.
Consumes
call.started
(internal call).

#### (e) Build steps + acceptance test

1. Migration `001_core` for both engines.
2. Write merge with pure functions; unit tests from `ml/eval/merges.csv` (~20 labeled pairs).
3. Accept / keep-apart / undo routes + row UI.
4. **Test:** a fixture of close calls plus one far call → each close call yields exactly one `incident.merge_suggested` and **no** `incident.merged` until M is pressed; the far call is its own incident; Undo restores a separate incident; approving dispatch on each fire gives `duplicate_units_sent=0`.

#### (f) Connects to

C2 (input), C1 (signals attach), C5 (why_line), C8 (duplicate guard), C12 (surge uses same logic), C13 (audit log).

#### (g) Time budget + fallback

Fast rule <20 ms inside the tool call. Gemini check 5 s, off the call path.
Fallback:
Gemini timeout → suggestion still shown, marked “not checked”.

## C7. Nearest unit + routing around closures + safe shelter (geo.py)

Owner: Staff

(image: )

Prototype v2 · step 8 · “Engine 42, 7 min via Genesee”, chip “Avoids Caltrans closure”, caller evacuation line: “Not routing to Torrey Pines HS, 1.2 km downwind. Sending callers to RIMAC.” Button Approve dispatch.
Numbers in mocks are placeholders, not measurements.

#### (a) UI

- Unit card: “Engine 42 · <eta from route> via Genesee”; chip “Avoids Carmel Valley Rd (Caltrans 12:52)”; next two units listed small.
- Map: white route line for the unit; green line for caller evacuation to the shelter; red dashed closure segments with label; refused shelter shown with a strikethrough label and reason.
- Shelter chip: “RIMAC · open · room” only if Bright Data capacity says so; else “RIMAC · capacity unknown”.
- **Fallback state:** straight dashed line with label **estimate** and “Road route unavailable”.

#### (b) Backend

- `services/routing.py`: top 3 available units by straight distance (PostGIS `<->` or haversine). For each: ORS route with `avoid_polygons` = buffered closures + current ring (C10). Pick min duration. Run 3 requests in parallel, overall timeout 2 s.
- OSRM fallback: `alternatives=true`, drop routes that intersect a closure (shapely), keep the fastest.
- Shelter: Ares `geo.choose(origin, places, hazard, need='fire', drift=wind.to_deg, perimeters=…)`. It refuses places downwind (`DRIFT_ARC`) and inside perimeters; record every refused place with its reason for the card.
- `GET /api/incidents/{id}/route` caches the answer for 60 s; `get_guidance` tool reads that cache only.
- **Spoken ETA rule:** the agent may say an ETA only if a unit was dispatched and the route result has `eta_s`. A straight-line estimate is spoken as “help is on the way” with no minutes. No route → “Stay where you are safe.”

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| ORS: `POST https://api.openrouteservice.org/v2/directions/driving-car/geojson` with `options.avoid_polygons` | `ORS_API_KEY` | [ORS API reference](https://giscience.github.io/openrouteservice/api-reference/) [ORS playground](https://openrouteservice.org/dev/#/api-docs) | [ORS signup](https://openrouteservice.org/dev/#/signup) |
| OSRM demo: `GET https://router.project-osrm.org/route/v1/driving/{lon,lat};{lon,lat}?overview=full&geometries=geojson&alternatives=true` (demo server, fair use only) | `OSRM_BASE_URL` | [OSRM API](https://project-osrm.org/docs/v5.24.0/api/) | free |
| Closures + shelters: from C1 tables (Bright Data) | — | see C1 | Promo `sandhacks26` ($100) · Bijin's credit link: ____ · [https://brightdata.com/cp/start](https://brightdata.com/cp/start) |

#### (d) Events

Emits
route.ready
.
Consumes
evidence.updated
(confirmed),
ring.updated
(re-route).

#### (e) Build steps + acceptance test

1. Seed `units.json` (Engine 42 at Station 42, 3 more). Seed `shelters.json` (RIMAC, Torrey Pines HS) from Ares `data/refuges.json`.
2. ORS call + timeout; OSRM fallback; straight-line fallback.
3. Wire `geo.choose`; store refused list.
4. **Test:** with a closure on Carmel Valley Rd, route avoids it; with wind from NW, Torrey Pines HS is refused and RIMAC is chosen; with ORS blocked by firewall, card shows straight line labeled “estimate” in <2.1 s.

#### (f) Connects to

C1 (closures, capacity), C5 (trigger), C8 (dispatch uses route), C10 (avoid ring), C2 (spoken guidance).

#### (g) Time budget + fallback

2 s total.
Fallback:
straight line + haversine ETA at 40 km/h, labeled estimate.

## C8. Dispatch with idempotency key + Arduino Uno bridge

Owner: Staff

(image: )

Prototype v1 · S6 · “DISPATCHED · Engine 42 · ETA 6 min”, radio line, “Station alert ● Uno buzzing”. JUMP IN turns active.
Numbers in mocks are placeholders, not measurements.
(image: )

Prototype v2 · step 9 · “Engine 42 en route”, chip “Approved by dispatcher”, caller phone shows “Engine 42 is on the way. Drive east on Genesee to RIMAC.”
Numbers in mocks are placeholders, not measurements.

#### (a) UI

- Button **Approve dispatch ⏎** on the route card. After click: button becomes “Dispatched 20:13:56 by Bijin”, never clickable twice.
- Chip “Station alert ● Uno buzzing” (red) after the board acks; “Station offline” (grey) if serial missing.
- Unit marker animates along the route line. Clock in right panel turns red and freezes at “first signal → human dispatch”.

#### (b) Backend

- `POST /api/incidents/{id}/dispatch` needs header `Idempotency-Key` (UUID made when the card renders). Insert into `dispatches` with UNIQUE key; on conflict return the first row (same 200). Second unit for same incident → 409 unless `allow_additional=true`.
- Writes `decisions` row; `units.status='dispatched'`; clock mark `human_dispatch`.
- `services/serial_bridge.py`: background thread owns the port; queue of commands; reconnect every 5 s.
- Protocol (ASCII, newline-terminated, 9600 baud): `P` ping → `OK`; `D<unit>` dispatch → buzz 3×200 ms + red LED on → `ACK D42`; `C` clear → LED off → `ACK C`; `W` warning pattern (long buzz).
- The agent speaks the ETA on the next turn: `get_guidance` now returns “Engine 42 is about 7 minutes away.”

```
// hardware/uno_station/uno_station.ino
const int BUZ = 8, LED = 13;
void setup() { pinMode(BUZ, OUTPUT); pinMode(LED, OUTPUT); Serial.begin(9600); }
void buzz(int n, int ms) { for (int i = 0; i < n; i++) { tone(BUZ, 2000); delay(ms); noTone(BUZ); delay(120); } }
void loop() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n'); cmd.trim();
  if (cmd == "P") Serial.println("OK");
  else if (cmd.startsWith("D")) { digitalWrite(LED, HIGH); buzz(3, 200); Serial.println("ACK " + cmd); }
  else if (cmd == "W") { buzz(1, 900); Serial.println("ACK W"); }
  else if (cmd == "C") { digitalWrite(LED, LOW); Serial.println("ACK C"); }
}
```

```
# routers/dispatch.py
@router.post("/api/incidents/{iid}/dispatch")
def dispatch(iid: str, body: DispatchIn, idempotency_key: str = Header(), op=Depends(operator)):
    prior = db.dispatch_by_key(idempotency_key)
    if prior: return prior.public()
    if db.has_dispatch(iid) and not body.allow_additional:
        raise HTTPException(409, "Unit already sent to this incident")
    d = db.create_dispatch(iid, body.unit_id, idempotency_key, approved_by=op.name)
    serial_bridge.send(f"D{body.unit_id}")
    bus.emit("unit.dispatched", iid, d.public())
    return d.public()
```

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| pyserial `serial.Serial(SERIAL_PORT, 9600, timeout=1)` | `SERIAL_PORT`, `SERIAL_BAUD` | [pyserial](https://pyserial.readthedocs.io/en/latest/) [Arduino Serial](https://docs.arduino.cc/language-reference/en/functions/communication/serial/) | — |

#### (d) Events

Emits
unit.dispatched
.
Consumes
route.ready
.

#### (e) Build steps + acceptance test

1. Flash `hardware/uno_station/uno_station.ino`.
2. Write bridge + `/health` serial field.
3. Route + card.
4. **Test:** double-click Approve and replay the same request with curl → exactly 1 `dispatches` row, 1 `unit.dispatched`, 1 buzz. Unplug the Uno → dispatch still succeeds, chip says “Station offline”.

#### (f) Connects to

C7 (route), C6 (duplicate guard), C2 (ETA spoken), C12 (counts duplicate_units_sent), C13 (clock).

#### (g) Time budget + fallback

API <200 ms; serial ack <500 ms.
Fallback:
no board → on-screen station light.

## C9. JUMP IN warm handoff

Owner: Staff

(image: )

Prototype v2 · step 10 · “You're live with caller 2”. Summary read to dispatcher first. Button “Hand back to AGNI”. JUMP IN pill turns red.
Numbers in mocks are placeholders, not measurements.
(image: )

Prototype v1 · S7 · “HUMAN · You are on the call · Agent briefed you first”, HAND BACK button.
Numbers in mocks are placeholders, not measurements.

#### (a) UI

- Bottom-right pill **JUMP IN** (key J), grey when no live call, white when available, red “HAND BACK” while the human is on.
- On press: card “You're live with caller n”, the 1-sentence summary in large text, needs chips, last 3 transcript lines.
- Caller hears: “I'm connecting you to a dispatcher now. Stay on the line.”
- **Error:** transfer fails → “Couldn't connect. AGNI is still with the caller.” and the agent continues.

#### (b) Backend

- `POST /api/calls/{id}/jump-in`: Gemini handoff summary from transcript (Section 13, 5 s, else last 3 lines). Emit `handoff.started`. Tell the agent to transfer: the agent has the `transfer_to_number` system tool with destination `DISPATCHER_PHONE_NUMBER` and type `twilio_warm_conference_transfer` (dispatcher hears the agent's summary, then is connected). Trigger it by sending a contextual update (“Dispatcher requests transfer now”) into the live conversation, or by a `should_transfer` flag the agent reads from `get_guidance` on its next turn.
- `POST /api/calls/{id}/hand-back`: after a transfer the AI is no longer on the line. Hand back = dispatcher ends their leg and AGNI calls the caller back with the Twilio outbound endpoint, passing the incident context as dynamic variables. Emit `handoff.ended` with `resumed_by:"agent"`, `mode:"callback"`.
- Ares already has dispatcher takeover in SQLite (`store.py`); keep its `state='human'` logic for the console.

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| `transfer_to_number` system tool, transfer type `twilio_warm_conference_transfer` | agent config | [Transfer to number](https://elevenlabs.io/docs/eleven-agents/customization/tools/system-tools/transfer-to-number) | Creator month via Discord · Bijin's credit link: ____ · [https://elevenlabs.io/app/sign-up](https://elevenlabs.io/app/sign-up) |
| Callback: `POST https://api.elevenlabs.io/v1/convai/twilio/outbound-call` {agent_id, agent_phone_number_id, to_number, conversation_initiation_client_data} | `ELEVENLABS_API_KEY`, `ELEVENLABS_PHONE_NUMBER_ID` | [Outbound call via Twilio](https://elevenlabs.io/docs/eleven-agents/api-reference/integrations/twilio/outbound-call) [Dynamic variables](https://elevenlabs.io/docs/eleven-agents/customization/personalization/dynamic-variables) | same |
| Gemini summary | `GEMINI_API_KEY` | [Structured output](https://ai.google.dev/gemini-api/docs/structured-output) | [https://aistudio.google.com/api-keys](https://aistudio.google.com/api-keys) (free tier) |

#### (d) Events

Emits
handoff.started
,
handoff.ended
.
Consumes
call.transcript
.

#### (e) Build steps + acceptance test

1. Enable transfer_to_number in the agent with the dispatcher's phone.
2. Write summary prompt + route.
3. **Test (8 PM gate):** live phone call → press J → dispatcher phone rings within 5 s → dispatcher hears summary, then the caller → press HAND BACK → caller gets an AGNI callback that knows the incident (“I'm back. Engine 42 is 4 minutes away.”). Events in order: `handoff.started` → `handoff.ended{resumed_by:"agent"}`.

#### (f) Connects to

C2 (live call), C13 (report notes takeover times).

#### (g) Time budget + fallback

Summary 5 s (fallback: last 3 lines). Transfer ≈ ring time.
Fallback:
if warm transfer isn't available on the account, use the default conference transfer and have the dispatcher read the summary from the screen.

## C10. Spread ring (NumPy wind model)

Owner: Andrej

(image: )

Prototype v2 · step 11 · “Homes in the 30-min ring”, chips “Estimate” and “Wind NW 14 mph”, button Send warning.
Numbers in mocks are placeholders, not measurements.

#### (a) UI

- Soft orange ring with blurred edge, stretched downwind. Label on the ring: “30-min estimate”. Card: approx. homes in ring + downwind zone, wind, route avoids closure + ring, shelter status.
- Button **Send warning to N homes** (C11).
- **Empty:** no wind data → ring is a plain circle with “Wind unknown · circle estimate”.
- **Battalion chief tablet** (`/chief`, read-only): big map with a **Now / +30 min** toggle, closures, units, shelters. No buttons that change anything.

#### (b) Backend

- `ml/spread.py` (Section 11): 100 m grid, 10 km square, 30 min, wind from NWS, optional slope; returns GeoJSON polygon + soft-edge opacities. Re-run when wind refreshes (~10 min) or from /ops “grow ring”.
- Homes estimate: count of seeded address points inside the polygon (`seed/homes_sd.geojson`, from OpenStreetMap buildings). Label it “approx. homes”.
- Store in `rings`; C7 adds the ring to `avoid_polygons`.

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| NWS (via C5 cache) | `NWS_USER_AGENT` | [NWS API](https://www.weather.gov/documentation/services-web-api) [NumPy](https://numpy.org/doc/stable/) | free |

#### (d) Events

Emits
ring.updated
.
Consumes
evidence.updated
(confirmed).

#### (e) Build steps + acceptance test

1. Write model + test: wind from 315° moves the centroid toward ~135°.
2. Polygon from grid (marching squares or convex hull of burned cells).
3. **Test:** confirmed incident → `ring.updated` with `label:"estimate"`, `minutes:30`, within 1 s.

#### (f) Connects to

C5 (wind + trigger), C7 (avoid), C11 (who to warn), C14 (grow ring).

#### (g) Time budget + fallback

<1 s.
Fallback:
wind missing → circle of radius 1.5 km labeled “circle estimate”.

## C11. Targeted two-way warning call (“One more thing”)

Owner: Staff

(image: )

Prototype v1 · S10 · reverse 911 list: “Judge · +1 ••• 4471 · ringing · ES”; judge phone shows “AGNI Alert · San Diego County” and the Spanish message.
Numbers in mocks are placeholders, not measurements.
(image: )

Prototype v2 · step 12 · “Calling homes in the ring” and a pressed-1 count added to the rescue list.
Numbers in mocks are placeholders, not measurements.

#### (a) UI

- **Why it is new:** San Diego County already sends mass alerts ([AlertSanDiego](https://www.alertsandiego.org/)). AGNI adds **targeted + two-way**: only addresses in the spread ring and downwind zone, and a way to answer back (press 1 or say help).
- **Only after a human confirms** the fire. The Send button is disabled until then.
- Card after Send: list of recipients (last 4 digits only), status per row: queued / ringing / answered / pressed 1 / no answer; language tag.
- Rescue pins: red pins with a person icon for each “pressed 1” or “said help”; counter “Residents asking for help 2”.
- Judge's phone (demo): incoming “AGNI Alert”; message: “Fuego cerca de usted. Salga ahora hacia el este por Genesee. El refugio en RIMAC tiene espacio. Si necesita ayuda para salir, oprima 1 o diga ayuda.” Spoken slowly, short, repeated once.
- **Error:** batch fails → “Warning not sent · retry” (nothing marked sent until ElevenLabs returns an id).

#### (b) Backend

- `POST /api/warnings/{incident_id}` (human, Idempotency-Key; 409 if the incident is not confirmed). Targeting: addresses inside the spread ring polygon UNION a downwind wedge (wind direction ± 30°, 3 km). In the demo, those “addresses” are the opt-in list `seed/warn_list.json` (team phones + judges who say yes), each placed at a demo address. Never real residents.
- Calls ElevenLabs batch calling with the warning agent (`ELEVENLABS_WARN_AGENT_ID`); each recipient gets `conversation_initiation_client_data.dynamic_variables` = {language, street, direction, shelter}.
- Warning agent prompt (Section 12) says the message slowly, then: “Press 1 or say help if you need help getting out.” DTMF input enabled. On “1” or the word help (any language) the agent calls `request_rescue` → `rescues` row → `rescue.requested`.
- Poll `GET /v1/convai/batch-calling/{id}` every 3 s to update row status. Uno gets `W`.

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| `POST https://api.elevenlabs.io/v1/convai/batch-calling/submit` {call_name, agent_id, agent_phone_number_id, recipients:[{phone_number, conversation_initiation_client_data}]} | `ELEVENLABS_API_KEY`, `ELEVENLABS_WARN_AGENT_ID`, `ELEVENLABS_PHONE_NUMBER_ID` | [Batch calling API](https://elevenlabs.io/docs/eleven-agents/api-reference/batch-calling/create) [Batch calls guide](https://elevenlabs.io/docs/eleven-agents/phone-numbers/batch-calls) [DTMF input](https://elevenlabs.io/docs/eleven-agents/customization/multimodal-input) | Creator month via Discord · Bijin's credit link: ____ · [https://elevenlabs.io/app/sign-up](https://elevenlabs.io/app/sign-up) |
| Single call fallback: `POST /v1/convai/twilio/outbound-call` | same | [Outbound call](https://elevenlabs.io/docs/eleven-agents/api-reference/integrations/twilio/outbound-call) | same |

#### (d) Events

Emits
warning.sent
,
rescue.requested
.
Consumes
ring.updated
.

#### (e) Build steps + acceptance test

1. Create warning agent (second agent, same voice, bilingual).
2. Route + batch call + status poller.
3. **Test:** Send to 2 team phones → both ring within 15 s; one presses 1 and one says “help” → two rescue pins within 2 s; Send is refused before Confirm; replaying the same Idempotency-Key does not call anyone twice.

#### (f) Connects to

C10 (ring), C7 (direction + shelter), C2 (same telephony), C13 (report counts warned / pressed 1).

#### (g) Time budget + fallback

Submit <1 s; ring time varies.
Fallback:
batch API error → loop single outbound calls; Twilio down → show the call list as “would call” and play the message audio on the laptop speaker, labeled demo.
```
# routers/warnings.py
@router.post("/api/warnings/{iid}")
def send_warning(iid: str, body: WarnIn, idempotency_key: str = Header(), op=Depends(operator)):
    if (w := db.warning_by_key(idempotency_key)): return w.public()
    route = routing.cached(iid); people = db.warn_list()
    recips = [{"phone_number": p.phone,
               "conversation_initiation_client_data": {"dynamic_variables": {
                   "language": p.lang, "direction": route.direction_words, "shelter": route.shelter.name,
                   "incident_id": iid}}} for p in people]
    r = httpx.post("https://api.elevenlabs.io/v1/convai/batch-calling/submit",
                   headers={"xi-api-key": ELEVEN_KEY},
                   json={"call_name": f"warn-{iid}", "agent_id": WARN_AGENT,
                         "agent_phone_number_id": PHONE_ID, "recipients": recips}, timeout=10)
    r.raise_for_status()
    w = db.create_warning(iid, r.json()["id"], len(recips), op.name, idempotency_key)
    bus.emit("warning.sent", iid, w.public()); serial_bridge.send("W")
    return w.public()
```

## C12. Surge script (75 simulated calls on Neon branch surge-sim) → sim.json

Owner: Staff

(image: )

Prototype v1 · S11 · surge banner and severity-sorted queue. In v2 the banner reads only from sim.json / live counters.
Numbers in mocks are placeholders, not measurements.

#### (a) UI

- Top banner: “**N calls → M incidents · D duplicate units sent**”, filled live from `surge.stats` during a run, and from `sim.json` on the opening screen. Missing → “— not measured yet”.
- Island: “Surge replay · Neon branch surge-sim”. A clear **SIMULATION** tag on every surge row.
- Fire list sorted by severity with caller counts; map zooms out to the county.

#### (b) Backend

- `backend/sim/surge.py` (details in §14B(b)): builds 75 scripted calls with ground truth (2–3 true fires, duplicates, lost callers, mixed languages, a false alarm). Feeds them through the same `report_fire` → landmarks → merge → evidence → warnings code path. No ElevenLabs minutes are used (text only).
- Runs against the `surge-sim` Neon branch (copy-on-write copy of main). Main stays clean.
- Emits `surge.stats` every 1 s: calls, fires, duplicate_units_sent, false_merges.
- Human steps are simulated by a scripted operator and labeled “simulated approval”. Merge suggestions are scored against ground truth.
- At the end writes `backend/sim/sim.json`; `GET /api/proof` serves it to the console and the slide.

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| Neon API: create branch `POST /api/v2/projects/{project_id}/branches`; reset: CLI `neon branches reset surge-sim --parent` | `NEON_API_KEY`, `NEON_PROJECT_ID`, `NEON_SURGE_BRANCH_ID` | [Create branch API](https://api-docs.neon.tech/reference/createprojectbranch) [Reset from parent](https://neon.com/docs/guides/reset-from-parent) [CLI branches](https://neon.com/docs/reference/cli-branches) | Promo `hackonneon` · Bijin's credit link: ____ · [https://neon.com/signup](https://neon.com/signup) |

#### (d) Events

Emits
surge.stats
plus normal events with
data.sim=true
.
Consumes
nothing.

#### (e) Build steps + acceptance test

1. Generator with fixed random seed + ground-truth file.
2. Branch switch in `db.py` (`with db.branch('surge-sim')`).
3. Scorer → `sim.json`.
4. **Test:** run twice with the same seed → identical `sim.json`; main branch incident count unchanged; console headline equals `sim.json` values; delete `sim.json` → headline shows “— not measured yet”.

#### (f) Connects to

C3, C6, C8, C11 (code paths under test), C14 (start/reset), C15 (Tiger counter if used), §14B, §15.

#### (g) Time budget + fallback

1 s ticks; full run ≤ 2 min.
Fallback:
no Neon → temp SQLite file, labeled “local sim”.

## C13. After-action report + audit trail (Gemini draft, human signs, measured clock)

Owner: Staff + Andrej

(image: )

Prototype v2 · step 13 · “Incident closed”: report timeline, measured clock, counts.
Numbers in mocks are placeholders, not measurements.

#### (a) UI

- Centered sheet: title “Torrey Pines fire, Incident 1”; timeline bullets with Pacific times; big numbers from the event log: first report → human confirm → dispatch → first warning, callers, duplicate units.
- **Audit trail** (what the county buys): every human decision (confirm, merge accept/undo, dispatch, warning, sign) with who and when, from `decisions`. Export as PDF/CSV.
- Header: “DRAFT · written by AI from the event log · edit before signing”. Editable text area. Button **Sign and close**.
- Proof panel: “camera triage accuracy · crowd precision · merge precision” from `eval.json` with n; if missing: “not measured yet”.
- After sign: “Signed by <operator> <time> PT”. The signed report is read-only.

#### (b) Backend

- `services/clock.py`: marks first_signal, first_call, estimate, human_confirm, human_dispatch, warning_sent, closed, all from `events.ts`. Numbers come only from these rows.
- `GET /api/incidents/{id}/report`: Gemini drafts from the `decisions` + `events` log (Section 13). It may not add facts not in the log.
- `POST /close`: saves `final`, `signed_by`; emits `incident.closed`.

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| Gemini text generation with JSON schema | `GEMINI_API_KEY` | [Structured output](https://ai.google.dev/gemini-api/docs/structured-output) | [https://aistudio.google.com/api-keys](https://aistudio.google.com/api-keys) (free tier) |

#### (d) Events

Emits
incident.closed
.
Consumes
all events for the incident.

#### (e) Build steps + acceptance test

1. Clock marks + unit test.
2. Draft prompt + schema.
3. **Test:** close the demo incident → every time in the report matches an `events` row; editing the draft and signing stores the edited text, not the draft.

#### (f) Connects to

All components (reads the log and the
decisions
audit table).

#### (g) Time budget + fallback

Gemini 5 s.
Fallback:
template report filled from the clock and counts.

## C14. Hidden /ops panel, overflow toggle, and county setup

Owner: Staff

#### (a) UI

- Route `/ops` (operator token), opened with Shift+O. Plain grid of big buttons; never shown to judges by default.
- **Overflow ON / OFF** switch at the top (writes `settings.overflow_enabled`; the 911 center owns this switch in real use).
- Buttons: **Replay signals**, **Start surge**, **Grow ring +10 min**, **Toggle DEMO_REPLAY**, **Reset to Calm**, **Run eval**. Status lines: DB branch, serial, each feed age, last seq, ElevenLabs agent id (masked).
- Reset shows a confirm: “Reset branch main-demo to its parent snapshot? Live data on this branch will be lost.”

#### (b) Backend

- `routers/ops.py` calls services: `brightdata.replay(seed)`, `surge.start()`, `spread.grow(minutes)`, `neon.reset(branch)`.
- Reset to Calm: Neon branch reset from parent (the demo runs on a child branch `demo` of a clean `calm` snapshot), then emit a stream marker so consoles clear and reload `/api/state`. SQLite fallback: copy `seed/calm.db` over the working file.
- Practice incidents (onboarding) use branch `practice-<id>`, deleted after 1 h.
- **County setup page** (`/setup`, admin): upload units CSV, choose region, enter the overflow phone number, press “Run a practice incident” (Neon practice branch).

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| Neon branches API + CLI | `NEON_API_KEY`, `NEON_PROJECT_ID` | [Manage branches](https://neon.com/docs/manage/branches) [Reset from parent](https://neon.com/docs/guides/reset-from-parent) | Promo `hackonneon` · Bijin's credit link: ____ · [https://neon.com/signup](https://neon.com/signup) |

#### (d) Events

Emits
whatever the triggered component emits.
Consumes
none.

#### (e) Build steps + acceptance test

1. Panel HTML + routes.
2. **Test:** run the full demo, press Reset to Calm → console back to S0 in <5 s, `/api/state` shows 0 incidents, main data untouched.

#### (f) Connects to

C1, C10, C12, C13, and Neon.

#### (g) Time budget + fallback

Reset <5 s.
Fallback:
SQLite file copy.
```
 ┌────────────────────────── /ops ─────────────────────────────┐
 │ OVERFLOW: [ ON ]   DB: neon/demo   Serial: OK   Last seq: 1287│
 │ Feeds: cams 0:42  wind 6:10  firms 11:02  brightdata 2:15   │
 │                                                             │
 │ [ Replay signals ]  [ Start surge (75) ]  [ Grow ring +10 ] │
 │ [ DEMO_REPLAY: ON ] [ Run eval ]          [ Reset to Calm ] │
 └─────────────────────────────────────────────────────────────┘
```

## C15. Stretch: Tiger Data surge counter (only if needed)

Owner: Staff (after freeze, Sunday)

#### (a) UI

- Only if the Postgres counter can't keep the 1-second surge banner smooth. Caption “live from Tiger Data” on the banner. Otherwise skip it; no logo without a job.

#### (b) Backend

- Second DB (`TIGER_DATABASE_URL`). `services/tiger.py` writes one row per event to hypertable `event_ticks`; the surge banner reads `ticks_1s`. Off by default.

```
CREATE TABLE event_ticks (ts TIMESTAMPTZ NOT NULL, type TEXT, incident_id TEXT, sim BOOLEAN);
SELECT create_hypertable('event_ticks', by_range('ts'));
CREATE MATERIALIZED VIEW ticks_1s WITH (timescaledb.continuous) AS
  SELECT time_bucket('1 second', ts) AS bucket,
         count(*) FILTER (WHERE type = 'call.started')    AS calls,
         count(*) FILTER (WHERE type = 'incident.created') AS fires,
         count(*) FILTER (WHERE type = 'unit.dispatched')  AS dispatches
  FROM event_ticks GROUP BY bucket;
```

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| Timescale: `create_hypertable`, continuous aggregates | `TIGER_DATABASE_URL` | [Hypertables](https://docs.tigerdata.com/use-timescale/latest/hypertables/) [Continuous aggregates](https://docs.tigerdata.com/use-timescale/latest/continuous-aggregates/) | Bijin's credit link: ____ · [https://console.cloud.timescale.com/signup](https://console.cloud.timescale.com/signup) |

#### (d) Events

Emits
none new.

#### (e) Build steps + acceptance test

1. Only after Sunday freeze, and only if the banner lags.
2. **Test:** banner values equal the Postgres counter ±1 each second.

#### (f) Connects to

C12 (surge).

#### (g) Time budget + fallback

Async.
Fallback:
off → Postgres counter.

## C16. Optional hosting (Vultr)

Owner: Staff

#### (a) UI

- No UI change. Console URL becomes a stable HTTPS domain instead of a tunnel.

#### (b) Backend

- One small Ubuntu VM: `uvicorn app.main:app` behind Caddy (auto TLS). The Uno stays on the demo laptop, so keep the serial bridge local: run a tiny `serial_agent.py` on the laptop that subscribes to `/api/events` and writes to the port.
- Do this only if the tunnel is flaky. A tunnel from the laptop is fine for judging.

#### (c) External API

| Endpoint | Auth env | Docs | Credits / signup |
|---|---|---|---|
| Vultr cloud compute | `VULTR_API_KEY` (only if scripting) | [Cloud compute docs](https://docs.vultr.com/products/compute/cloud-compute) [Vultr docs](https://docs.vultr.com/) | Bijin's credit link: ____ · [https://www.vultr.com/register/](https://www.vultr.com/register/) [403 to bots] |

#### (d) Events

None.

#### (e) Build steps + acceptance test

1. Create VM, open 443, install Python + Caddy, copy `.env` by hand (scp), start service.
2. **Test:** ElevenLabs tools hit the VM URL with p95 <800 ms; laptop serial agent buzzes on dispatch.

#### (f) Connects to

Everything (hosts C1–C15).

#### (g) Time budget + fallback

Fallback:
laptop + tunnel (Ares
tunnel.sh
).

## 11. ML spec (Andrej)

Written by Andrej in the team room; placed here as he asked. None of these can turn a pin red or dispatch anything. Only a human or a confirmed caller can.

| Piece | File | Input | Output | Rules |
|---|---|---|---|---|
| 1. Camera triage | `backend/ml/triage.py` | ALERTCalifornia still (JPEG bytes), `camera_id`, `captured_at` | `{label: smoke\|no_smoke\|cant_tell, flames_visible, box: [x0,y0,x1,y1]\|null (0–1), reason ≤20 words}` | Gemini 2.5 Flash via google-genai with `response_mime_type="application/json"` + `response_schema`. “If dark, hazy, or ambiguous, answer cant_tell. Never guess smoke.” Writes `triage_results`, emits `triage.result`. 5 s timeout → “Analyzing”. Cache by (camera_id, captured_at). |
| 2. Crowd-post classifier | `backend/ml/posts.py` | Bright Data posts: text, url, posted_at, scraped_at | `{about_fire, place_text\|null, confidence: high\|medium\|low}` | place_text is geocoded afterward. Gemini never invents coordinates. Only about_fire=true → `signal.new` (dashed pin). |
| 3. Caller bearings (bonus, v2) | `swarm.py` (built) | Caller position + bearing (compass on camera page, or words → angle) | Estimate point + ellipse when ≥2 bearings cross within 5 km | Bonus only: landmarks (C3) are primary. Emits `bearing.added`, `estimate.updated`. |
| 6. Caller harness (v2) | `backend/sim/harness.py` | 10 personas × 3 runs | `eval.json` agent scores | See §14B(a). |
| 4. Spread ring | `backend/ml/spread.py` (~80 lines NumPy) | NWS wind (points → nearest station → observations/latest), optional slope | GeoJSON polygon of burned-cell boundary + soft-edge opacities | 100 m cells, 10 km square, 30 min. Rate scales with alignment to wind. Always “30-min estimate”. `ring.updated` on wind refresh (~10 min). |
| 5. Eval + proof panel | `backend/ml/eval/` | frames.csv (25 real SD stills, hand-labeled), posts.csv (30), merges.csv (~20 pairs) | `eval.json` with accuracy/precision and n | `run_eval.py` prints each with n. /ops proof panel reads only eval.json; missing → “not measured yet”. |

```
# backend/ml/spread.py  (sketch)
import numpy as np
CELL, HALF, MINUTES = 100, 50, 30            # 100 m cells, 10 km square

def ring(lat, lon, wind_to_deg, wind_kph, base_m_per_min=8.0):
    burned = np.zeros((2*HALF+1, 2*HALF+1), bool); burned[HALF, HALF] = True
    w = np.deg2rad(wind_to_deg)
    dirs = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
    budget = np.zeros_like(burned, float)
    for _ in range(MINUTES):
        grow = np.zeros_like(burned)
        for dy, dx in dirs:
            ang = np.arctan2(dx, -dy)                     # 0 = north, clockwise
            align = max(0.1, np.cos(ang - w))             # tail-wind factor
            rate = base_m_per_min * (1 + 0.15 * wind_kph * align) * align
            src = np.roll(np.roll(burned, dy, 0), dx, 1)
            budget += src * rate / CELL / len(dirs)
        grow = budget >= 1.0
        burned |= grow
    return grid_to_polygon(burned, lat, lon, CELL)        # contour → GeoJSON, label "estimate"
```

Andrej offered to build pieces 1, 4 and 5 once Bijin says go.

## 12. ElevenLabs agent: prompt and tools

### 12.1 Intake agent system prompt ( agent/system_prompt.md )

```
You are AGNI, an overflow line for wildfire reports in San Diego County. You only answer
calls that 911 could not pick up because every line was busy. You are not 911 and you do
not replace dispatchers. A human dispatcher watches every call and makes every decision
about fires, units, and warnings. First words: "This is AGNI, helping 911 while lines are
busy." If report_fire returns overflow=false, say "Please hang up and dial 911." and end.

Style: calm, short sentences, under 15 words. One question at a time. Reply in the
caller's language. If they switch language, switch with them.

Ask at most THREE questions:
Q1 "What do you see, and what is near you?" Take landmarks, not addresses: a store,
   school, church, park, road. Call report_fire with the caller's exact words.
Q2 "Which way is the smoke from you?" Call add_bearing. If they don't know, move on.
Q3 "Is anyone with you? Can everyone walk?" Call set_needs. If someone can't move,
   say "I've marked that someone can't move. That goes to the top."
Safety first: if someone is in immediate danger, tell them to get away now, then go on.
If report_fire says the landmark is unclear, ask ONE short follow-up it gives you.
Offer the camera link only if they are on a smartphone and not driving.
Then call get_guidance and read its "say" text exactly. Never invent a place, route,
shelter, or time. Say an ETA only if get_guidance gives one. If there is no route,
say "Stay where you are safe. Help is coming."

Rules:
- Never promise a unit is coming unless get_guidance says a unit was dispatched.
- Never say a fire is confirmed unless get_guidance says confirmed.
- Never look things up on the web. Use only your tools.
- If get_guidance returns should_transfer=true, say "I'm connecting you to a dispatcher
  now. Stay on the line." and use transfer_to_number.
- If the caller asks for a human at any time, transfer.
- If the call drops, the system calls back. On a callback, start from {{resume_context}}.
Dynamic variables you may receive: {{incident_id}}, {{language}}, {{resume_context}}.
If {{resume_context}} is set, start with: "This is AGNI again. {{resume_context}}"
```

### 12.2 Warning agent system prompt

```
You are AGNI Alert for San Diego County. You are calling about a fire near {{street}}.
Speak in {{language}}, slowly, with pauses. Short words. Say exactly:
"Fire near you. Leave now. Go {{direction}}. The shelter at {{shelter}} has room.
 If you need help getting out, press 1, or say help."
Say it a second time if there is no answer. If the caller presses 1 or says "help" (any
language), call request_rescue and say
"Help is noted. Stay where you are safe and keep your phone on."
If they ask questions, repeat the direction and shelter. Do not add new facts. Keep it
under 45 seconds.
```

### 12.3 Webhook tool schemas

Each tool: method POST, URL `{PUBLIC_BASE_URL}/api/tools/<name>`, header `X-Agni-Tool-Secret: {{secret}}` (store as a secret in ElevenLabs), response time <800 ms, response `{"say": "..."}` plus fields. `conversation_id` comes from the system dynamic variable `{{system__conversation_id}}`.

```
{
 "name": "report_fire",
 "description": "Call as soon as the caller names anything near them. Creates an incident (merges are only suggested to the dispatcher).",
 "type": "webhook",
 "api_schema": {
  "url": "{PUBLIC_BASE_URL}/api/tools/report_fire",
  "method": "POST",
  "request_headers": {
   "X-Agni-Tool-Secret": "<secret ref>"
  },
  "request_body_schema": {
   "type": "object",
   "required": [
    "conversation_id",
    "landmark_text"
   ],
   "properties": {
    "conversation_id": {
     "type": "string",
     "description": "{{system__conversation_id}}"
    },
    "landmark_text": {
     "type": "string",
     "description": "Caller's exact words about where they are: store, school, church, park, road"
    },
    "what_seen": {
     "type": "string",
     "description": "smoke | flames | glow | smell"
    },
    "language": {
     "type": "string",
     "description": "ISO code like en, es"
    }
   }
  }
 }
}
```

```
{
 "name": "add_bearing",
 "description": "Call when the caller says which way the smoke is.",
 "type": "webhook",
 "api_schema": {
  "url": "{PUBLIC_BASE_URL}/api/tools/add_bearing",
  "method": "POST",
  "request_headers": {
   "X-Agni-Tool-Secret": "<secret ref>"
  },
  "request_body_schema": {
   "type": "object",
   "required": [
    "conversation_id",
    "direction_words"
   ],
   "properties": {
    "conversation_id": {
     "type": "string",
     "description": "{{system__conversation_id}}"
    },
    "direction_words": {
     "type": "string",
     "description": "Caller's words, e.g. 'northeast', 'inland', 'toward the ocean'"
    }
   }
  }
 }
}
```

```
{
 "name": "set_needs",
 "description": "Call when you learn who needs help.",
 "type": "webhook",
 "api_schema": {
  "url": "{PUBLIC_BASE_URL}/api/tools/set_needs",
  "method": "POST",
  "request_headers": {
   "X-Agni-Tool-Secret": "<secret ref>"
  },
  "request_body_schema": {
   "type": "object",
   "required": [
    "conversation_id"
   ],
   "properties": {
    "conversation_id": {
     "type": "string",
     "description": "{{system__conversation_id}}"
    },
    "mobility": {
     "type": "boolean",
     "description": "Someone can't walk or needs help moving"
    },
    "people": {
     "type": "integer",
     "description": "Number of people with the caller"
    },
    "notes": {
     "type": "string",
     "description": "Short notes: kids, pets, oxygen"
    }
   }
  }
 }
}
```

```
{
 "name": "send_cam_link",
 "description": "Texts the caller a camera link. Ask first.",
 "type": "webhook",
 "api_schema": {
  "url": "{PUBLIC_BASE_URL}/api/tools/send_cam_link",
  "method": "POST",
  "request_headers": {
   "X-Agni-Tool-Secret": "<secret ref>"
  },
  "request_body_schema": {
   "type": "object",
   "required": [
    "conversation_id"
   ],
   "properties": {
    "conversation_id": {
     "type": "string",
     "description": "{{system__conversation_id}}"
    }
   }
  }
 }
}
```

```
{
 "name": "get_guidance",
 "description": "Call after collecting info, and every time the caller asks what to do.",
 "type": "webhook",
 "api_schema": {
  "url": "{PUBLIC_BASE_URL}/api/tools/get_guidance",
  "method": "POST",
  "request_headers": {
   "X-Agni-Tool-Secret": "<secret ref>"
  },
  "request_body_schema": {
   "type": "object",
   "required": [
    "conversation_id"
   ],
   "properties": {
    "conversation_id": {
     "type": "string",
     "description": "{{system__conversation_id}}"
    }
   }
  }
 }
}
```

```
{
 "name": "request_rescue",
 "description": "Warning agent only. Call when the caller presses 1 or says help in any language.",
 "type": "webhook",
 "api_schema": {
  "url": "{PUBLIC_BASE_URL}/api/tools/request_rescue",
  "method": "POST",
  "request_headers": {
   "X-Agni-Tool-Secret": "<secret ref>"
  },
  "request_body_schema": {
   "type": "object",
   "required": [
    "conversation_id"
   ],
   "properties": {
    "conversation_id": {
     "type": "string",
     "description": "{{system__conversation_id}}"
    },
    "digits": {
     "type": "string",
     "description": "Keys pressed, if any"
    },
    "said_help": {
     "type": "boolean",
     "description": "True if they said help instead of pressing 1"
    }
   }
  }
 }
}
```

Field names follow the ElevenLabs webhook-tool form (name, description, URL, method, headers, body parameters). If the dashboard JSON differs slightly, keep the names and descriptions; they matter to the model. Responses:

```
report_fire   -> {"incident_id":"inc_a1","overflow":true,"say":"Got it. Which way is the smoke from you?"}
                 {"overflow":false,"say":"Please hang up and dial 911."}
                 {"incident_id":"inc_a1","overflow":true,"follow_up":"The Vons on Carmel Valley or on Del Mar Heights?"}
add_bearing   -> {"say":"Thank you. Anyone with you who can't walk?","estimate":{"radius_m":450}}
get_guidance  -> {"say":"Go east on Genesee to RIMAC. It has room. Engine 42 is about 7 minutes away.",   # ETA only from route.eta_s
                  "confirmed":true,"dispatched":true,"should_transfer":false}
request_rescue-> {"say":"Help is noted. Stay where you are safe and keep your phone on."}
```

### 12.4 System tools to enable

| Tool | Setting |
|---|---|
| language_detection | on (EN, ES, plus any the account supports) |
| transfer_to_number | destination `DISPATCHER_PHONE_NUMBER`, type `twilio_warm_conference_transfer`, condition “dispatcher requested or caller asks for a human” |
| end_call | on |
| DTMF input | `dtmf_input_settings` on, timeout 2 s, # terminator |
| voicemail_detection | on for warning agent (leave the message once) |

## 13. Gemini prompts and schemas

Model `gemini-2.5-flash` (set by `GEMINI_MODEL`). SDK `google-genai`. Every call: JSON mode with a schema, 5 s timeout, result cached, raw response saved for eval. Gemini returns boxes as `box_2d = [ymin, xmin, ymax, xmax]` on a 0–1000 scale (per the image-understanding docs); we convert to Andrej's `[x0,y0,x1,y1]` 0–1.

```
# services/gemini.py
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Literal, Optional
client = genai.Client()                                 # reads GEMINI_API_KEY

class Smoke(BaseModel):
    label: Literal["smoke", "no_smoke", "cant_tell"]
    flames_visible: bool
    box_2d: Optional[list[int]]                          # [ymin,xmin,ymax,xmax] 0-1000
    reason: str

def smoke_verdict(jpeg: bytes) -> dict:
    r = client.models.generate_content(
        model=MODEL,
        contents=[types.Part.from_bytes(data=jpeg, mime_type="image/jpeg"), SMOKE_PROMPT],
        config=types.GenerateContentConfig(response_mime_type="application/json",
                                           response_schema=Smoke, temperature=0))
    v = r.parsed
    box = None
    if v.box_2d and v.label == "smoke":
        y0, x0, y1, x1 = v.box_2d
        box = [x0/1000, y0/1000, x1/1000, y1/1000]
    return {"label": v.label, "flames_visible": v.flames_visible, "box": box, "reason": v.reason}
```

### 13.1 Camera check: does this frame support the caller report? (C4)

```
You look at one still from a fixed wildfire camera in San Diego County.
A caller reported smoke near this camera. Decide if wildfire smoke is visible.
- "smoke": a clear plume or column rising from land. Give box_2d around the plume.
- "no_smoke": the view is clear enough to see there is no plume.
- "cant_tell": night, fog, haze, glare, low clouds, lens dirt, or anything ambiguous.
If unsure, answer cant_tell. Never guess smoke. Clouds and marine layer are not smoke.
flames_visible is true only if you see orange flame.
reason: max 20 words, plain English.
```

**Response schema**

```
{
 "label": "smoke|no_smoke|cant_tell",
 "flames_visible": "bool",
 "box_2d": "[ymin,xmin,ymax,xmax] 0-1000 or null",
 "reason": "string ≤20 words"
}
```

### 13.2 Crowd-post classifier (C1)

```
Here is a public post scraped from the web. Is it a first-hand or local report about
a fire or smoke happening now in San Diego County?
- about_fire: true only for current fire/smoke sightings. False for news recaps,
  jokes, fire drills, fireworks, BBQ, old events, or other regions.
- place_text: the place named in the post, copied as written (street, park, area).
  null if none. Do not guess coordinates.
- confidence: high | medium | low.
Post (posted_at={posted_at}): """{text}"""
```

**Response schema**

```
{
 "about_fire": "bool",
 "place_text": "string|null",
 "confidence": "high|medium|low"
}
```

### 13.3 Same-event check (C6)

```
Two people reported a possible fire. Decide if they are describing the same fire.
Report A ({dt_a}, {place_a}): """{transcript_a}"""
Report B ({dt_b}, {place_b}): """{transcript_b}"""
They are {distance_m} m and {dt_s} s apart.
Same fire if they describe the same smoke or flames from nearby places.
Different if the landmarks, direction, or what they see clearly differ.
If you cannot tell, say confidence low.
```

**Response schema**

```
{
 "same_event": "bool",
 "confidence": "high|medium|low",
 "reason": "string ≤25 words"
}
```

### 13.4 Handoff summary (C9)

```
Write what a dispatcher must know before talking to this caller, in one or two
English sentences under 35 words. Include: language, location words, what they see,
who needs help, and which unit is assigned (from the facts given). Only use facts
in the transcript and the facts block. No guesses.
Facts: {facts_json}
Transcript: {transcript}
```

**Response schema**

```
{
 "summary": "string ≤35 words",
 "needs": "[string]",
 "language": "string"
}
```

### 13.6 Landmark extraction (C3)

```
A caller is describing where they are during a possible wildfire in San Diego County.
Pull out the place names they say, copied as said, in the original language.
- landmarks: names of stores, schools, churches, parks, trailheads, roads, intersections.
- relation: behind | next to | across from | near | on | unknown.
- moving: true if they say they are driving or walking.
Do NOT return coordinates, addresses you were not told, or guesses. If none, return [].
Caller words: """{text}"""
```

**Response schema**

```
{
 "landmarks": "[string]",
 "relation": "string",
 "moving": "bool"
}
```

### 13.5 After-action draft (C13)

```
Draft an after-action report for this incident from the event log below.
Use only facts in the log. Use the times exactly as given (Pacific time).
Sections: Summary (2 sentences), Timeline (bullets), Decisions (who approved what),
What worked, What to improve. Mark anything not in the log as "unknown".
Event log: {events_json}
```

**Response schema**

```
{
 "summary": "string",
 "timeline": "[{time, text}]",
 "decisions": "[{time, actor, action}]",
 "worked": "[string]",
 "improve": "[string]"
}
```

## 14. Build order and checkpoints

All times Pacific. Commits only inside the window. Freeze features Sun 9 AM; after that, fixes only.

| When | Block | Done means (test) | Owner |
|---|---|---|---|
| Sat 12:45–2:00 PM | **Voice call ringing.** FastAPI skeleton, `bus.py` + SSE, `report_fire`/`get_guidance` tools, agent + Twilio number, console shows call card from events. | Call the number, speak, see `call.started` + transcript on console. **Gate 2 PM.** | Staff |
| Sat 2:00–3:30 PM | Bearings (C3) + camera wall (C4) live mode + triage.py. | Two scripted bearings → ellipse; 3 real stills with verdicts. | Staff, Andrej |
| Sat 3:30–5:00 PM | **Route + dispatch.** Evidence (C5) + Confirm, routing (C7) with closures + geo.choose, dispatch with idempotency (C8), Uno. | Confirm → route avoids closure, refuses downwind shelter → Approve → one buzz. **Gate 5 PM.** | Staff |
| Sat 5:00–6:30 PM | Bright Data pollers (C1) + classifier; merge (C6) + Undo. | Real SERP rows; 6 calls → 2 incidents. | Staff, Andrej |
| Sat 6:30–8:00 PM | **JUMP IN** (C9): transfer + summary + callback hand-back. | Phone test passes. **Gate 8 PM.** | Staff |
| Sat 8:00–10:00 PM | Spread ring (C10), reverse 911 + Press 1 (C11). Move store to Neon if voice worked by 2 PM. | Team phones ring; press 1 → rescue pin. | Andrej, Staff |
| Sat 10 PM–Sun 1 AM | Surge (C12) on surge-sim, /ops (C14), report (C13), eval run. | 75 calls → 4 fires → 0 duplicates; Reset to Calm works. | Staff |
| Sun 7:00–9:00 AM | Stretch: Tiger, Solana (C15). Only if everything above is green. | Tests in C15. | Staff |
| Sun 9:00–10:45 AM | Freeze. Rehearse 5×. Record ≤3 min video. README. | Full demo twice without touching /ops errors. | All |
| Sun before 11:00 AM | **Submit initial Devpost.** | Link public. | Bijin |
| Sun before 12:00 PM | Final submit; check commit times. | `git log --format=%ci` all inside window. | Bijin |

## 15. 5-minute demo script (mapped to states)

| Time | State | Say / do | What judges see |
|---|---|---|---|
| 0:00–0:25 | v1 S0 / v2 0 | “Eaton fire: 14 reports reached 911 before west Altadena's 3:25 AM evacuation order. 17 of the 18 deaths were there. The reports existed. Nobody fused them.” | Calm map: “28 cameras live · Wind NW 14 mph”. |
| 0:25–0:45 | v2 2 | “Before anyone calls, Bright Data finds public posts.” | Dashed pins, “unverified”, sources linked. |
| 0:45–1:30 | v1 S2 → v2 3 | Judge calls the number on speaker, starts in English, switches to Spanish. | Transcript streams; ES chip; caller pin; camera link. |
| 1:30–1:55 | v2 4 | Second caller (teammate) says “smoke to the south”. | Rays cross → estimate ellipse. |
| 1:55–2:20 | v2 5 → 6 | “AGNI checks the nearest public cameras.” Live tile honestly says no smoke; replay tiles labeled. | Camera wall + evidence stack with empty FIRMS/NIFC dots and reasons. |
| 2:20–2:45 | v2 7 → 8 → 9 | Dispatcher presses Confirm, then Approve. | Route around closure; “Not routing to Torrey Pines HS, downwind”; Uno buzzes on the table. |
| 2:45–3:15 | v2 10 | Press J. Teammate's phone rings, hears summary, talks, hands back. | “You're live with caller 2” → handoff.ended resumed_by agent. |
| 3:15–3:40 | v1 S8 → S11 | /ops Start surge. | “75 calls → 4 fires · 0 duplicate units sent”, Neon branch surge-sim. |
| 3:40–4:20 | v2 11 → 12 | “One more thing.” Send warning. The judge's phone rings in Spanish: press 1. | Ring “30-min estimate”; rescue pin appears when judge presses 1. |
| 4:20–4:45 | v2 13 | Sign the report. | Measured clock, counts, proof panel (or “not measured yet”). |
| 4:45–5:00 | — | “AI listens and finds. Humans decide. Every number you saw was measured.” | Reset to Calm for the next judge. |

## 16. Sponsor map

Rule: each sponsor must earn a screen judges can see.

| Sponsor | Where in AGNI | Screen judges see | Status | Credit |
|---|---|---|---|---|
| ElevenLabs | Intake agent (C2), JUMP IN (C9), warning batch calls + Press 1 (C11) | Judge's own call in Spanish; teammate's phone rings on JUMP IN; judge's phone rings with the warning | Core | Creator month via Discord |
| Gemini (MLH) | Smoke verdict (C4), post classifier (C1), same-event (C6), handoff summary (C9), report draft (C13) | Smoke boxes or “Can't tell”; merge reason; summary; draft report | Core | AI Studio key (free tier) |
| Bright Data (cash prize $1,000) | SERP last hour, Reddit + X scrapers, Browser API for Caltrans QuickMap closures and shelter capacity (C1, C7) | Signals before the first call; route bends around a real closure; “RIMAC has room” is sourced | Core | `sandhacks26` ($100) |
| Neon | Incident store (C6), surge-sim branch (C12), Reset to Calm + practice branches (C14) | Surge on its own branch; instant reset | Core (tonight) | `hackonneon` |
| Tiger Data | Hypertable + continuous aggregate for surge counter and clock (C15) | “live from Tiger Data” caption on the banner | Stretch | — |
| Solana | Devnet memo with SHA-256 of decision log at close (C15) | “Fingerprint on devnet ↗” on the signed report | Stretch | devnet faucet |
| Vultr | Optional VM hosting (C16) | Stable HTTPS URL | Optional | — |

## 17. Honesty rules

- Crowd and AI signals raise priority only. They never confirm, dispatch, or warn.
- Three human buttons: **Confirm fire**, **Approve dispatch**, **Send warning**. Plus **Sign** on the report. Each writes a `decisions` row with the person's name.
- The voice agent never fetches the web mid-call. It reads cached tables only.
- Every estimate says “estimate”: ellipse, straight-line route, spread ring, homes count.
- Live camera tiles show what Gemini sees now, usually “No smoke visible”. Smoke frames are a labeled REPLAY of a past real fire.
- Empty states give a reason: “No detection yet; satellite data can lag hours.” “None mapped yet; doesn't rule out fire.”
- Every source shows its age. Stale data turns amber.
- Numbers on screen come from measured events or `eval.json`. If not measured: “not measured yet”.
- Warning calls go only to opt-in phones (team, consenting judges). Phone numbers show last 4 digits only. No personal data on chain.
- Surge is a simulation and says so on every pin.
- We do not claim to replace 911. AGNI is an overflow helper that sits next to dispatch software.

## 18. Risks and fallbacks

| Risk | Sign | Fallback |
|---|---|---|
| Venue Wi-Fi drops | SSE reconnect banner | Phone hotspot; console catches up from last seq; cached feeds. |
| Tunnel dies | Tool calls fail | Restart tunnel, update agent tool URLs (keep a script); or Vultr VM (C16). |
| Tool latency > 800 ms | Agent pauses | Tools return cached data only; slow work in background tasks. |
| Twilio trial limits (verified numbers only) | Calls to judges fail | Verify judge numbers before the demo or upgrade; else ring a teammate phone and say so. |
| Warm transfer type not available | Transfer errors | Default conference transfer; dispatcher reads the on-screen summary. |
| Hand-back cannot rejoin the same call | — | Callback with context (C9); label it “AGNI calls back”. |
| Gemini timeout / rate limit | Tiles stay “Analyzing” | 5 s cutoff → “not counted”; cache; fewer frames. |
| Bright Data site changes (QuickMap selectors) | 0 closures | Use last cached snapshot with its timestamp; manual closure seed labeled “manual”. |
| ORS/OSRM down | Route > 2 s | Straight line labeled estimate. |
| No smoke on live cameras | Live tile says no smoke | Correct. Use labeled replay for the smoke beat. |
| FIRMS key missing | Satellite row | “Key not set” empty dot. Ask Bijin for FIRMS_MAP_KEY in 1:1. |
| Uno unplugged / wrong port | Station offline chip | On-screen station light; /health shows serial state. |
| Neon not ready tonight | USE_NEON stays 0 | Keep SQLite; surge in temp file labeled “local sim”. |
| Secrets leak | Key in chat or git | Rotate at once; `.env` in `.gitignore`; pre-commit grep for key patterns. |
| Commit outside window | DQ | No fork; fresh `git init` after 10:30 AM Sat; last commit before 12:00 PM Sun. |

## 19. Acceptance checklist

- ☐ Phone call answered <2 s; Spanish switch works; transcript on console <1 s.
- ☐ Tool p95 <800 ms in logs; no Bright Data request during any call (mock asserts).
- ☐ Two bearings → estimate ellipse labeled “estimate”.
- ☐ 3 nearest ALERTCalifornia cameras load; live verdict honest; replay labeled.
- ☐ Evidence stack shows FIRMS/NIFC empty dots with reasons; Confirm writes a decision row.
- ☐ Route avoids a closure; downwind shelter refused with reason; fallback line labeled estimate <2 s.
- ☐ Approve twice → 1 dispatch, 1 event, 1 buzz.
- ☐ 6 calls → 2 incidents; Undo merge works; duplicate units 0.
- ☐ JUMP IN rings dispatcher with summary; hand-back emits handoff.ended resumed_by agent.
- ☐ Spread ring labeled 30-min estimate, moves downwind.
- ☐ Warning reaches opt-in phones; Press 1 → rescue pin <2 s.
- ☐ Surge: 75 calls / 90 s on surge-sim; surge.stats every 1 s; main untouched.
- ☐ Report times match events; human signs; proof panel reads eval.json or says not measured.
- ☐ /ops Reset to Calm <5 s.
- ☐ SSE reconnect replays from last seq with no duplicates.
- ☐ No secrets in repo, PDF, or rooms; .env.example names only.
- ☐ All commits inside the window; Devpost submitted before 11:00 AM Sun.

## 20. Links and verification status

Checked from the build computer on Sat Nov 14, 2026 (~1 PM PT) with an HTTP GET following redirects. “OK” = page returned 200. Other codes are noted; a 403/429 usually means the site blocks scripts, not that the page is missing.

| URL | Status |
|---|---|
| [https://ai.google.dev/gemini-api/docs/image-understanding](https://ai.google.dev/gemini-api/docs/image-understanding) | OK |
| [https://ai.google.dev/gemini-api/docs/quickstart](https://ai.google.dev/gemini-api/docs/quickstart) | OK |
| [https://ai.google.dev/gemini-api/docs/structured-output](https://ai.google.dev/gemini-api/docs/structured-output) | OK |
| [https://aistudio.google.com/api-keys](https://aistudio.google.com/api-keys) | OK |
| [https://api-docs.neon.tech/reference/createprojectbranch](https://api-docs.neon.tech/reference/createprojectbranch) | OK |
| [https://brightdata.com/cp/start](https://brightdata.com/cp/start) | OK |
| [https://brightdata.com/products/web-scraper/reddit](https://brightdata.com/products/web-scraper/reddit) | OK |
| [https://brightdata.com/products/web-scraper/twitter](https://brightdata.com/products/web-scraper/twitter) | OK |
| [https://cameras.alertcalifornia.org/](https://cameras.alertcalifornia.org/) | OK |
| [https://console.cloud.timescale.com/signup](https://console.cloud.timescale.com/signup) | OK |
| [https://data-nifc.opendata.arcgis.com/datasets/nifc::wfigs-current-interagency-fire-perimeters](https://data-nifc.opendata.arcgis.com/datasets/nifc::wfigs-current-interagency-fire-perimeters) | OK |
| [https://developer.mozilla.org/en-US/docs/Web/API/DeviceOrientationEvent](https://developer.mozilla.org/en-US/docs/Web/API/DeviceOrientationEvent) | OK |
| [https://docs.arduino.cc/language-reference/en/functions/communication/serial/](https://docs.arduino.cc/language-reference/en/functions/communication/serial/) | OK |
| [https://docs.brightdata.com/api-reference/rest-api/scraper/asynchronous-requests](https://docs.brightdata.com/api-reference/rest-api/scraper/asynchronous-requests) | OK |
| [https://docs.brightdata.com/api-reference/scrapers/synchronous-requests](https://docs.brightdata.com/api-reference/scrapers/synchronous-requests) | OK |
| [https://docs.brightdata.com/introduction](https://docs.brightdata.com/introduction) | OK |
| [https://docs.brightdata.com/products/scraping-browser/code-examples](https://docs.brightdata.com/products/scraping-browser/code-examples) | OK |
| [https://docs.brightdata.com/products/scraping-browser/introduction](https://docs.brightdata.com/products/scraping-browser/introduction) | OK |
| [https://docs.brightdata.com/products/serp-api/parsed-json-results](https://docs.brightdata.com/products/serp-api/parsed-json-results) | OK |
| [https://docs.brightdata.com/products/serp-api/send-your-first-request](https://docs.brightdata.com/products/serp-api/send-your-first-request) | OK |
| [https://docs.tigerdata.com/use-timescale/latest/continuous-aggregates/](https://docs.tigerdata.com/use-timescale/latest/continuous-aggregates/) | OK |
| [https://docs.tigerdata.com/use-timescale/latest/hypertables/](https://docs.tigerdata.com/use-timescale/latest/hypertables/) | OK |
| [https://docs.vultr.com/](https://docs.vultr.com/) | OK |
| [https://docs.vultr.com/products/compute/cloud-compute](https://docs.vultr.com/products/compute/cloud-compute) | OK |
| [https://elevenlabs.io/app/sign-up](https://elevenlabs.io/app/sign-up) | OK |
| [https://elevenlabs.io/docs/eleven-agents/api-reference/batch-calling/create](https://elevenlabs.io/docs/eleven-agents/api-reference/batch-calling/create) | OK |
| [https://elevenlabs.io/docs/eleven-agents/api-reference/integrations/twilio/outbound-call](https://elevenlabs.io/docs/eleven-agents/api-reference/integrations/twilio/outbound-call) | OK |
| [https://elevenlabs.io/docs/eleven-agents/customization/multimodal-input](https://elevenlabs.io/docs/eleven-agents/customization/multimodal-input) | OK |
| [https://elevenlabs.io/docs/eleven-agents/customization/personalization/dynamic-variables](https://elevenlabs.io/docs/eleven-agents/customization/personalization/dynamic-variables) | OK |
| [https://elevenlabs.io/docs/eleven-agents/customization/tools/system-tools/language-detection](https://elevenlabs.io/docs/eleven-agents/customization/tools/system-tools/language-detection) | OK |
| [https://elevenlabs.io/docs/eleven-agents/customization/tools/system-tools/transfer-to-number](https://elevenlabs.io/docs/eleven-agents/customization/tools/system-tools/transfer-to-number) | OK |
| [https://elevenlabs.io/docs/eleven-agents/customization/tools/webhook-tools](https://elevenlabs.io/docs/eleven-agents/customization/tools/webhook-tools) | OK |
| [https://elevenlabs.io/docs/eleven-agents/overview](https://elevenlabs.io/docs/eleven-agents/overview) | OK |
| [https://elevenlabs.io/docs/eleven-agents/phone-numbers/batch-calls](https://elevenlabs.io/docs/eleven-agents/phone-numbers/batch-calls) | OK |
| [https://elevenlabs.io/docs/eleven-agents/phone-numbers/sip-trunking](https://elevenlabs.io/docs/eleven-agents/phone-numbers/sip-trunking) | not checked |
| [https://elevenlabs.io/docs/eleven-agents/phone-numbers/twilio-integration/native-integration](https://elevenlabs.io/docs/eleven-agents/phone-numbers/twilio-integration/native-integration) | OK |
| [https://elevenlabs.io/docs/eleven-agents/workflows/post-call-webhooks](https://elevenlabs.io/docs/eleven-agents/workflows/post-call-webhooks) | OK |
| [https://firms.modaps.eosdis.nasa.gov/api/area/](https://firms.modaps.eosdis.nasa.gov/api/area/) | OK |
| [https://firms.modaps.eosdis.nasa.gov/api/map_key/](https://firms.modaps.eosdis.nasa.gov/api/map_key/) | OK |
| [https://giscience.github.io/openrouteservice/api-reference/](https://giscience.github.io/openrouteservice/api-reference/) | OK |
| [https://googleapis.github.io/python-genai/](https://googleapis.github.io/python-genai/) | OK |
| [https://neon.com/docs/extensions/postgis](https://neon.com/docs/extensions/postgis) | OK |
| [https://neon.com/docs/guides/reset-from-parent](https://neon.com/docs/guides/reset-from-parent) | OK |
| [https://neon.com/docs/introduction/branching](https://neon.com/docs/introduction/branching) | OK |
| [https://neon.com/docs/manage/branches](https://neon.com/docs/manage/branches) | OK |
| [https://neon.com/docs/reference/cli-branches](https://neon.com/docs/reference/cli-branches) | OK |
| [https://neon.com/signup](https://neon.com/signup) | OK |
| [https://numpy.org/doc/stable/](https://numpy.org/doc/stable/) | OK |
| [https://openrouteservice.org/dev/#/api-docs](https://openrouteservice.org/dev/#/api-docs) | OK |
| [https://openrouteservice.org/dev/#/signup](https://openrouteservice.org/dev/#/signup) | OK |
| [https://project-osrm.org/docs/v5.24.0/api/](https://project-osrm.org/docs/v5.24.0/api/) | OK |
| [https://pyserial.readthedocs.io/en/latest/](https://pyserial.readthedocs.io/en/latest/) | OK |
| [https://quickmap.dot.ca.gov/](https://quickmap.dot.ca.gov/) | OK |
| [https://www.alertcalifornia.org/](https://www.alertcalifornia.org/) | OK |
| [https://www.alertsandiego.org/](https://www.alertsandiego.org/) | not checked |
| [https://www.latimes.com/california/story/2025-01-20/in-much-of-altadena-evacuation-orders-came-hours-after-the-fire-arrived](https://www.latimes.com/california/story/2025-01-20/in-much-of-altadena-evacuation-orders-came-hours-after-the-fire-arrived) | OK |
| [https://www.latimes.com/california/story/2025-04-16/911-logs-west-altadena-eaton-fire-evacuations](https://www.latimes.com/california/story/2025-04-16/911-logs-west-altadena-eaton-fire-evacuations) | OK |
| [https://www.twilio.com/docs/voice](https://www.twilio.com/docs/voice) | OK |
| [https://www.twilio.com/try-twilio](https://www.twilio.com/try-twilio) | OK |
| [https://www.vultr.com/register/](https://www.vultr.com/register/) | 403 · site blocks scripts; open in a browser |
| [https://www.weather.gov/documentation/services-web-api](https://www.weather.gov/documentation/services-web-api) | OK |

### Not verified (treat with care)

- Bijin's exact hackathon credit links (ElevenLabs Discord claim, Bright Data, Neon, Tiger, Solana, Vultr, Twilio): not on the box. Yellow slots left blank. Codes sandhacks26 and hackonneon came from teammates relaying Bijin's room message.
- `https://www.vultr.com/register/`: returns 403 to scripts; not confirmed.
- OpenRouteService endpoint `POST https://api.openrouteservice.org/v2/directions/driving-car/geojson` and `options.avoid_polygons`: from ORS docs knowledge, not called live (needs a key).
- Neon create-branch REST path `/api/v2/projects/{project_id}/branches`: the docs page loads; exact path not called (needs a key). The CLI reset command was read from the Neon docs page.
- ElevenLabs webhook-tool JSON field names in Section 12.3 (`api_schema`, `request_body_schema`, `request_headers`): shape follows the docs form; check against the dashboard export.
- Triggering transfer_to_number from the console (contextual update / should_transfer flag): design choice, test on a real call by 8 PM. Hand-back is a callback, not a rejoin.
- Bright Data Reddit/X dataset IDs: must be copied from the Bright Data control panel; none invented here. QuickMap page selectors must be found by hand.
- Gemini `box_2d` 0–1000 format: from the image-understanding docs pattern; confirm on the first real call.
- FastAPI built-in SSE (`fastapi.sse`) needs FastAPI ≥ 0.135 per the docs; the spec code uses `StreamingResponse`, which works on any version.
- Eaton fire numbers come from LA Times stories (linked); the “17 of 18” wording reflects later reporting that all but one of 18 deaths were in west Altadena.
