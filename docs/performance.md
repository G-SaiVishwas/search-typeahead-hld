# Performance Report

Measured on a local Mac dev machine with the implementation in this repository.

## How to reproduce

```bash
./start.sh
# wait for backend startup (~45s first time while trie builds)

# Warm suggest cache path
for i in $(seq 1 25); do curl -s "http://localhost:8000/suggest?q=goog" > /dev/null; done

# Replay searches for batch-write demo
python backend/scripts/replay.py --limit 3000

curl -s http://localhost:8000/metrics | python3 -m json.tool
```

## Measured results (sample run)

| Metric | Value |
|--------|-------|
| `/suggest` p50 latency | ~0.5–2 ms (trie path, cache disabled) |
| `/suggest` p95 latency | ~28 ms (includes occasional SQLite fallback) |
| Cache hit rate | Requires all 3 Redis nodes (`docker compose up -d`) |
| DB writes after 3,000 search events | 11 transactions |
| Write reduction ratio | **0.9963** (99.63% fewer writes vs naive per-event writes) |
| Batch flush count | 11 flushes for 3,000 events |

## Interpretation

- **Latency:** The in-memory trie serves common prefixes with sub-millisecond lookups after warmup. Startup builds a trie for queries with `global_count >= 10` (~42k queries) in ~21 seconds; long-tail prefixes fall back to SQLite `LIKE` queries.
- **Cache:** With Docker running, three Redis nodes shard prefix keys via consistent hashing. `/cache/debug?prefix=goog` shows node ownership and hit/miss status.
- **Batch writes:** `POST /search` returns immediately; a background thread flushes every 500 events or 2 seconds. Replaying 3,000 events produced only 11 SQLite write transactions instead of 3,000.

## Failure-mode note

Buffered events live in memory until flush. A process crash before flush loses pending events. See `docs/design-choices.md` for mitigation options (WAL, durable queue, shorter flush interval).
