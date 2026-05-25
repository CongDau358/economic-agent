"""
tests/test_api.py

Chạy:
    pytest tests/ -v
    pytest tests/ -v --cov=backend --cov-fail-under=60
"""

from __future__ import annotations

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def patch_env(tmp_path_factory):
    import os
    tmp = tmp_path_factory.mktemp("data")
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    os.environ["AUTH_ENABLED"]        = "false"
    os.environ["CHROMA_PERSIST_DIR"]  = str(tmp / "vector")
    os.environ["RAW_DATA_DIR"]        = str(tmp / "raw")
    os.environ["PROCESSED_DATA_DIR"]  = str(tmp / "processed")
    (tmp / "vector").mkdir(parents=True, exist_ok=True)
    (tmp / "raw").mkdir(parents=True, exist_ok=True)
    (tmp / "processed").mkdir(parents=True, exist_ok=True)
    yield
    from backend.config import get_settings
    get_settings.cache_clear()


# Mock tất cả service nặng trước khi import app
@pytest.fixture(scope="session")
def mock_services():
    with (
        patch("backend.rag.vector_store.VectorStoreService"),
        patch("backend.retrieval.service.RetrievalAPI"),
        patch("backend.retrieval.router.bind_retrieval_api"),
        patch("backend.orchestration.pipeline.PromptOrchestrationPipeline"),
    ):
        yield


@pytest_asyncio.fixture
async def client(mock_services):
    from backend.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── Health ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "jobs" in data


# ── Auth ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predict_requires_auth_when_enabled(mock_services, tmp_path):
    import os
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["API_KEYS"]     = "secret123"
    from backend.config import get_settings
    get_settings.cache_clear()

    from backend.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/predict", json={
            "company": "Acme",
            "financial_signals": [],
            "sentiment_signals": [],
            "macro_signals": [],
        })
    assert r.status_code == 401

    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_predict_passes_with_valid_key(mock_services):
    import os
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["API_KEYS"]     = "secret123"
    from backend.config import get_settings
    get_settings.cache_clear()

    from backend.main import app
    from backend.trend_engine import TrendEngine
    mock_result = {"company": "Acme", "status": "OK", "score": 0.7,
                   "trend": {"short_term": "bullish", "near_term": "bullish"},
                   "confidence": 0.8, "risks": [], "opportunities": [],
                   "executive_summary": "OK", "warnings": [], "scenarios": {},
                   "financial_signals": {"score": 0.5, "inputs": []},
                   "sentiment_signals": {"score": 0.3, "inputs": []},
                   "macro_signals": {"score": 0.2, "inputs": []},
                   "assumptions": []}

    with patch.object(TrendEngine, "analyze", return_value=mock_result):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post(
                "/predict",
                json={"company": "Acme", "financial_signals": ["revenue_up"]},
                headers={"X-API-Key": "secret123"},
            )
    assert r.status_code == 200

    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()


# ── Upload + Job tracking ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_text_returns_job_id(client, mocker):
    mocker.patch("backend.main._sync_ingest", return_value={"chunk_count": 3})
    r = await client.post(
        "/upload",
        data={"source_type": "text", "company": "Test Co", "sector": "Tech",
              "text": "Revenue up 15% YoY."},
    )
    assert r.status_code == 200
    data = r.json()
    assert "job_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_get_job_not_found(client):
    r = await client.get("/jobs/nonexistent-id")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_jobs(client):
    r = await client.get("/jobs")
    assert r.status_code == 200
    assert "jobs" in r.json()
    assert "count" in r.json()


@pytest.mark.asyncio
async def test_list_jobs_filter_by_status(client):
    r = await client.get("/jobs?status=pending&limit=10")
    assert r.status_code == 200


