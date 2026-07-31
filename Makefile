PY := backend/.venv/Scripts/python.exe
SCENARIO ?= heatwave
SEED ?= 42

.PHONY: setup demo api test test-all run record models clean

setup:
	cd backend && uv sync

api:
	cd backend && .venv/Scripts/python.exe -m uvicorn services.api.main:app --reload --port 8000

demo:
	docker compose up --build

run:
	cd backend && .venv/Scripts/python.exe -m services.sim.run --scenario $(SCENARIO) --seed $(SEED)

record:
	cd backend && .venv/Scripts/python.exe -m services.sim.record --all --seed $(SEED)

test:
	cd backend && .venv/Scripts/python.exe -m pytest -q -m "not slow"

test-all:
	cd backend && .venv/Scripts/python.exe -m pytest -q

models:
	cd backend && .venv/Scripts/python.exe -c "import json; from services.api.models_registry import read_artifacts; print(json.dumps(read_artifacts(), indent=2))"

clean:
	cd backend && rm -rf .pytest_cache && find . -name __pycache__ -type d -exec rm -rf {} +
