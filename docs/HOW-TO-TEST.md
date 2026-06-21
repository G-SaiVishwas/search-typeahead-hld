# How the App Works & How to Test It

Use this checklist before submitting the assignment.

## What the app does (30-second overview)

1. You type in the search box → the UI calls `GET /suggest?q=<prefix>` (debounced ~150ms).
2. The backend checks **Redis cache** (if Docker is running) → then an **in-memory trie** → then **SQLite** for long-tail prefixes.
3. You submit a search → `POST /search` returns `{"message":"Searched"}` immediately; counts update via a **background batch writer**.
4. **Trending** uses basic ranking (global count) or enhanced ranking (0.6×global + 0.3×weekly + 0.1×daily).
5. **Cache debug** shows which Redis node owns a prefix key (consistent hashing).

## Start the full stack

### Prerequisites

- Python 3.9+
- Node.js 18+
- **Redis on 3 ports** — either Docker Desktop (`docker compose up -d`) or Homebrew Redis (`./scripts/start_redis_local.sh`; `start.sh` tries Docker first, then local fallback)

### One command

```bash
cd Project_HLD
chmod +x start.sh stop.sh
./start.sh
```

Wait ~45 seconds on first run (trie build). Then open:

| URL | Purpose |
|-----|---------|
| http://localhost:5173 | React UI |
| http://localhost:8000/docs | Swagger API docs |
| http://localhost:8000/health | Health + cache node status |

Verify cache is enabled:

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

You should see `"cache_enabled": true` and all three nodes `"redis-0": true`, `"redis-1": true`, `"redis-2": true`.

If `cache_enabled` is false, start Docker Desktop and run:

```bash
docker compose up -d
# restart backend (or ./stop.sh && ./start.sh)
```

### Stop

```bash
./stop.sh
```

---

## Manual UI test checklist

Do these in the browser at http://localhost:5173:

| # | Action | Expected result |
|---|--------|-----------------|
| 1 | Load the page | Search box, Search button, Trending panel visible |
| 2 | Type `goog` | Dropdown shows up to 10 suggestions; top result is `google` |
| 3 | Click a suggestion | Search runs; green text `API response: Searched` |
| 4 | Type `goog` and press **Enter** | Same searched message |
| 5 | Press **ArrowDown** then **Enter** on a suggestion | Selected suggestion is searched |
| 6 | Toggle **Trending ranking** | Suggestion order may change vs Basic |
| 7 | Check **Trending Searches** panel | List of 10 trending queries on the right |
| 8 | Click a trending item | Runs search and shows `Searched` |
| 9 | Clear input / type nothing | No error; empty dropdown |
| 10 | Type nonsense prefix `zzzzxyz` | “No suggestions for this prefix” |

Optional: while typing, note the gray **Cache node** line (shows HIT/MISS when Redis is enabled).

---

## API test checklist (terminal)

Run with backend on port 8000:

```bash
# 1. Health
curl -s http://localhost:8000/health | python3 -m json.tool

# 2. Suggestions (prefix, sorted by count)
curl -s "http://localhost:8000/suggest?q=goog" | python3 -m json.tool

# 3. Empty prefix (graceful)
curl -s "http://localhost:8000/suggest?q=" | python3 -m json.tool

# 4. Case insensitive
curl -s "http://localhost:8000/suggest?q=GOOG" | python3 -m json.tool

# 5. Search submission
curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query":"my test search"}' | python3 -m json.tool

# 6. Cache debug (assignment requirement)
curl -s "http://localhost:8000/cache/debug?prefix=goog" | python3 -m json.tool

# 7. Trending
curl -s "http://localhost:8000/trending?limit=10" | python3 -m json.tool

# 8. Basic vs trending compare
curl -s "http://localhost:8000/trending/compare?prefix=go" | python3 -m json.tool

# 9. Batch write demo
python backend/scripts/replay.py --limit 3000
curl -s http://localhost:8000/metrics | python3 -m json.tool
```

**Batch write success:** `write_reduction_ratio` should be **> 0.99** (e.g. 3000 events → ~11 DB writes).

**Cache success:** Repeat the same suggest call twice; second response should show `"hit": true` in the `cache` field and `/cache/debug` should show `"hit": true`.

```bash
curl -s "http://localhost:8000/suggest?q=face" > /dev/null
curl -s "http://localhost:8000/suggest?q=face" | python3 -m json.tool
curl -s "http://localhost:8000/cache/debug?prefix=face" | python3 -m json.tool
```

---

## Consistent hashing demo

```bash
curl -s -X POST http://localhost:8000/cache/demo/rebalance | python3 -m json.tool
```

Shows how many sample prefixes remap when a node is added/removed (~1/N keys).

---

## Automated API smoke test

```bash
cd Project_HLD
source .venv/bin/activate
python backend/scripts/smoke_test.py
```

Expect all lines to say `PASS`.

---

## Submission artifacts (already in repo)

| File | Contents |
|------|----------|
| `README.md` | Setup & run |
| `docs/architecture.md` | System diagram |
| `docs/api.md` | Endpoint reference |
| `docs/performance.md` | Latency & batch metrics |
| `docs/design-choices.md` | Trade-offs |
| `docs/HOW-TO-TEST.md` | This guide |

Private notes (not pushed): `DESIGN.md` (gitignored).

---

## Common issues

| Problem | Fix |
|---------|-----|
| `cache_enabled: false` | Start Docker Desktop → `docker compose up -d` → restart backend |
| Backend slow first start | Normal (~45s trie build); subsequent starts same unless DB changes |
| Frontend can’t reach API | Ensure backend on :8000; Vite proxies `/api` → backend |
| Port already in use | `./stop.sh` then `./start.sh` |

---

## Demo script for viva (5 minutes)

1. `./start.sh` → open UI, type `goog`, show suggestions.
2. Submit search → show `Searched` response.
3. `curl /cache/debug?prefix=goog` → explain assigned Redis node.
4. Toggle Trending ranking in UI → show order change.
5. `python backend/scripts/replay.py --limit 3000` → `curl /metrics` → explain write reduction.