# ── Predict ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predict_basic(client, mocker):
    mock_result = {
        "company": "Vinamilk", "status": "OK", "score": 0.72,
        "trend": {"short_term": "bullish", "near_term": "bullish"},
        "confidence": 0.85, "risks": ["cost_up"], "opportunities": ["revenue_up"],
        "executive_summary": "Tăng trưởng tốt.",
        "warnings": [], "scenarios": {"bull": 0.84, "base": 0.72, "bear": 0.57},
        "financial_signals": {"score": 0.6, "inputs": ["revenue_up"]},
        "sentiment_signals": {"score": 0.4, "inputs": []},
        "macro_signals": {"score": 0.3, "inputs": []},
        "assumptions": [],
    }
    from backend.trend_engine import TrendEngine
    mocker.patch.object(TrendEngine, "analyze", return_value=mock_result)

    r = await client.post("/predict", json={
        "company": "Vinamilk",
        "financial_signals": ["revenue_up", "margin_stable"],
        "sentiment_signals": ["positive_news"],
        "macro_signals": ["policy_support"],
    })
    assert r.status_code == 200
    data = r.json()
    assert data["company"] == "Vinamilk"
    assert data["score"] == 0.72
    assert data["trend"]["short_term"] == "bullish"


@pytest.mark.asyncio
async def test_predict_insufficient_data(client, mocker):
    from backend.trend_engine import TrendEngine
    mocker.patch.object(TrendEngine, "analyze", return_value={
        "status": "INSUFFICIENT_DATA",
        "message": "Cần ít nhất 2 tín hiệu",
        "score": None, "trend": None, "confidence": 0.0,
    })
    r = await client.post("/predict", json={
        "company": "X", "financial_signals": [], "sentiment_signals": [], "macro_signals": [],
    })
    assert r.status_code == 200
    assert r.json()["status"] == "INSUFFICIENT_DATA"


@pytest.mark.asyncio
async def test_predict_caches_second_call(client, mocker):
    from backend.trend_engine import TrendEngine
    mock_result = {
        "company": "A", "status": "OK", "score": 0.6,
        "trend": {"short_term": "neutral", "near_term": "neutral"},
        "confidence": 0.7, "risks": [], "opportunities": [],
        "executive_summary": "", "warnings": [], "scenarios": {},
        "financial_signals": {"score": 0, "inputs": []},
        "sentiment_signals": {"score": 0, "inputs": []},
        "macro_signals": {"score": 0, "inputs": []},
        "assumptions": [],
    }
    call = mocker.patch.object(TrendEngine, "analyze", return_value=mock_result)

    payload = {"company": "A", "financial_signals": ["revenue_up"],
               "sentiment_signals": [], "macro_signals": []}
    await client.post("/predict", json=payload)
    r2 = await client.post("/predict", json=payload)

    assert r2.status_code == 200
    # Lần 2 dùng cache → analyze chỉ gọi 1 lần
    assert call.call_count == 1
    assert r2.json().get("_cached") is True


# ── Ask ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ask_returns_response(client, mocker):
    from backend.main import orchestrator
    mock_run    = mocker.patch.object(orchestrator, "run", return_value=MagicMock())
    mock_to_dict = mocker.patch.object(orchestrator, "to_response_dict", return_value={
        "answer": "Rủi ro chính là biến động tỷ giá.",
        "citations": [{"source": "Q3 Report"}],
        "confidence": 0.8,
    })

    r = await client.post("/ask", json={
        "question": "Rủi ro chính là gì?",
        "company": "Vinamilk",
        "retrieval_mode": "hybrid",
    })
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_ask_missing_question(client):
    r = await client.post("/ask", json={"question": "ab"})  # min_length=3 → "ab" len=2
    assert r.status_code == 422


# ── Cache unit tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_in_memory_cache_set_get():
    from backend.services.cache import InMemoryCache
    cache = InMemoryCache(default_ttl=60)
    await cache.set("k", {"score": 0.8})
    result = await cache.get("k")
    assert result == {"score": 0.8}


