from __future__ import annotations

import bisect
import hashlib
import json
import logging
import threading
from dataclasses import dataclass
from typing import Any

import redis

from backend.app.config import Settings, get_settings
from backend.app.metrics import metrics

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CacheOwnership:
    cache_key: str
    node_name: str
    ring_hash: int
    ring_position: int
    total_vnodes: int


class ConsistentHashRing:
    def __init__(
        self,
        nodes: dict[str, redis.Redis],
        vnodes: int = 150,
    ) -> None:
        self.vnodes = vnodes
        self.clients = nodes
        self.ring: list[int] = []
        self.hash_to_node: dict[int, str] = {}
        self._lock = threading.RLock()
        for name in nodes:
            self.add_node(name)

    @staticmethod
    def _hash(value: str) -> int:
        digest = hashlib.md5(value.encode("utf-8")).hexdigest()
        return int(digest, 16)

    def add_node(self, name: str) -> None:
        if name not in self.clients:
            raise KeyError(f"Unknown node client: {name}")
        with self._lock:
            for i in range(self.vnodes):
                h = self._hash(f"{name}:vnode:{i}")
                if h not in self.hash_to_node:
                    bisect.insort(self.ring, h)
                    self.hash_to_node[h] = name

    def remove_node(self, name: str, drop_client: bool = False) -> None:
        with self._lock:
            to_remove = [h for h, n in self.hash_to_node.items() if n == name]
            for h in to_remove:
                del self.hash_to_node[h]
                idx = bisect.bisect_left(self.ring, h)
                if idx < len(self.ring) and self.ring[idx] == h:
                    self.ring.pop(idx)
            if drop_client:
                self.clients.pop(name, None)

    def get_node_name(self, key: str) -> str:
        with self._lock:
            if not self.ring:
                raise RuntimeError("Consistent hash ring has no nodes")
            h = self._hash(key)
            idx = bisect.bisect_left(self.ring, h)
            if idx == len(self.ring):
                idx = 0
            ring_hash = self.ring[idx]
            return self.hash_to_node[ring_hash]

    def get_ownership(self, key: str) -> CacheOwnership:
        with self._lock:
            if not self.ring:
                raise RuntimeError("Consistent hash ring has no nodes")
            h = self._hash(key)
            idx = bisect.bisect_left(self.ring, h)
            if idx == len(self.ring):
                idx = 0
            ring_hash = self.ring[idx]
            return CacheOwnership(
                cache_key=key,
                node_name=self.hash_to_node[ring_hash],
                ring_hash=ring_hash,
                ring_position=idx,
                total_vnodes=len(self.ring),
            )

    def get_client(self, key: str) -> tuple[str, redis.Redis]:
        name = self.get_node_name(key)
        return name, self.clients[name]

    def get(self, key: str) -> tuple[str, Any | None, bool]:
        try:
            name, client = self.get_client(key)
            raw = client.get(key)
        except redis.RedisError:
            metrics.record_cache_miss()
            return "unavailable", None, False
        if raw is None:
            metrics.record_cache_miss()
            return name, None, False
        metrics.record_cache_hit()
        return name, json.loads(raw), True

    def set(self, key: str, value: Any, ttl: int) -> str:
        try:
            name, client = self.get_client(key)
            client.setex(key, ttl, json.dumps(value))
            return name
        except redis.RedisError:
            return "unavailable"

    def delete(self, key: str) -> str:
        try:
            name, client = self.get_client(key)
            client.delete(key)
            return name
        except redis.RedisError:
            return "unavailable"

    def delete_many(self, keys: list[str]) -> dict[str, int]:
        deleted: dict[str, int] = {}
        for key in keys:
            node = self.delete(key)
            deleted[node] = deleted.get(node, 0) + 1
        return deleted

    def ping_all(self) -> dict[str, bool]:
        status: dict[str, bool] = {}
        for name, client in self.clients.items():
            try:
                status[name] = client.ping()
            except redis.RedisError:
                status[name] = False
        return status

    def node_names(self) -> list[str]:
        return list(self.clients.keys())


class PrefixCache:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.enabled = False
        self.ring: ConsistentHashRing | None = None

    def connect(self) -> None:
        clients: dict[str, redis.Redis] = {}
        for idx, (host, port) in enumerate(self.settings.redis_node_list):
            name = f"redis-{idx}"
            clients[name] = redis.Redis(
                host=host,
                port=port,
                decode_responses=True,
                socket_connect_timeout=2,
            )
        ring = ConsistentHashRing(clients, vnodes=self.settings.cache_vnodes)
        health = ring.ping_all()
        if not all(health.values()):
            logger.warning("Not all Redis nodes are healthy: %s", health)
            self.enabled = False
            self.ring = None
            return
        self.ring = ring
        self.enabled = True

    def cache_key(self, prefix: str, mode: str) -> str:
        return f"suggest:{mode}:{prefix}"

    def get_suggestions(self, prefix: str, mode: str) -> tuple[str, list[dict] | None, bool]:
        if not self.enabled or self.ring is None or not prefix:
            return "none", None, False
        key = self.cache_key(prefix, mode)
        node, value, hit = self.ring.get(key)
        return node, value, hit

    def set_suggestions(self, prefix: str, mode: str, suggestions: list[dict]) -> str:
        if not self.enabled or self.ring is None or not prefix:
            return "none"
        key = self.cache_key(prefix, mode)
        return self.ring.set(key, suggestions, self.settings.cache_ttl_seconds)

    def invalidate_prefixes(self, prefixes: list[str], modes: list[str] | None = None) -> dict[str, int]:
        if not self.enabled or self.ring is None:
            return {}
        modes = modes or ["basic", "trending"]
        keys = [self.cache_key(p, m) for p in prefixes for m in modes]
        return self.ring.delete_many(keys)

    def debug(self, prefix: str, mode: str = "basic") -> dict[str, Any]:
        if not self.enabled or self.ring is None:
            return {
                "enabled": False,
                "prefix": prefix,
                "mode": mode,
                "cache_key": self.cache_key(prefix, mode) if prefix else "",
                "assigned_node": "none",
                "resolved_node": "none",
                "hit": False,
                "ring_hash": None,
                "ring_position": None,
                "total_vnodes": 0,
                "value": None,
                "nodes": [],
                "message": "Cache layer not connected (start Docker Compose Redis nodes and restart backend)",
            }
        key = self.cache_key(prefix, mode)
        ownership = self.ring.get_ownership(key)
        node, value, hit = self.ring.get(key)
        return {
            "enabled": True,
            "prefix": prefix,
            "mode": mode,
            "cache_key": key,
            "assigned_node": ownership.node_name,
            "resolved_node": node,
            "hit": hit,
            "ring_hash": ownership.ring_hash,
            "ring_position": ownership.ring_position,
            "total_vnodes": ownership.total_vnodes,
            "value": value,
            "nodes": self.ring.node_names(),
        }

    def health(self) -> dict[str, bool]:
        if not self.enabled or self.ring is None:
            return {}
        return self.ring.ping_all()
