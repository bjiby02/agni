.PHONY: test dev seed demo eval live-check live-ready surge agents

test:
	cd backend && AGNI_MOCK=1 ../.venv/bin/python3 -m unittest discover -s tests -v

dev:
	cd backend && ../.venv/bin/uvicorn agni.main:app --reload --host 127.0.0.1 --port 8000

seed:
	cd backend && ../.venv/bin/python3 -c 'from agni.db import init; from agni import pollers; init(); pollers.ensure_demo_hazards()'

demo:
	AGNI_MOCK=1 .venv/bin/python3 scripts/demo.py

eval:
	AGNI_MOCK=1 .venv/bin/python3 backend/ml/eval/run_eval.py

surge:
	cd backend && AGNI_MOCK=1 ../.venv/bin/python3 sim/surge.py --n 75 --seconds 90

live-check:
	.venv/bin/python3 scripts/live_check.py

live-ready:
	.venv/bin/python3 scripts/live_ready.py

agents:
	.venv/bin/python3 scripts/create_agents.py
