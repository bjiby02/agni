# AGNI

AGNI is a crisis-intelligence command system for emergency teams. It combines rapid incident intake, hazard-aware routing, visual triage, responder assignment, and a dispatcher-controlled human override in one live command console.

> **Safety boundary:** AGNI is a hackathon prototype and simulation tool. It does not contact emergency services or replace trained dispatchers. In a real emergency, call local emergency services.

## What works today

- Seeded incident, responder, and hazard data for a deterministic demo
- Priority calculation from smoke, flames, and blocked-exit signals
- Nearest available responder selection that penalizes hazard-intersecting paths
- Dispatcher override state and operator notes
- Server-Sent Events endpoint for live dashboard updates
- Tactical command-console UI with mock/simulation mode

## Architecture

```text
React command console  <-- SSE / REST -->  FastAPI application
                                            |-- dispatch service
                                            |-- hazard + unit repositories
                                            |-- provider adapters (vision, voice, data)
                                            `-- PostgreSQL/PostGIS (production target)
```

The local starter intentionally uses in-memory demo data. Provider integrations are isolated behind adapters so API credentials can be added without entangling dispatch logic.

## Run locally

Backend (Python 3.11+):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn agni.main:app --reload --port 8000
```

Frontend (Node 20+):

```bash
cd frontend
npm install
npm run dev
```

Open the frontend URL printed by Vite. It defaults to `http://localhost:5173` and calls the API at `http://localhost:8000`.

## Environment

Copy `.env.example` to `.env` when integrating providers. Never commit keys. The application remains usable in deterministic demo mode when credentials are absent.

For sponsor-specific account provisioning and secure integration sequencing, see [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md).

## API surface

- `GET /health`
- `GET /api/incidents`
- `GET /api/incidents/{id}`
- `POST /api/incidents/{id}/vision`
- `POST /api/incidents/{id}/dispatch`
- `POST /api/incidents/{id}/override`
- `GET /api/events`

## Development checks

```bash
cd backend
python -m unittest discover -s tests -v
```

