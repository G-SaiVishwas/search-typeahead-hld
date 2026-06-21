from __future__ import annotations

import csv
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import get_settings
from backend.app.store import QueryStore
from backend.app.trie import normalize_query

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def ingest(csv_path: Path | None = None, chunk_size: int = 50_000) -> None:
    settings = get_settings()
    csv_path = csv_path or settings.csv_path
    store = QueryStore(settings)
    store.init_schema()

    if store.row_count() > 0:
        count = store.row_count()
        logger.info("Database already contains %s rows; skipping ingest", count)
        return

    logger.info("Ingesting from %s", csv_path)
    started = time.time()
    batch: list[tuple[str, int, int, int, str | None]] = []
    total = 0

    with open(csv_path, newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            query = normalize_query(row["Query"])
            if not query:
                continue
            batch.append(
                (
                    query,
                    int(row["Global Count"]),
                    int(row["Weekly Count"]),
                    int(row["Daily Count"]),
                    None,
                )
            )
            if len(batch) >= chunk_size:
                store.bulk_upsert_seed(batch)
                total += len(batch)
                logger.info("Inserted %s rows...", total)
                batch.clear()

        if batch:
            store.bulk_upsert_seed(batch)
            total += len(batch)

    elapsed = time.time() - started
    logger.info("Ingest complete: %s rows in %.2fs", total, elapsed)
    logger.info("Validated row count: %s", store.row_count())

    sample = store.top_by_global(5)
    logger.info("Top 5 by global count:")
    for record in sample:
        logger.info("  %s -> %s", record.query, record.global_count)


if __name__ == "__main__":
    ingest()
