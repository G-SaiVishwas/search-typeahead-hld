from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone

from backend.app.cache import PrefixCache
from backend.app.config import Settings, get_settings
from backend.app.metrics import metrics
from backend.app.store import QueryStore
from backend.app.trie import SuggestionTrie, all_prefixes

logger = logging.getLogger(__name__)


class BatchWriteManager:
    def __init__(
        self,
        store: QueryStore,
        trie: SuggestionTrie,
        cache: PrefixCache,
        settings: Settings | None = None,
    ) -> None:
        self.store = store
        self.trie = trie
        self.cache = cache
        self.settings = settings or get_settings()
        self._buffer: list[tuple[str, datetime]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_flush = time.time()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="batch-flusher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self.flush(force=True)

    def enqueue(self, query: str) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._buffer.append((query, now))
            metrics.record_search_received(1)

    def _run(self) -> None:
        while not self._stop.is_set():
            time.sleep(0.25)
            with self._lock:
                pending = len(self._buffer)
            elapsed = time.time() - self._last_flush
            if pending >= self.settings.batch_flush_size or (
                pending > 0 and elapsed >= self.settings.batch_flush_interval_seconds
            ):
                self.flush(force=True)

    def flush(self, force: bool = False) -> int:
        with self._lock:
            if not self._buffer:
                return 0
            if not force and len(self._buffer) < self.settings.batch_flush_size:
                return 0
            batch = self._buffer
            self._buffer = []

        deltas: dict[str, int] = defaultdict(int)
        for query, _ in batch:
            deltas[query] += 1

        updated = self.store.apply_deltas(dict(deltas))
        metrics.record_search_flushed(len(batch))
        self._last_flush = time.time()

        prefixes_to_invalidate: set[str] = set()
        for record in updated:
            self.trie.update_query(
                record.query,
                record.global_count,
                record.weekly_count,
                record.daily_count,
            )
            prefixes_to_invalidate.update(all_prefixes(record.query))

        if prefixes_to_invalidate:
            invalidated = self.cache.invalidate_prefixes(sorted(prefixes_to_invalidate))
            logger.info(
                "Flushed %s events into %s unique queries; invalidated cache keys %s",
                len(batch),
                len(deltas),
                invalidated,
            )

        return len(batch)

    @property
    def pending(self) -> int:
        with self._lock:
            return len(self._buffer)
