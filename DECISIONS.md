# AGNI decisions

- Use SQLite and local fixtures until the Neon task. This keeps the app usable without accounts or network access.
- Default `AGNI_MOCK=1` and `OVERFLOW_ENABLED=0`. The brief requires offline-safe behavior and an explicit overflow switch.
- Keep the AGNI camera, feed, geography and bearing modules inside this independent AGNI repository. AGNI has its own FastAPI entry point and database.
- Do not enable live outbound calls until the opt-in list and account setup are present.
- Follow Build Spec v2: Solana is cut. Tiger Data is a stretch option only if the surge counter needs it.
- Preserve straight-line routes as estimates. Do not speak an ETA unless a real route supplies it.
- Coordinates come only from the cached landmark list. Gemini extracts landmark text only; it does not geocode.
- Keep the committed landmark cache as a clearly labeled mock fixture. A Bright Data landmark import replaces it for live use.
- The spread ring is a labeled 30-minute, 100 m-cell estimate. It is a dispatcher review aid, not a perimeter forecast.
- A warning batch records human approval and only selects opted-in contacts inside the reviewed ring. The current adapter never dials a phone.
- The local surge rehearsal uses a separate temporary SQLite file and writes measured output to an ignored `backend/sim/sim.json` file.
- Code tree: the Ares helpers AGNI uses (`swarm.py`, `geo.py`, `feeds.py`, `directory.py`) live in `backend/core/`. The rest of the old Ares app is archived in `legacy/ares/` and nothing imports it.
- Transfer trigger: the console cannot force an ElevenLabs transfer mid-call, so JUMP IN sets `should_transfer` on `get_guidance` and the prompt tells the agent to run `transfer_to_number`. Hand-back is a callback. Both are LIVE-UNVERIFIED.
- Caller phone numbers are stored only in `call_contacts`, used only for the callback, and scrubbed from any Gemini prompt.
- Bearings from merged incidents cross on the surviving incident, so the estimate appears when a dispatcher accepts the merge.
- Practice values are labeled where they show: the wind (from 20°, toward 200°), the road closure snapshot and the 555 warning numbers. None of them is presented as observed.
- The demo replay call is synthetic and labeled "Replay". It runs through the same tool handlers as a live call.
- The console rebuilds its state from `/api/stream?since=0` on load, so a refresh restores the screen.
- Merge precision in `eval.json` comes from 20 synthetic hand-labeled pairs, and the proof panel says so.
- Postgres: one SQL dialect in the app, translated for Postgres in `backend/agni/pg.py` (placeholders, `strftime('now')`, `INSERT OR REPLACE/IGNORE`, two-argument `MIN`, `lastrowid`). Times stay ISO text on both so the report hash matches. PostGIS columns are generated from lat/lon when the extension exists.
- The caller camera page is a hash route in the same console app, served by FastAPI from `frontend/dist`, so one tunnel URL covers everything.
- Bright Data runs on a timer and waits while an inbound call from the last 15 minutes has not ended. In practice mode /ops can load the synthetic fixture at any time because it makes no network request.
- Posts are classified by Gemini when a key is set, otherwise by a keyword fallback that is labeled as such.

- Caltrans closures: QuickMap's Full Closures layer is drawn from public KML files listed in `/config/layers.json` (checked by hand 2026-11-14). We read those files instead of clicking the map through the Browser API, because they hold the closure paths and do not break when the page layout changes. They go through the Web Unlocker zone when `BRIGHTDATA_UNLOCKER_ZONE` is set, otherwise directly. Only full closures are kept; a closure with no path is stored as a point and not used for routing, so no geometry is invented.
- Tiger Data and Solana are not built: Solana is cut in Build Spec FINAL, and the surge counter does not need Tiger.
