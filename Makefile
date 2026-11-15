.PHONY: test dev seed demo eval live-check surge agents

test:
	cd backend && AGNI_MOCK=1 python3 -m unittest discover -s tests -v

dev:
	cd backend && AGNI_MOCK=1 uvicorn agni.main:app --reload --host 127.0.0.1 --port 8000

seed:
	cd backend && python3 -c 'from agni.db import init; init()'

demo:
	cd backend && AGNI_MOCK=1 python3 ../scripts/demo.py

eval:
	cd backend && python3 ml/eval/run_eval.py

agents:
	python3 scripts/create_agents.py

surge:
	cd backend && AGNI_MOCK=1 python3 sim/surge.py --n 75 --seconds 90

live-check:
	@python3 scripts/live_check.py
