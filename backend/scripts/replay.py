from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import get_settings
from backend.app.trie import normalize_query

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def replay(
    api_base: str = "http://localhost:8000",
    limit: int = 10_000,
    csv_path: Path | None = None,
) -> None:
    settings = get_settings()
    csv_path = csv_path or settings.raw_csv_path
    sent = 0
    started = time.time()

    with httpx.Client(base_url=api_base, timeout=30.0) as client:
        with open(csv_path, newline="", encoding="utf-8", errors="replace") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                query = normalize_query(row["Query"])
                if not query:
                    continue
                response = client.post("/search", json={"query": query})
                response.raise_for_status()
                sent += 1
                if sent >= limit:
                    break
                if sent % 1000 == 0:
                    logger.info("Replayed %s searches...", sent)

        client.post("/batch/flush")
        metrics = client.get("/metrics").json()

    elapsed = time.time() - started
    logger.info("Replay complete: %s events in %.2fs", sent, elapsed)
    logger.info("Metrics: %s", metrics)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay raw query events into POST /search")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--limit", type=int, default=10_000)
    parser.add_argument("--csv", type=Path, default=None)
    args = parser.parse_args()
    replay(api_base=args.base_url, limit=args.limit, csv_path=args.csv)
