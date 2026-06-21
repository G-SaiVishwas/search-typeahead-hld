PYTHON ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PY := $(VENV)/bin/python
UVICORN := $(VENV)/bin/uvicorn

.PHONY: setup redis ingest backend frontend run stop clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -r requirements.txt
	cd frontend && npm install

redis:
	docker compose up -d

ingest:
	$(PY) backend/scripts/ingest.py

backend:
	$(UVICORN) backend.app.main:app --host 0.0.0.0 --port 8000 --reload

frontend:
	cd frontend && npm run dev

run: redis setup ingest backend

stop:
	docker compose down
	-pkill -f "uvicorn backend.app.main:app" || true

clean:
	rm -rf $(VENV) frontend/node_modules frontend/dist data/*.db .pids
