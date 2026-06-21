from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Iterable

from backend.app.config import Settings, get_settings
from backend.app.metrics import metrics


@dataclass(frozen=True)
class QueryRecord:
    query: str
    global_count: int
    weekly_count: int
    daily_count: int
    last_seen: str | None = None

    @property
    def trending_score(self) -> float:
        return 0.6 * self.global_count + 0.3 * self.weekly_count + 0.1 * self.daily_count


class QueryStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.db_path = Path(self.settings.db_path)
        self._lock = threading.RLock()

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS queries (
                    query TEXT PRIMARY KEY,
                    global_count INTEGER NOT NULL DEFAULT 0,
                    weekly_count INTEGER NOT NULL DEFAULT 0,
                    daily_count INTEGER NOT NULL DEFAULT 0,
                    last_seen TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_queries_global_count
                    ON queries(global_count DESC);
                """
            )

    def row_count(self) -> int:
        with self.connect() as conn:
            metrics.record_db_read()
            row = conn.execute("SELECT COUNT(*) AS c FROM queries").fetchone()
            return int(row["c"])

    def iter_queries(self, min_count: int = 0) -> Iterable[QueryRecord]:
        with self.connect() as conn:
            metrics.record_db_read()
            cursor = conn.execute(
                """
                SELECT query, global_count, weekly_count, daily_count, last_seen
                FROM queries
                WHERE global_count >= ?
                ORDER BY query
                """,
                (min_count,),
            )
            for row in cursor:
                yield QueryRecord(
                    query=row["query"],
                    global_count=int(row["global_count"]),
                    weekly_count=int(row["weekly_count"]),
                    daily_count=int(row["daily_count"]),
                    last_seen=row["last_seen"],
                )

    def get_query(self, query: str) -> QueryRecord | None:
        with self.connect() as conn:
            metrics.record_db_read()
            row = conn.execute(
                """
                SELECT query, global_count, weekly_count, daily_count, last_seen
                FROM queries WHERE query = ?
                """,
                (query,),
            ).fetchone()
            if row is None:
                return None
            return QueryRecord(
                query=row["query"],
                global_count=int(row["global_count"]),
                weekly_count=int(row["weekly_count"]),
                daily_count=int(row["daily_count"]),
                last_seen=row["last_seen"],
            )

    def top_by_global(self, limit: int = 10) -> list[QueryRecord]:
        with self.connect() as conn:
            metrics.record_db_read()
            rows = conn.execute(
                """
                SELECT query, global_count, weekly_count, daily_count, last_seen
                FROM queries
                ORDER BY global_count DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [
                QueryRecord(
                    query=row["query"],
                    global_count=int(row["global_count"]),
                    weekly_count=int(row["weekly_count"]),
                    daily_count=int(row["daily_count"]),
                    last_seen=row["last_seen"],
                )
                for row in rows
            ]

    def top_by_trending(self, limit: int = 10) -> list[QueryRecord]:
        with self.connect() as conn:
            metrics.record_db_read()
            rows = conn.execute(
                """
                SELECT query, global_count, weekly_count, daily_count, last_seen
                FROM queries
                ORDER BY (0.6 * global_count + 0.3 * weekly_count + 0.1 * daily_count) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [
                QueryRecord(
                    query=row["query"],
                    global_count=int(row["global_count"]),
                    weekly_count=int(row["weekly_count"]),
                    daily_count=int(row["daily_count"]),
                    last_seen=row["last_seen"],
                )
                for row in rows
            ]

    def prefix_search(self, prefix: str, limit: int = 10, mode: str = "basic") -> list[QueryRecord]:
        if not prefix:
            return []
        order_clause = (
            "global_count DESC, query ASC"
            if mode == "basic"
            else "(0.6 * global_count + 0.3 * weekly_count + 0.1 * daily_count) DESC, query ASC"
        )
        with self.connect() as conn:
            metrics.record_db_read()
            rows = conn.execute(
                f"""
                SELECT query, global_count, weekly_count, daily_count, last_seen
                FROM queries
                WHERE query LIKE ? ESCAPE '\\'
                ORDER BY {order_clause}
                LIMIT ?
                """,
                (prefix + "%", limit),
            ).fetchall()
            return [
                QueryRecord(
                    query=row["query"],
                    global_count=int(row["global_count"]),
                    weekly_count=int(row["weekly_count"]),
                    daily_count=int(row["daily_count"]),
                    last_seen=row["last_seen"],
                )
                for row in rows
            ]

    def bulk_upsert_seed(self, rows: list[tuple[str, int, int, int, str | None]]) -> None:
        if not rows:
            return
        with self.connect() as conn:
            metrics.record_db_write()
            conn.executemany(
                """
                INSERT INTO queries (query, global_count, weekly_count, daily_count, last_seen)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(query) DO UPDATE SET
                    global_count = excluded.global_count,
                    weekly_count = excluded.weekly_count,
                    daily_count = excluded.daily_count,
                    last_seen = COALESCE(excluded.last_seen, queries.last_seen)
                """,
                rows,
            )

    def apply_deltas(
        self,
        deltas: dict[str, int],
        now: datetime | None = None,
    ) -> list[QueryRecord]:
        if not deltas:
            return []

        now = now or datetime.now(timezone.utc)
        now_iso = now.isoformat()
        updated: list[QueryRecord] = []

        with self.connect() as conn:
            metrics.record_db_write()
            for query, delta in deltas.items():
                row = conn.execute(
                    "SELECT global_count, weekly_count, daily_count FROM queries WHERE query = ?",
                    (query,),
                ).fetchone()
                if row is None:
                    global_count = delta
                    weekly_count = delta
                    daily_count = delta
                    conn.execute(
                        """
                        INSERT INTO queries (query, global_count, weekly_count, daily_count, last_seen)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (query, global_count, weekly_count, daily_count, now_iso),
                    )
                else:
                    global_count = int(row["global_count"]) + delta
                    weekly_count = int(row["weekly_count"]) + delta
                    daily_count = int(row["daily_count"]) + delta
                    conn.execute(
                        """
                        UPDATE queries
                        SET global_count = ?, weekly_count = ?, daily_count = ?, last_seen = ?
                        WHERE query = ?
                        """,
                        (global_count, weekly_count, daily_count, now_iso, query),
                    )

                updated.append(
                    QueryRecord(
                        query=query,
                        global_count=global_count,
                        weekly_count=weekly_count,
                        daily_count=daily_count,
                        last_seen=now_iso,
                    )
                )

        return updated

    def decay_recency_counters(self, now: datetime | None = None) -> int:
        """Apply time decay to weekly/daily counters so spikes fade over time."""
        now = now or datetime.now(timezone.utc)
        daily_factor = 0.5 ** (1.0 / max(self.settings.trending_decay_daily_hours, 1.0))
        weekly_factor = 0.5 ** (1.0 / max(self.settings.trending_decay_weekly_hours, 1.0))

        with self.connect() as conn:
            metrics.record_db_write()
            cur = conn.execute(
                """
                UPDATE queries
                SET daily_count = CAST(daily_count * ? AS INTEGER),
                    weekly_count = CAST(weekly_count * ? AS INTEGER)
                WHERE daily_count > 0 OR weekly_count > 0
                """,
                (daily_factor, weekly_factor),
            )
            return cur.rowcount
