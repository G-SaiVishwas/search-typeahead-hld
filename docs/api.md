# API Reference

Base URL: `http://localhost:8000`

## GET /suggest

Return up to 10 prefix-matching suggestions.

**Query parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `q` | string | optional | Prefix to match (case-insensitive) |
| `limit` | int | 10 | Max suggestions (1-10) |
| `mode` | string | `basic` | `basic` (global count) or `trending` (recency-aware score) |

**Example**

```bash
curl "http://localhost:8000/suggest?q=goog&mode=basic"
```

**Response**

```json
{
  "prefix": "goog",
  "mode": "basic",
  "cache": {"node": "redis-0", "hit": false},
  "suggestions": [
    {"query": "google", "count": 32396, "score": 32396}
  ]
}
```

Edge cases:
- Missing or empty `q` returns `{"suggestions": []}` with HTTP 200.
- Prefixes with no matches return an empty list.

## POST /search

Submit a search and record the query via the batch writer.

**Body**

```json
{"query": "google"}
```

**Response**

```json
{"message": "Searched"}
```

## GET /cache/debug

Debug cache routing for a prefix.

**Query parameters**

| Name | Type | Description |
|------|------|-------------|
| `prefix` | string | Prefix to inspect |
| `mode` | string | `basic` or `trending` |

**Example**

```bash
curl "http://localhost:8000/cache/debug?prefix=goog"
```

## GET /trending

Return global trending queries.

**Query parameters**

| Name | Default | Description |
|------|---------|-------------|
| `limit` | 10 | Number of results |
| `mode` | `trending` | `basic` or `trending` |

## GET /metrics

Runtime metrics: cache hit rate, DB read/write counts, batch flush stats, suggest latency percentiles.

## GET /health

Service health including trie size, DB row count, Redis node ping status.

## POST /batch/flush

Force-flush pending search events (useful for demos/tests).

## GET /trending/compare

Compare basic vs trending rankings for the same prefix (demo endpoint).

## POST /cache/demo/rebalance

Demonstrates consistent hashing remapping when a node is added/removed.
