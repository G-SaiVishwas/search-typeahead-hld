from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.app.batch import BatchWriteManager
from backend.app.cache import PrefixCache
from backend.app.config import get_settings
from backend.app.metrics import metrics
from backend.app.store import QueryStore
from backend.app.trending import records_to_suggestions, trie_suggestions_to_response
from backend.app.trie import SuggestionTrie, normalize_prefix, normalize_query

logger = logging.getLogger(__name__)

store = QueryStore()
trie = SuggestionTrie(top_k=get_settings().trie_top_k)
cache = PrefixCache()
batch_manager = BatchWriteManager(store, trie, cache)


def bootstrap_data() -> None:
    settings = get_settings()
    store.init_schema()
    if store.row_count() == 0:
        from backend.scripts.ingest import ingest

        logger.info("Empty database detected; running ingestion")
        ingest(settings.csv_path)

    logger.info("Building trie from SQLite (min_count=%s)...", settings.trie_min_count)
    records = [
        (r.query, r.global_count, r.weekly_count, r.daily_count)
        for r in store.iter_queries(min_count=settings.trie_min_count)
    ]
    global trie
    trie.build_from_records(records)
    batch_manager.trie = trie
    logger.info("Trie ready with %s high-frequency queries (SQLite fallback for long tail)", trie.size)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    bootstrap_data()
    try:
        cache.connect()
        if cache.enabled:
            logger.info("Connected to Redis cache nodes: %s", cache.health())
        else:
            logger.warning("Redis cache disabled; serving from trie/SQLite only")
    except Exception as exc:
        logger.warning("Redis unavailable; continuing without cache: %s", exc)
    batch_manager.start()
    yield
    batch_manager.stop()


app = FastAPI(title="Typeahead Search API", version="1.0.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)


class SearchResponse(BaseModel):
    message: str


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "trie_queries": trie.size,
        "db_rows": store.row_count(),
        "cache_enabled": cache.enabled,
        "cache_nodes": cache.health(),
        "pending_batch_events": batch_manager.pending,
    }


@app.get("/metrics")
def get_metrics() -> dict:
    return metrics.snapshot()


@app.get("/suggest")
def suggest(
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=10),
    mode: Literal["basic", "trending"] = Query(default="basic"),
) -> dict:
    started = time.perf_counter()
    prefix = normalize_prefix(q)

    if not prefix:
        return {"prefix": "", "mode": mode, "suggestions": []}

    node, cached, hit = cache.get_suggestions(prefix, mode)
    if hit and cached is not None:
        elapsed_ms = (time.perf_counter() - started) * 1000
        metrics.record_suggest_latency(elapsed_ms)
        return {
            "prefix": prefix,
            "mode": mode,
            "cache": {"node": node, "hit": True},
            "suggestions": cached[:limit],
        }

    suggestions = trie.suggest(prefix, limit=limit, mode=mode)
    if not suggestions:
        records = store.prefix_search(prefix, limit=limit, mode=mode)
        suggestions = records_to_suggestions(records, mode)
    payload = trie_suggestions_to_response(suggestions)
    assigned_node = cache.set_suggestions(prefix, mode, payload)
    elapsed_ms = (time.perf_counter() - started) * 1000
    metrics.record_suggest_latency(elapsed_ms)

    return {
        "prefix": prefix,
        "mode": mode,
        "cache": {"node": assigned_node, "hit": False},
        "suggestions": payload,
    }


@app.post("/search", response_model=SearchResponse)
def search(body: SearchRequest) -> SearchResponse:
    query = normalize_query(body.query)
    if not query:
        raise HTTPException(status_code=400, detail="Query must not be empty")
    batch_manager.enqueue(query)
    return SearchResponse(message="Searched")


@app.post("/batch/flush")
def flush_batch() -> dict:
    flushed = batch_manager.flush(force=True)
    return {"flushed_events": flushed, "pending": batch_manager.pending}


@app.get("/trending")
def trending(
    limit: int = Query(default=10, ge=1, le=50),
    mode: Literal["basic", "trending"] = Query(default="trending"),
) -> dict:
    if mode == "basic":
        records = store.top_by_global(limit)
    else:
        records = store.top_by_trending(limit)
    suggestions = records_to_suggestions(records, mode)
    return {
        "mode": mode,
        "trending": trie_suggestions_to_response(suggestions),
    }


@app.get("/cache/debug")
def cache_debug(
    prefix: str = Query(..., min_length=0),
    mode: Literal["basic", "trending"] = Query(default="basic"),
) -> dict:
    normalized = normalize_prefix(prefix)
    return cache.debug(normalized, mode)


@app.get("/trending/compare")
def trending_compare(prefix: str = Query(default="go"), limit: int = Query(default=10, ge=1, le=10)) -> dict:
    normalized = normalize_prefix(prefix)
    basic = trie.suggest(normalized, limit=limit, mode="basic")
    enhanced = trie.suggest(normalized, limit=limit, mode="trending")
    return {
        "prefix": normalized,
        "basic": trie_suggestions_to_response(basic),
        "trending": trie_suggestions_to_response(enhanced),
    }


@app.post("/cache/demo/rebalance")
def cache_demo_rebalance() -> dict:
    if not cache.enabled or cache.ring is None:
        raise HTTPException(status_code=503, detail="Cache not enabled")

    sample_prefixes = ["go", "app", "face", "video", "news", "shop", "music", "game"]
    before = {p: cache.ring.get_node_name(cache.cache_key(p, "basic")) for p in sample_prefixes}

    temp_name = "redis-demo"
    cache.ring.clients[temp_name] = cache.ring.clients["redis-0"]
    cache.ring.add_node(temp_name)
    after_add = {p: cache.ring.get_node_name(cache.cache_key(p, "basic")) for p in sample_prefixes}

    cache.ring.remove_node(temp_name)
    after_remove = {p: cache.ring.get_node_name(cache.cache_key(p, "basic")) for p in sample_prefixes}

    changed_on_add = sum(1 for p in sample_prefixes if before[p] != after_add[p])
    changed_on_remove = sum(1 for p in sample_prefixes if after_add[p] != after_remove[p])

    return {
        "sample_size": len(sample_prefixes),
        "before": before,
        "after_add_node": after_add,
        "after_remove_node": after_remove,
        "changed_on_add": changed_on_add,
        "changed_on_remove": changed_on_remove,
        "approx_remap_ratio_add": round(changed_on_add / len(sample_prefixes), 3),
    }
