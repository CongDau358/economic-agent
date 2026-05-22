"""
tests/test_api.py
Integration tests for the Economic Agent API.

Run:
    pytest tests/ -v
    pytest tests/ -v --cov=backend --cov-report=term-missing
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def patch_settings(tmp_path_factory):
    """Override settings to disable auth and use temp dirs during tests."""
    import os
    tmp = tmp_path_factory.mktemp("data")
    os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
    os.environ["AUTH_ENABLED"] = "false"
    os.environ["CHROMA_PERSIST_DIR"] = str(tmp / "vector")
    os.environ["RAW_DATA_DIR"] = str(tmp / "raw")
    os.environ["PROCESSED_DATA_DIR"] = str(tmp / "processed")
    yield


@pytest_asyncio.fixture
async def client():
    from backend.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Health ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


# ── Auth ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predict_no_auth_returns_401_when_auth_enabled(tmp_path):
    """When auth is enabled and no key is provided, expect 401."""
    import os
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["API_KEYS"] = "secret123"

    from backend.config import get_settings
    get_settings.cache_clear()

    from backend.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/predict", json={
            "company": "Acme",
            "financial_signals": [],
            "sentiment_signals": [],
            "macro_signals": [],
        })
    assert resp.status_code == 401

    # Restore
    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()


# ── Upload ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_text_queues_job(client):
    resp = await client.post(
        "/upload",
        data={
            "source_type": "text",
            "company": "Test Corp",
            "sector": "Technology",
            "text": "Revenue increased 15 percent year-over-year.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert "job_id" in data

    job_id = data["job_id"]
    # Job should be trackable
    job_resp = await client.get(f"/jobs/{job_id}")
    assert job_resp.status_code == 200
    assert job_resp.json()["job_id"] == job_id


@pytest.mark.asyncio
async def test_upload_missing_company_fails(client):
    resp = await client.post(
        "/upload",
        data={"source_type": "text", "text": "Some text"},
    )
    assert resp.status_code == 422  # Pydantic validation error


# ── Predict ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predict_basic(client, mocker):
    """Predict endpoint returns expected structure."""
    mock_result = {
        "company": "Acme",
        "score": 0.72,
        "trend": "bullish",
        "confidence": 0.8,
        "summary": "Strong financials with positive macro tailwinds.",
        "risks": ["cost_pressure"],
        "opportunities": ["market_expansion"],
    }
    mocker.patch("backend.trend_engine.TrendEngine.analyze", return_value=mock_result)

    resp = await client.post(
        "/predict",
        json={
            "company": "Acme",
            "financial_signals": ["revenue_up", "margin_stable"],
            "sentiment_signals": ["positive_news"],
            "macro_signals": ["policy_support"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["company"] == "Acme"
    assert "score" in data


@pytest.mark.asyncio
async def test_predict_caches_result(client, mocker):
    """Second identical call returns cached result."""
    mock_result = {"company": "Acme", "score": 0.65, "trend": "neutral"}
    mocker.patch("backend.trend_engine.TrendEngine.analyze", return_value=mock_result)

    payload = {
        "company": "Acme",
        "financial_signals": ["revenue_up"],
        "sentiment_signals": [],
        "macro_signals": [],
    }
    resp1 = await client.post("/predict", json=payload)
    resp2 = await client.post("/predict", json=payload)

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp2.json().get("_cached") is True


# ── Ask ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ask_returns_answer(client, mocker):
    mock_rag = {
        "answer": "Key risks include supply chain disruption and currency exposure.",
        "citations": [{"source": "Q3 Report", "page": 12}],
        "confidence": 0.75,
    }
    mocker.patch("backend.rag.retriever.RAGRetriever.ask", return_value=mock_rag)

    resp = await client.post(
        "/ask",
        json={
            "question": "What are key risks?",
            "company": "Acme",
            "sector": "Manufacturing",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "citations" in data


# ── Jobs ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_job_not_found(client):
    resp = await client.get("/jobs/nonexistent-id")
    assert resp.status_code == 404


# ── Market data (unit) ────────────────────────────────────────────────────────

def test_make_cache_key_is_deterministic():
    from backend.services.cache import make_cache_key
    k1 = make_cache_key("predict", company="Acme", signals=["a", "b"])
    k2 = make_cache_key("predict", company="Acme", signals=["a", "b"])
    assert k1 == k2


def test_make_cache_key_differs_on_different_input():
    from backend.services.cache import make_cache_key
    k1 = make_cache_key("predict", company="Acme")
    k2 = make_cache_key("predict", company="Beta")
    assert k1 != k2


@pytest.mark.asyncio
async def test_in_memory_cache_ttl():
    """Expired entries should not be returned."""
    import time
    from backend.services.cache import InMemoryCache
    cache = InMemoryCache(default_ttl=1)
    await cache.set("k", "v", ttl=1)
    assert await cache.get("k") == "v"
    time.sleep(1.1)
    assert await cache.get("k") is None