# Search Typeahead System

HLD101 assignment implementation: prefix suggestions, distributed Redis cache with consistent hashing, trending searches, batch writes, and a React UI.

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker Desktop (for 3 Redis cache nodes)

## One-command start

```bash
chmod +x start.sh
./start.sh
```

Then open:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs

Stop everything:

```bash
./stop.sh
```

**Note:** Start Docker Desktop before `./start.sh`, or ensure Homebrew `redis-server` is installed for the local fallback. Without all 3 Redis nodes, the API still works but distributed caching is disabled.

## Manual setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d
python backend/scripts/ingest.py

uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
cd frontend && npm install && npm run dev
```

## Dataset

Place the provided CSV files in `data/`:

- `data/typeahed_dataset.csv` — aggregated query counts (seed data)
- `data/raw_queries.csv` — raw search events with timestamps (replay / batch demo)

Ingestion creates `data/typeahead.db` automatically on first run.

## Demo commands

```bash
# Replay raw events into POST /search to demonstrate batch write reduction
python backend/scripts/replay.py --limit 10000

# Inspect metrics
curl http://localhost:8000/metrics

# Cache debug for a prefix
curl "http://localhost:8000/cache/debug?prefix=goog"

# Compare basic vs trending ranking for a prefix
curl "http://localhost:8000/trending/compare?prefix=go"
```

## Documentation

- **[How to Test (start here)](docs/HOW-TO-TEST.md)** — how the app works + submission checklist
- [Architecture](docs/architecture.md)
- [API Reference](docs/api.md)
- [Performance Report](docs/performance.md)
- [Design Choices](docs/design-choices.md)

## Project structure

```
backend/app/          FastAPI service, trie, cache, batch writer
backend/scripts/      ingest + replay utilities
frontend/             React + Vite UI
data/                 CSV datasets + SQLite DB
docs/                 Submission documentation
docker-compose.yml    3 Redis nodes
start.sh              One-command local startup
```
