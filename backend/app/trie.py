from __future__ import annotations

import bisect
import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from backend.app.metrics import metrics


@dataclass
class Suggestion:
    query: str
    count: int
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query, "count": self.count, "score": round(self.score, 4)}


@dataclass
class TrieNode:
    children: dict[str, TrieNode] = field(default_factory=dict)
    top_k: list[Suggestion] = field(default_factory=list)


class SuggestionTrie:
    def __init__(self, top_k: int = 10) -> None:
        self.top_k = top_k
        self.root = TrieNode()
        self._lock = threading.RLock()
        self._query_counts: dict[str, int] = {}

    def build_from_records(self, records: list[tuple[str, int, int, int]]) -> None:
        with self._lock:
            self.root = TrieNode()
            self._query_counts.clear()
            for query, global_count, weekly_count, daily_count in records:
                score = 0.6 * global_count + 0.3 * weekly_count + 0.1 * daily_count
                self._insert(query, global_count, score)

    def _insert(self, query: str, count: int, score: float) -> None:
        self._query_counts[query] = count
        node = self.root
        suggestion = Suggestion(query=query, count=count, score=score)
        for ch in query:
            node = node.children.setdefault(ch, TrieNode())
            self._update_top_k(node, suggestion)

    def _update_top_k(self, node: TrieNode, suggestion: Suggestion) -> None:
        existing = {s.query: s for s in node.top_k}
        if suggestion.query in existing:
            existing[suggestion.query] = suggestion
        else:
            existing[suggestion.query] = suggestion
        ranked = sorted(existing.values(), key=lambda s: (-s.score, -s.count, s.query))
        node.top_k = ranked[: self.top_k]

    def update_query(self, query: str, global_count: int, weekly_count: int, daily_count: int) -> None:
        score = 0.6 * global_count + 0.3 * weekly_count + 0.1 * daily_count
        with self._lock:
            self._insert(query, global_count, score)

    def suggest(self, prefix: str, limit: int | None = None, mode: str = "basic") -> list[Suggestion]:
        limit = limit or self.top_k
        with self._lock:
            node = self.root
            for ch in prefix:
                if ch not in node.children:
                    return []
                node = node.children[ch]

            suggestions = list(node.top_k)
            if mode == "basic":
                suggestions.sort(key=lambda s: (-s.count, s.query))
            else:
                suggestions.sort(key=lambda s: (-s.score, -s.count, s.query))
            return suggestions[:limit]

    @property
    def size(self) -> int:
        return len(self._query_counts)


def normalize_query(raw: str | None) -> str:
    if raw is None:
        return ""
    return " ".join(raw.strip().lower().split())


def normalize_prefix(raw: str | None) -> str:
    return normalize_query(raw)


def all_prefixes(query: str) -> list[str]:
    return [query[: i + 1] for i in range(len(query))]
