# Design Choices

## Primary store: SQLite

**Choice:** SQLite file at `data/typeahead.db`.

**Why:** Zero external dependency, easy local setup, sufficient for assignment scale (1.24M rows).

**Trade-off:** Not horizontally scalable; acceptable for this project.

## Suggestion index: Trie with precomputed top-K

**Choice:** In-memory trie where each node stores the top 10 completions in its subtree. Queries with `global_count >= 10` are loaded into the trie; long-tail matches fall back to SQLite prefix search.

**Why:** Meets the assignment latency goal by avoiding query-time sorting for common prefixes. Startup stays under ~30 seconds locally.

## Cache: 3 Redis nodes + app-level consistent hashing

**Choice:** Three standalone Redis instances (Docker Compose), sharded by our own hash ring with 150 vnodes per node.

**Why:** Makes consistent hashing explicit and inspectable via `/cache/debug`. Avoids hiding routing inside Redis Cluster.

**Trade-off:** Requires Docker; we provide `start.sh` for one-command startup.

## Trending: dual ranking modes

**Basic:** sort by `global_count`.

**Enhanced:** score = `0.6 * global + 0.3 * weekly + 0.1 * daily`.

Live searches increment all counters; periodic decay reduces daily/weekly values so spikes fade.

**Trade-off:** Enhanced mode is fresher but more complex to explain and maintain.

## Batch writes

**Choice:** In-memory buffer flushed every 500 events or 2 seconds.

**Why:** Dramatically reduces SQLite write transactions during search bursts.

**Failure trade-off:** Buffered events are lost on crash before flush. Mitigations documented in DESIGN.md: smaller flush window, append-only WAL, or durable queue (Kafka/Redis stream).

## Content safety

AOL dataset may contain sensitive queries. Optional blocklist can be applied at ingest and serve time for demo UI polish.

## Documentation split

- `docs/` — pushed submission artifacts
- `DESIGN.md` — private extended notes (gitignored)
