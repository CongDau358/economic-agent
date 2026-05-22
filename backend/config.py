"""
backend/config.py
Centralized configuration using pydantic-settings.
All settings are loaded from environment variables or .env file.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── AI / LLM ──────────────────────────────────────────────────────────────
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # ── Auth ──────────────────────────────────────────────────────────────────
    # Comma-separated list of valid API keys for this service
    # e.g. API_KEYS=key1,key2,key3
    api_keys: str = ""
    auth_enabled: bool = True

    @property
    def valid_api_keys(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    # ── Vector store ──────────────────────────────────────────────────────────
    chroma_persist_dir: str = "data/vector"
    chroma_collection_name: str = "economic_docs"

    # ── Data paths ────────────────────────────────────────────────────────────
    raw_data_dir: str = "data/raw"
    processed_data_dir: str = "data/processed"

    # ── Market data ───────────────────────────────────────────────────────────
    # FRED (Federal Reserve Economic Data) — free, no key required for basic
    fred_api_key: str = ""
    # Alpha Vantage — free tier available at https://www.alphavantage.co/
    alpha_vantage_api_key: str = ""

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    log_level: str = "info"

    # ── Redis cache (optional) ────────────────────────────────────────────────
    redis_url: str = ""          # Leave blank to use in-memory cache
    cache_ttl_seconds: int = 3600

    # ── Trend engine weights ──────────────────────────────────────────────────
    weight_financial: float = 0.5
    weight_sentiment: float = 0.3
    weight_macro: float = 0.2

    # ── RAG ───────────────────────────────────────────────────────────────────
    rag_top_k: int = 5
    rag_score_threshold: float = 0.5
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 200


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance (singleton)."""
    return Settings()