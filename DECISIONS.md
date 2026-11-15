# AGNI decisions

- Use SQLite and local fixtures until the Neon task. This keeps the app usable without accounts or network access.
- Default `AGNI_MOCK=1` and `OVERFLOW_ENABLED=0`. The brief requires offline-safe behavior and an explicit overflow switch.
- Keep the package name `backend/agni/` (not `backend/app/`) to avoid a mid-hackathon rename; contracts and routes still follow Part B.
- Keep the AGNI camera, feed, geography and bearing modules inside this independent AGNI repository. AGNI has its own FastAPI entry point and database.
- Do not enable live outbound calls until the opt-in list and account setup are present.
- Follow Build Spec v2: Solana is cut. Tiger Data is a stretch option only if the surge counter needs it.
- Preserve straight-line routes as estimates. Do not speak an ETA unless a real route supplies it.
- Coordinates: cache-first (`seed/landmarks.json` + optional `seed/cached_landmarks.json`), then region-boxed Photon/Nominatim via `geo.search`. Caller/tool lat+lon → `location_src=caller` immediately. Gemini extracts landmark text only; it never invents coordinates. Miss → honest “Location: not yet”.
- Keep the committed landmark cache as a clearly labeled mock fixture. A Bright Data landmark import replaces it for live use.
- The spread ring is a labeled 30-minute, 100 m-cell estimate. It is a dispatcher review aid, not a perimeter forecast.
- A warning batch records human approval and only selects opted-in contacts inside the reviewed ring. The current adapter never dials a phone.
- The local surge rehearsal uses a separate temporary SQLite file and writes measured output to an ignored `backend/sim/sim.json` file.
- JUMP IN hand-back uses a callback model (`resumed_by: agent`, `mode: callback`) because warm transfer drops the agent from the call (FINAL review note).
- Dispatcher console stays React + Vite with Leaflet CARTO dark tiles instead of rewriting to static HTML; event contract and keyboard map match Part B.
- **Map tiles (Nov 14 night):** Spec says CARTO `dark_matter`, but `basemaps.cartocdn.com/dark_matter/...` returns 404. Use HTTPS `dark_all` (`https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png`). Esri World Dark Gray Canvas paints repeating "Map data not yet available" watermarks — do not use it. `invalidateSize` on resize/layout.
- Service adapters live under `backend/agni/services/` and select mock vs live only through `config.MOCK` / env keys.
- Camera SMS: when `TWILIO_CONTENT_SID` is set, `_twilio_sms` sends `ContentSid` + `ContentVariables={"1": short_url}` (no Body). Freeform Body remains the fallback. Trial accounts cannot create Content Templates (Content API 20003) and reject freeform (572006); upgrade is required before custom camera-link SMS works.
- `make demo` drives the storyboard path through TestClient against an isolated `data/agni-demo.sqlite` so the main practice DB is untouched.
- **PM friction pass (Nov 14 eve):** Callers refuse typing long URLs. Demo path is SMS tap-link OR a **4-letter CODE** shown giant on the console with **Copy short link** for the dispatcher to text from their phone. Agent must speak `send_cam_link.say` verbatim and never dictate hosts.
- **Live-call console:** During a live call, Confirm (Enter) stays the primary action (`live_confirm`). Cam CODE + landmark appear in “Do this next”; JUMP IN is secondary.
- **Guidance after intake:** `get_guidance` returns a concrete shelter direction from `routing.choose_shelter` (cardinal + name) when a landmark pin exists; immobile callers get “stay put / prioritized” instead.
- **Tunnel ops:** `scripts/keep_live.sh` must not `pkill` a healthy serveo SSH. Restart API by killing only the `:8000` listener. Re-source `.env` via Python (not `source .env`) — shell metacharacters in values break bash.
- **Console WOW pass (Nov 14 eve):** Three ambient/interaction layers, secondary to Confirm:
  1. **Public ears box** — glass panel under metrics (was “Local news”); reads `/api/state` `signals` + SSE `signal.new` (cached/fixture OK). Never triggers Bright Data from the UI.
  2. **Incoming call pop** — on `call.started`, non-blocking toast; auto-selects the fire; Open / Jump in / Dismiss. Appear within 1 s of the event.
  3. **AGNI stuck → takeover** — new SSE `call.needs_human` (reason + call_id). Emitted when: silence ≥25 s on a live call with no fresh transcript, caller asks for a human, or `set_needs` notes request a dispatcher. Client also derives silence stuck as a backup. UI: banner + next-step CTA “press J”; JUMP IN uses existing `/api/calls/{id}/jump-in` and honest-fails if `DISPATCHER_PHONE_NUMBER` unset.

## Console eye-path (Nov 14 eve) — Jobs/Elon pass
- One hero instruction: top mode banner. Walkthrough collapsed by default; no triplicate dial copy.
- Left = the call only. Right news = Bright Data cache · never dispatch (dimmed during live call).
- Bottom CCTV: idle = Waiting for a call pin; after lat/lon = nearest ALERTCalifornia stills (or honest fail).
- Map: flyTo zoom 15 on lat/lon. Marker layer must not panTo (it cancelled zoom).
- Landmark resolve: if Gemini returns empty, match spoken words against cached landmark list.

## Bright Data WOW uses (Nov 14 eve) — noble, not a news sidebar
Judges should feel Bright Data saves time and wrong paths, not that we scraped Google. Three demo-visible uses, all cache-first (`seed/cached_*.json`); never live scrape during a call:

1. **Public ears (hear residents earlier)** — Right panel renamed from “Local news” to **Public ears (Bright Data)** with mission line. Nearby cache posts attach gray/unverified to a pin; when timestamps exist, show **First public mention → call · ~N min earlier**. Crowd never greens a pin or dispatches.
2. **Safe path (closures + shelter capacity)** — On Confirm → route card: chips **Avoids Caltrans closure (Bright Data)** and **Shelter capacity from Bright Data** when QuickMap/shelter cache rows exist. Reduces sending units into closed roads and callers into full/downwind shelters.
3. **Honest landmark pin** — Prefer Bright Data / seed landmark cache; else region geocode; else caller GPS. Chip names the source. Never invent.

Ops may optionally refresh SERP when keys are set and no call is live; default path stays fixtures.
