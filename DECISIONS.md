# AGNI decisions

- Use SQLite and local fixtures until the Neon task. This keeps the app usable without accounts or network access.
- Default `AGNI_MOCK=1` and `OVERFLOW_ENABLED=0`. The brief requires offline-safe behavior and an explicit overflow switch.
- Keep the package name `backend/agni/` (not `backend/app/`) to avoid a mid-hackathon rename; contracts and routes still follow Part B.
- Keep the AGNI camera, feed, geography and bearing modules inside this independent AGNI repository. AGNI has its own FastAPI entry point and database.
- Do not enable live outbound calls until the opt-in list and account setup are present.
- Follow Build Spec v2: Solana is cut. Tiger Data is a stretch option only if the surge counter needs it.
- Preserve straight-line routes as estimates. Do not speak an ETA unless a real route supplies it.
- Coordinates come only from the cached landmark list. Gemini extracts landmark text only; it does not geocode.
- Keep the committed landmark cache as a clearly labeled mock fixture. A Bright Data landmark import replaces it for live use.
- The spread ring is a labeled 30-minute, 100 m-cell estimate. It is a dispatcher review aid, not a perimeter forecast.
- A warning batch records human approval and only selects opted-in contacts inside the reviewed ring. The current adapter never dials a phone.
- The local surge rehearsal uses a separate temporary SQLite file and writes measured output to an ignored `backend/sim/sim.json` file.
- JUMP IN hand-back uses a callback model (`resumed_by: agent`, `mode: callback`) because warm transfer drops the agent from the call (FINAL review note).
- Dispatcher console stays React + Vite with Leaflet CARTO dark_matter tiles instead of rewriting to static HTML; event contract and keyboard map match Part B.
- Service adapters live under `backend/agni/services/` and select mock vs live only through `config.MOCK` / env keys.
- `make demo` drives the storyboard path through TestClient against an isolated `data/agni-demo.sqlite` so the main practice DB is untouched.
