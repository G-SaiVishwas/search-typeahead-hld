from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "typeahead.db"
DEFAULT_CSV_PATH = DATA_DIR / "typeahed_dataset.csv"
DEFAULT_RAW_CSV_PATH = DATA_DIR / "raw_queries.csv"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_path: Path = DEFAULT_DB_PATH
    csv_path: Path = DEFAULT_CSV_PATH
    raw_csv_path: Path = DEFAULT_RAW_CSV_PATH

    redis_nodes: str = "localhost:6379,localhost:6380,localhost:6381"
    cache_ttl_seconds: int = 300
    cache_vnodes: int = 150

    batch_flush_size: int = 500
    batch_flush_interval_seconds: float = 2.0

    trie_top_k: int = 10
    trie_min_count: int = 10

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    trending_decay_daily_hours: float = 24.0
    trending_decay_weekly_hours: float = 168.0

    @property
    def redis_node_list(self) -> list[tuple[str, int]]:
        nodes: list[tuple[str, int]] = []
        for entry in self.redis_nodes.split(","):
            entry = entry.strip()
            if not entry:
                continue
            host, port = entry.rsplit(":", 1)
            nodes.append((host, int(port)))
        return nodes

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
