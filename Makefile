.PHONY: test dev seed demo eval live-check

test:
	cd backend && AGNI_MOCK=1 python3 -m unittest discover -s tests -v

dev:
	cd backend && AGNI_MOCK=1 uvicorn agni.main:app --reload --host 127.0.0.1 --port 8000

seed:
	cd backend && python3 -c 'from agni.db import init; init()'

demo:
	@echo "Demo replay is not implemented yet. See STATUS.md (T17)."

eval:
	@echo "Evaluation harness is not implemented yet. See STATUS.md (T15)."

surge:
	cd backend && AGNI_MOCK=1 python3 sim/surge.py --n 75 --seconds 90

live-check:
	@python3 scripts/live_check.py
