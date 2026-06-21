from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class MetricsCollector:
    cache_hits: int = 0
    cache_misses: int = 0
    db_reads: int = 0
    db_writes: int = 0
    search_events_received: int = 0
    search_events_flushed: int = 0
    flush_count: int = 0
    suggest_latencies_ms: list[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_cache_hit(self) -> None:
        with self._lock:
            self.cache_hits += 1

    def record_cache_miss(self) -> None:
        with self._lock:
            self.cache_misses += 1

    def record_db_read(self) -> None:
        with self._lock:
            self.db_reads += 1

    def record_db_write(self) -> None:
        with self._lock:
            self.db_writes += 1

    def record_search_received(self, count: int = 1) -> None:
        with self._lock:
            self.search_events_received += count

    def record_search_flushed(self, count: int) -> None:
        with self._lock:
            self.search_events_flushed += count
            self.flush_count += 1

    def record_suggest_latency(self, elapsed_ms: float) -> None:
        with self._lock:
            self.suggest_latencies_ms.append(elapsed_ms)
            if len(self.suggest_latencies_ms) > 10000:
                self.suggest_latencies_ms = self.suggest_latencies_ms[-5000:]

    @staticmethod
    def _percentile(values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        idx = int(round((pct / 100.0) * (len(ordered) - 1)))
        return round(ordered[idx], 3)

    def snapshot(self) -> dict:
        with self._lock:
            total_cache = self.cache_hits + self.cache_misses
            hit_rate = (self.cache_hits / total_cache) if total_cache else 0.0
            write_reduction = 0.0
            if self.search_events_received:
                write_reduction = 1.0 - (self.db_writes / self.search_events_received)
            return {
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "cache_hit_rate": round(hit_rate, 4),
                "db_reads": self.db_reads,
                "db_writes": self.db_writes,
                "search_events_received": self.search_events_received,
                "search_events_flushed": self.search_events_flushed,
                "flush_count": self.flush_count,
                "write_reduction_ratio": round(write_reduction, 4),
                "latency_ms": {
                    "p50": self._percentile(self.suggest_latencies_ms, 50),
                    "p95": self._percentile(self.suggest_latencies_ms, 95),
                    "p99": self._percentile(self.suggest_latencies_ms, 99),
                    "samples": len(self.suggest_latencies_ms),
                },
            }


metrics = MetricsCollector()
