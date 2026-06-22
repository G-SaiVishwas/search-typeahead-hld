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

**Source:** AOL User Session Collection (500k) — real anonymized web search logs
(March–May 2006), published on Kaggle:
https://www.kaggle.com/datasets/dineshydv/aol-user-session-collection-500k

Two derived CSVs are used (place them in `data/`):

- `data/typeahed_dataset.csv` — 1,244,453 unique queries aggregated into
  `Query, Global Count, Weekly Count, Daily Count, Trending Score` (seed data).
- `data/raw_queries.csv` — 2,969,752 raw `Query, QueryTime` search events
  (replayed to demonstrate batch writes and recency).

Ingestion (`backend/scripts/ingest.py`, run automatically on first start) bulk-loads
`typeahed_dataset.csv` into SQLite at `data/typeahead.db`. The trie is then built
from that table at backend startup.

Derived-file mirrors (Google Drive):
- raw_queries: https://drive.google.com/file/d/1XIbyjLBMxoSptTvZXeK65uIVr-RJ2LWZ/view?usp=sharing
- typeahed_dataset: https://drive.google.com/file/d/1931-OYamJ8ggTzkpPG1nt1R_SDbh1HDg/view?usp=sharing

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
