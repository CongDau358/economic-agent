"""
tests/test_config.py
Tests cho Settings / config.py.
"""

from __future__ import annotations

import os
import pytest


@pytest.fixture(autouse=True)
def clear_settings_cache():
    yield
    from backend.config import get_settings
    get_settings.cache_clear()


# ── Required fields ───────────────────────────────────────────────────────────

class TestRequiredFields:

    def test_openai_key_loaded(self):
        from backend.config import get_settings
        s = get_settings()
        assert s.openai_api_key  # từ setup_test_env fixture

    def test_openai_key_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
        from backend.config import get_settings
        get_settings.cache_clear()
        assert get_settings().openai_api_key == "sk-test-123"


# ── Defaults ──────────────────────────────────────────────────────────────────

class TestDefaults:

    def test_default_model(self):
        from backend.config import get_settings
        s = get_settings()
        assert s.openai_model == "gpt-4o-mini"

    def test_default_embedding_model(self):
        from backend.config import get_settings
        assert get_settings().openai_embedding_model == "text-embedding-3-small"

    def test_default_port(self):
        from backend.config import get_settings
        assert get_settings().port == 8000

    def test_default_host(self):
        from backend.config import get_settings
        assert get_settings().host == "0.0.0.0"

    def test_default_weights_sum_to_one(self):
        from backend.config import get_settings
        s = get_settings()
        total = s.weight_financial + s.weight_sentiment + s.weight_macro
        assert abs(total - 1.0) < 1e-9

    def test_default_rag_top_k(self):
        from backend.config import get_settings
        assert get_settings().rag_top_k == 5

    def test_default_cache_ttl(self):
        from backend.config import get_settings
        assert get_settings().cache_ttl_seconds == 3600

    def test_default_auth_enabled(self, monkeypatch):
        monkeypatch.setenv("AUTH_ENABLED", "true")
        from backend.config import get_settings
        get_settings.cache_clear()
        assert get_settings().auth_enabled is True

    def test_default_collection_name(self):
        from backend.config import get_settings
        assert get_settings().chroma_collection_name == "economic_docs"


# ── Overrides ─────────────────────────────────────────────────────────────────

class TestEnvOverrides:

    def test_override_model(self, monkeypatch):
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
        from backend.config import get_settings
        get_settings.cache_clear()
        assert get_settings().openai_model == "gpt-4o"

    def test_override_weights(self, monkeypatch):
        monkeypatch.setenv("WEIGHT_FINANCIAL", "0.6")
        monkeypatch.setenv("WEIGHT_SENTIMENT", "0.2")
        monkeypatch.setenv("WEIGHT_MACRO",     "0.2")
        from backend.config import get_settings
        get_settings.cache_clear()
        s = get_settings()
        assert s.weight_financial == 0.6
        assert s.weight_sentiment == 0.2
        assert s.weight_macro     == 0.2

    def test_override_rag_top_k(self, monkeypatch):
        monkeypatch.setenv("RAG_TOP_K", "8")
        from backend.config import get_settings
        get_settings.cache_clear()
        assert get_settings().rag_top_k == 8

    def test_override_log_level(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "debug")
        from backend.config import get_settings
        get_settings.cache_clear()
        assert get_settings().log_level == "debug"

    def test_override_chunk_size(self, monkeypatch):
        monkeypatch.setenv("RAG_CHUNK_SIZE",    "500")
        monkeypatch.setenv("RAG_CHUNK_OVERLAP", "100")
        from backend.config import get_settings
        get_settings.cache_clear()
        s = get_settings()
        assert s.rag_chunk_size    == 500
        assert s.rag_chunk_overlap == 100

    def test_redis_url_empty_by_default(self):
        from backend.config import get_settings
        # setup_test_env đặt REDIS_URL=""
        assert get_settings().redis_url == ""

    def test_override_redis_url(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")
        from backend.config import get_settings
        get_settings.cache_clear()
        assert get_settings().redis_url == "redis://localhost:6379/1"


# ── valid_api_keys property ───────────────────────────────────────────────────

class TestValidApiKeys:

    def test_empty_api_keys(self, monkeypatch):
        monkeypatch.setenv("API_KEYS", "")
        from backend.config import get_settings
        get_settings.cache_clear()
        assert get_settings().valid_api_keys == set()

    def test_single_key(self, monkeypatch):
        monkeypatch.setenv("API_KEYS", "my-key")
        from backend.config import get_settings
        get_settings.cache_clear()
        assert "my-key" in get_settings().valid_api_keys

    def test_multiple_keys(self, monkeypatch):
        monkeypatch.setenv("API_KEYS", "key-a,key-b,key-c")
        from backend.config import get_settings
        get_settings.cache_clear()
        assert get_settings().valid_api_keys == {"key-a", "key-b", "key-c"}

    def test_keys_stripped(self, monkeypatch):
        monkeypatch.setenv("API_KEYS", " key-a , key-b ")
        from backend.config import get_settings
        get_settings.cache_clear()
        keys = get_settings().valid_api_keys
        assert "key-a" in keys
        assert "key-b" in keys
        assert " key-a " not in keys

    def test_duplicate_keys_deduplicated(self, monkeypatch):
        monkeypatch.setenv("API_KEYS", "key-a,key-a,key-b")
        from backend.config import get_settings
        get_settings.cache_clear()
        assert len(get_settings().valid_api_keys) == 2


# ── Singleton / caching ───────────────────────────────────────────────────────

class TestSingleton:

    def test_same_instance_returned(self):
        from backend.config import get_settings
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_cache_clear_returns_new_instance(self, monkeypatch):
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4-turbo")
        from backend.config import get_settings
        get_settings.cache_clear()
        s = get_settings()
        assert s.openai_model == "gpt-4-turbo"


# ── Type validation ───────────────────────────────────────────────────────────

class TestTypeValidation:

    def test_port_is_int(self):
        from backend.config import get_settings
        assert isinstance(get_settings().port, int)

    def test_weights_are_float(self):
        from backend.config import get_settings
        s = get_settings()
        assert isinstance(s.weight_financial, float)
        assert isinstance(s.weight_sentiment, float)
        assert isinstance(s.weight_macro, float)

    def test_auth_enabled_is_bool(self):
        from backend.config import get_settings
        assert isinstance(get_settings().auth_enabled, bool)

    def test_rag_top_k_is_int(self):
        from backend.config import get_settings
        assert isinstance(get_settings().rag_top_k, int)

    def test_cache_ttl_is_int(self):
        from backend.config import get_settings
        assert isinstance(get_settings().cache_ttl_seconds, int)