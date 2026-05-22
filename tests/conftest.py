"""
tests/conftest.py
Shared fixtures cho toàn bộ test suite.
"""

from __future__ import annotations

import os
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport


# ── Environment setup (session-scoped) ────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def setup_test_env(tmp_path_factory):
    """Patch env vars và tạo thư mục temp trước khi bất kỳ test nào chạy."""
    tmp = tmp_path_factory.mktemp("data")
    for sub in ("vector", "raw", "processed"):
        (tmp / sub).mkdir(parents=True, exist_ok=True)

    env_patch = {
        "OPENAI_API_KEY":       "test-key-not-real",
        "AUTH_ENABLED":         "false",
        "API_KEYS":             "test-secret",
        "CHROMA_PERSIST_DIR":   str(tmp / "vector"),
        "RAW_DATA_DIR":         str(tmp / "raw"),
        "PROCESSED_DATA_DIR":   str(tmp / "processed"),
        "REDIS_URL":            "",            # force in-memory cache
        "LOG_LEVEL":            "warning",     # suppress logs during tests
        "WEIGHT_FINANCIAL":     "0.5",
        "WEIGHT_SENTIMENT":     "0.3",
        "WEIGHT_MACRO":         "0.2",
    }
    with patch.dict(os.environ, env_patch):
        yield

    # Clear settings cache sau session
    try:
        from backend.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass


# ── Mock heavy services ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def mock_heavy_services():
    """Mock VectorStore, RetrievalAPI, Orchestrator để test không cần OpenAI."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.run.return_value = MagicMock()
    mock_orchestrator.to_response_dict.return_value = {
        "answer": "Mock answer từ RAG.",
        "citations": [{"source": "mock_doc.pdf", "score": 0.88}],
        "confidence": 0.82,
    }

    with (
        patch("backend.rag.vector_store.VectorStoreService", return_value=MagicMock()),
        patch("backend.retrieval.service.RetrievalAPI", return_value=MagicMock()),
        patch("backend.retrieval.router.bind_retrieval_api"),
        patch("backend.orchestration.pipeline.PromptOrchestrationPipeline",
              return_value=mock_orchestrator),
    ):
        yield {"orchestrator": mock_orchestrator}


# ── HTTP client ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(mock_heavy_services):
    """Async HTTP client kết nối trực tiếp vào app (không cần server chạy)."""
    from backend.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(mock_heavy_services):
    """Client có sẵn X-API-Key header."""
    from backend.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": "test-secret"},
    ) as ac:
        yield ac


# ── Trend engine fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def bullish_result():
    return {
        "company": "Vinamilk", "status": "OK", "score": 0.78,
        "trend": {"short_term": "bullish", "near_term": "bullish"},
        "confidence": 0.87,
        "executive_summary": "Tăng trưởng mạnh với triển vọng tích cực.",
        "risks": [], "opportunities": ["revenue_up", "eps_beat"],
        "scenarios": {"bull": 0.90, "base": 0.78, "bear": 0.63},
        "warnings": [],
        "financial_signals": {"score": 0.72, "inputs": ["revenue_up", "eps_beat"]},
        "sentiment_signals": {"score": 0.55, "inputs": ["positive_news"]},
        "macro_signals": {"score": 0.40, "inputs": ["policy_support"]},
        "assumptions": ["Trọng số: Tài chính 50%, Sentiment 30%, Vĩ mô 20%"],
    }


@pytest.fixture
def bearish_result():
    return {
        "company": "Acme", "status": "OK", "score": 0.28,
        "trend": {"short_term": "bearish", "near_term": "bearish"},
        "confidence": 0.75,
        "executive_summary": "Suy giảm với nhiều rủi ro.",
        "risks": ["revenue_down", "eps_miss"],
        "opportunities": [],
        "scenarios": {"bull": 0.40, "base": 0.28, "bear": 0.13},
        "warnings": [],
        "financial_signals": {"score": -0.60, "inputs": ["revenue_down", "eps_miss"]},
        "sentiment_signals": {"score": -0.40, "inputs": ["analyst_downgrade"]},
        "macro_signals": {"score": -0.30, "inputs": ["geopolitical_risk"]},
        "assumptions": [],
    }


@pytest.fixture
def insufficient_result():
    return {
        "company": "X", "status": "INSUFFICIENT_DATA",
        "message": "Cần ít nhất 2 tín hiệu để phân tích.",
        "score": None, "trend": None, "confidence": 0.0,
    }


# ── Job store fixture ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def clean_job_store():
    """Job store sạch cho mỗi test."""
    from backend.services.job_store import InMemoryJobStore
    store = InMemoryJobStore(ttl_seconds=300)
    yield store


# ── Cache fixture ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def clean_cache():
    """In-memory cache sạch cho mỗi test."""
    from backend.services.cache import InMemoryCache
    cache = InMemoryCache(default_ttl=60)
    yield cache
    await cache.clear()