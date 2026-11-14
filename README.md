# AGNI

AGNI is a 911 overflow support prototype. It accepts a report only when the dispatch center enables overflow. A dispatcher confirms each fire, approves each unit dispatch, and approves each warning.

AGNI does not replace 911 or the dispatch center. It is not connected to a public 911 system. Do not use this prototype for emergency response.

## Start the API

Python 3.11 or later is required.

```sh
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
make seed
make dev
```

The API starts on `http://127.0.0.1:8000`. Mock mode is on by default. It does not call external services in mock mode. The local database is `data/agni-api.sqlite`.

In a second terminal, start the console:

```sh
cd frontend
npm install
npm run dev
```

Open the Vite address. To show live camera stills and public feeds, set `AGNI_MOCK=0` in local `.env`. Live integrations remain unverified until the live checks pass.

## Work status

See [STATUS.md](STATUS.md) for task progress, live verification and setup that needs an account owner. See [DECISIONS.md](DECISIONS.md) for implementation choices.

## Development

```sh
make test
```

Unit tests must run offline. Do not put keys in chat or source control. Add local keys to `.env` only. Do not enable outbound calls until the opt-in list and phone integrations are set up.
