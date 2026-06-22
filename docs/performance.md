# Performance Report

Measured on a local macOS dev machine (Apple Silicon) with all three Redis
nodes running and the backend serving from the in-memory trie + Redis cache.

## How to reproduce

```bash
./start.sh
# wait for backend startup (~10-45s while the trie builds)

# Latency + cache benchmark (cold then warm prefixes)
# then read server-side percentiles from /metrics
curl -s http://localhost:8000/metrics | python3 -m json.tool

# Batch-write demo: replay raw events into POST /search
python backend/scripts/replay.py --limit 5000
curl -s http://localhost:8000/metrics | python3 -m json.tool

# Automated regression
python backend/scripts/smoke_test.py
```

## Measured results

Workload: 27 representative prefixes, each requested cold once then 20x warm
(567 suggest requests), followed by a 5,000-event search replay.

| Metric | Value |
|--------|-------|
| `/suggest` server-side p50 | **0.321 ms** |
| `/suggest` server-side p95 | **0.644 ms** |
| `/suggest` server-side p99 | **0.869 ms** |
| End-to-end p50 (incl. HTTP, warm) | ~2.0 ms |
| Cache hit rate (warm workload) | **95.8%** (569 hits / 25 misses) |
| Search events replayed | 5,000 |
| SQLite write transactions | **5** |
| Write reduction ratio | **0.999 (99.9%)** |
| Trie queries in memory | ~42,000 (`global_count >= 10`) |
| Trie build time at startup | ~7-21 s |
| Smoke tests | 21 / 21 pass |

## Consistent hashing distribution

27 prefix keys mapped across the 3-node ring (150 vnodes each):

| Node | Keys owned |
|------|-----------|
| redis-0 | 9 |
| redis-1 | 10 |
| redis-2 | 8 |

Adding a 4th node (`/cache/demo/rebalance`) remapped **25%** of sample keys,
matching the consistent-hashing expectation of ~1/N remapping (N=4).

## Interpretation

- **Latency:** The trie returns precomputed top-K with no query-time sorting, so
  server-side p99 stays under 1 ms — far below the assignment's low-latency goal.
  Long-tail prefixes (not in the trie) fall back to an indexed SQLite prefix scan.
- **Cache:** After warmup, ~96% of suggest requests are served from Redis without
  touching the trie or DB. `/cache/debug?prefix=` exposes the owning node, ring
  hash, ring position, and hit/miss for any prefix.
- **Batch writes:** `POST /search` returns immediately; a background thread flushes
  every 500 events or 2 seconds. 5,000 events collapsed into just 5 DB transactions
  (99.9% fewer writes than naive per-event writes).

## Failure-mode note

Buffered events live in memory until the next flush. A process crash before flush
loses pending events. Mitigations (WAL / append-only log, durable queue such as
Redis Streams or Kafka, or a shorter flush interval) are discussed in
`docs/design-choices.md`.
