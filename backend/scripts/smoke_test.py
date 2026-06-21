#!/usr/bin/env python3
"""Run API smoke tests against a running backend."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE = "http://127.0.0.1:8000"
failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}: {detail}")
        failures.append(name)


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=60.0)

    r = client.get("/health")
    check("GET /health status", r.status_code == 200, r.text)
    health = r.json()
    check("health trie loaded", health.get("trie_queries", 0) > 0)
    check("health db seeded", health.get("db_rows", 0) >= 1_000_000)

    r = client.get("/suggest")
    check("GET /suggest empty q", r.status_code == 200 and r.json()["suggestions"] == [])

    r = client.get("/suggest", params={"q": "GOOG"})
    check(
        "GET /suggest case insensitive",
        r.status_code == 200 and any(s["query"] == "google" for s in r.json()["suggestions"]),
    )

    r = client.get("/suggest", params={"q": "goog", "limit": 10})
    data = r.json()
    suggestions = data["suggestions"]
    check("GET /suggest <=10 results", len(suggestions) <= 10)
    check("GET /suggest sorted by count", suggestions == sorted(suggestions, key=lambda s: -s["count"]))
    check("GET /suggest top result google", suggestions and suggestions[0]["query"] == "google")

    r = client.get("/suggest", params={"q": "zzzznomatch12345"})
    check("GET /suggest no-match prefix", r.json()["suggestions"] == [])

    r = client.get("/suggest", params={"q": "go", "mode": "trending"})
    check("GET /suggest trending mode", r.status_code == 200 and len(r.json()["suggestions"]) > 0)

    r = client.post("/search", json={"query": "smoke test query"})
    check("POST /search", r.status_code == 200 and r.json() == {"message": "Searched"})

    r = client.post("/search", json={"query": ""})
    check("POST /search rejects empty", r.status_code == 422)

    r = client.post("/batch/flush")
    check("POST /batch/flush", r.status_code == 200)

    r = client.get("/trending", params={"limit": 5, "mode": "basic"})
    check("GET /trending basic", r.status_code == 200 and len(r.json()["trending"]) == 5)

    r = client.get("/trending", params={"limit": 5, "mode": "trending"})
    check("GET /trending enhanced", r.status_code == 200 and len(r.json()["trending"]) == 5)

    r = client.get("/trending/compare", params={"prefix": "go"})
    body = r.json()
    check("GET /trending/compare", r.status_code == 200 and "basic" in body and "trending" in body)

    r = client.get("/cache/debug", params={"prefix": "goog"})
    debug = r.json()
    check("GET /cache/debug has hit field", "hit" in debug)
    check("GET /cache/debug has assigned_node", "assigned_node" in debug)

    if health.get("cache_enabled"):
        r1 = client.get("/suggest", params={"q": "face"})
        r2 = client.get("/suggest", params={"q": "face"})
        check("cache second request hits", r2.json().get("cache", {}).get("hit") is True)
        r = client.post("/cache/demo/rebalance")
        check("POST /cache/demo/rebalance", r.status_code == 200)
    else:
        print("WARN  Redis cache disabled (start Docker for full cache tests)")

    r = client.get("/metrics")
    metrics = r.json()
    check("GET /metrics", r.status_code == 200 and "latency_ms" in metrics)

    print("\nSUMMARY:", len(failures), "failures")
    if failures:
        print("Failed:", ", ".join(failures))
        return 1
    print("All smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