@pytest.mark.asyncio
async def test_in_memory_cache_miss():
    from backend.services.cache import InMemoryCache
    cache = InMemoryCache()
    assert await cache.get("no-such-key") is None


@pytest.mark.asyncio
async def test_in_memory_cache_expired():
    import time
    from backend.services.cache import InMemoryCache
    cache = InMemoryCache(default_ttl=1)
    await cache.set("k", "v", ttl=1)
    time.sleep(1.1)
    assert await cache.get("k") is None


def test_cache_key_deterministic():
    from backend.services.cache import make_cache_key
    k1 = make_cache_key("predict", company="Acme", signals=["a", "b"])
    k2 = make_cache_key("predict", company="Acme", signals=["a", "b"])
    assert k1 == k2


def test_cache_key_differs():
    from backend.services.cache import make_cache_key
    k1 = make_cache_key("predict", company="A")
    k2 = make_cache_key("predict", company="B")
    assert k1 != k2


# ── Job store unit tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_job_store_lifecycle():
    from backend.services.job_store import InMemoryJobStore, JobStatus
    store = InMemoryJobStore(ttl_seconds=60)

    job = await store.create("j1", company="Acme", source_type="text")
    assert job.status == JobStatus.PENDING

    await store.update("j1", JobStatus.RUNNING)
    job = await store.get("j1")
    assert job.status == JobStatus.RUNNING

    await store.update("j1", JobStatus.DONE, result={"chunk_count": 5})
    job = await store.get("j1")
    assert job.status == JobStatus.DONE
    assert job.result["chunk_count"] == 5


@pytest.mark.asyncio
async def test_job_store_not_found():
    from backend.services.job_store import InMemoryJobStore
    store = InMemoryJobStore()
    assert await store.get("missing") is None


@pytest.mark.asyncio
async def test_job_store_list_filter():
    from backend.services.job_store import InMemoryJobStore, JobStatus
    store = InMemoryJobStore()
    await store.create("j2", company="Vinamilk", source_type="pdf")
    await store.create("j3", company="VCB", source_type="text")

    jobs = await store.list_jobs(company="Vinamilk")
    assert all(j["company"] == "Vinamilk" for j in jobs)


# ── Trend engine unit tests ───────────────────────────────────────────────────

def test_trend_engine_bullish():
    from backend.trend_engine import TrendEngine
    engine = TrendEngine()
    result = engine.analyze(
        company="Acme",
        financial_signals=["revenue_up", "profit_up", "eps_beat"],
        sentiment_signals=["analyst_upgrade", "positive_news"],
        macro_signals=["policy_support", "gdp_growth"],
    )
    assert result["status"] == "OK"
    assert result["score"] > 0.5
    assert result["trend"]["short_term"] == "bullish"


def test_trend_engine_bearish():
    from backend.trend_engine import TrendEngine
    engine = TrendEngine()
    result = engine.analyze(
        company="Acme",
        financial_signals=["revenue_down", "profit_down", "eps_miss"],
        sentiment_signals=["analyst_downgrade", "negative_news"],
        macro_signals=["geopolitical_risk", "interest_rate_high"],
    )
    assert result["status"] == "OK"
    assert result["score"] < 0.5
    assert result["trend"]["short_term"] == "bearish"


def test_trend_engine_insufficient_data():
    from backend.trend_engine import TrendEngine
    engine = TrendEngine()
    result = engine.analyze("Acme", [], [], [])
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["score"] is None


def test_trend_engine_conflict_detected():
    from backend.trend_engine import TrendEngine
    engine = TrendEngine()
    result = engine.analyze(
        company="Acme",
        financial_signals=["revenue_up", "revenue_down", "eps_beat", "eps_miss"],
        sentiment_signals=["positive_news"],
        macro_signals=["gdp_growth"],
    )
    assert "conflicting_financial_signals" in result["risks"]
    assert result["confidence"] < 0.8