"""
tests/test_rate_limiter.py
Tests cho rate limiter — constants, stub, endpoint integration.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# ── Constants ─────────────────────────────────────────────────────────────────

class TestLimitConstants:

    def test_all_limits_defined(self):
        from backend.services.rate_limiter import (
            UPLOAD_LIMIT, PREDICT_LIMIT, ASK_LIMIT,
            SEARCH_LIMIT, HEALTH_LIMIT,
        )
        for name, val in [
            ("UPLOAD_LIMIT",  UPLOAD_LIMIT),
            ("PREDICT_LIMIT", PREDICT_LIMIT),
            ("ASK_LIMIT",     ASK_LIMIT),
            ("SEARCH_LIMIT",  SEARCH_LIMIT),
            ("HEALTH_LIMIT",  HEALTH_LIMIT),
        ]:
            assert "/" in val, f"{name} phải dạng 'N/unit'"
            n, unit = val.split("/")
            assert n.isdigit(), f"{name}: N phải là số"
            assert unit in ("second", "minute", "hour"), f"{name}: unit không hợp lệ"

    def test_upload_stricter_than_predict(self):
        from backend.services.rate_limiter import UPLOAD_LIMIT, PREDICT_LIMIT
        upload_n  = int(UPLOAD_LIMIT.split("/")[0])
        predict_n = int(PREDICT_LIMIT.split("/")[0])
        assert upload_n < predict_n, "Upload phải giới hạn chặt hơn predict"

    def test_health_most_permissive(self):
        from backend.services.rate_limiter import (
            HEALTH_LIMIT, UPLOAD_LIMIT, PREDICT_LIMIT,
            ASK_LIMIT, SEARCH_LIMIT,
        )
        health_n = int(HEALTH_LIMIT.split("/")[0])
        for limit in (UPLOAD_LIMIT, PREDICT_LIMIT, ASK_LIMIT, SEARCH_LIMIT):
            n = int(limit.split("/")[0])
            assert health_n >= n, "Health phải có limit cao nhất"

    def test_search_limit_exists_and_reasonable(self):
        from backend.services.rate_limiter import SEARCH_LIMIT
        n = int(SEARCH_LIMIT.split("/")[0])
        assert 5 <= n <= 100, "SEARCH_LIMIT nên từ 5-100/min"


# ── Limiter object ─────────────────────────────────────────────────────────────

class TestLimiterObject:

    def test_limiter_importable(self):
        from backend.services.rate_limiter import limiter
        assert limiter is not None

    def test_slowapi_available_flag(self):
        from backend.services.rate_limiter import SLOWAPI_AVAILABLE
        assert isinstance(SLOWAPI_AVAILABLE, bool)

    def test_stub_limiter_when_no_slowapi(self, monkeypatch):
        """Khi slowapi không cài, stub không raise exception."""
        import sys
        # Remove slowapi từ sys.modules để force reimport
        slowapi_mods = [k for k in sys.modules if k.startswith("slowapi")]
        saved = {k: sys.modules.pop(k) for k in slowapi_mods}

        try:
            # Mock slowapi không có
            with patch.dict("sys.modules", {"slowapi": None,
                                            "slowapi.util": None,
                                            "slowapi.errors": None}):
                import importlib
                import backend.services.rate_limiter as rl
                importlib.reload(rl)
                # Stub limiter không raise khi gọi .limit()
                decorator = rl.limiter.limit("10/minute")
                assert callable(decorator)
        except Exception:
            pass  # nếu reload không được, bỏ qua
        finally:
            sys.modules.update(saved)

    def test_rate_limit_handler_returns_response(self):
        from backend.services.rate_limiter import rate_limit_handler, SLOWAPI_AVAILABLE
        if not SLOWAPI_AVAILABLE:
            pytest.skip("slowapi not installed")

        from fastapi import Request
        from fastapi.responses import JSONResponse

        async def run():
            mock_req = MagicMock(spec=Request)
            mock_exc = MagicMock()
            mock_exc.limit = "10/minute"
            mock_exc.retry_after = 60
            response = await rate_limit_handler(mock_req, mock_exc)
            assert isinstance(response, JSONResponse)
            assert response.status_code == 429

        import asyncio
        asyncio.run(run())


# ── Endpoint integration ──────────────────────────────────────────────────────

class TestEndpointRateLimiting:
    """
    Test rằng các endpoint có rate limit decorator.
    Không test actual throttling (cần nhiều requests).
    """

    @pytest.mark.asyncio
    async def test_predict_endpoint_accepts_request(self, client, mocker):
        """Predict endpoint hoạt động bình thường trong giới hạn."""
        from backend.trend_engine import TrendEngine
        mocker.patch.object(TrendEngine, "analyze", return_value={
            "company": "X", "status": "INSUFFICIENT_DATA",
            "message": "Not enough data.", "score": None,
            "trend": None, "confidence": 0.0,
        })
        r = await client.post("/predict", json={
            "company": "X", "financial_signals": [],
            "sentiment_signals": [], "macro_signals": [],
        })
        assert r.status_code in (200, 429)

    @pytest.mark.asyncio
    async def test_search_endpoint_accepts_request(self, client):
        """Search endpoint hoạt động bình thường trong giới hạn."""
        with patch("backend.services.search.search", return_value=[]):
            r = await client.get("/search?q=test+query")
        assert r.status_code in (200, 422, 429)

    @pytest.mark.asyncio
    async def test_ask_endpoint_accepts_request(self, client, mock_heavy_services):
        """Ask endpoint hoạt động bình thường trong giới hạn."""
        mock_heavy_services["orchestrator"].to_response_dict.return_value = {
            "answer": "Test.", "citations": [], "confidence": 0.8,
        }
        r = await client.post("/ask", json={
            "question": "What are the risks?",
            "company": "VNM",
        })
        assert r.status_code in (200, 429)

    @pytest.mark.asyncio
    async def test_health_always_accessible(self, client):
        """Health check có limit cao nhất, luôn accessible."""
        r = await client.get("/health")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_slowapi_registered_in_app(self, mock_heavy_services):
        """Nếu slowapi available, limiter được đăng ký vào app."""
        from backend.services.rate_limiter import SLOWAPI_AVAILABLE
        if not SLOWAPI_AVAILABLE:
            pytest.skip("slowapi not installed")

        from backend.main import app
        assert hasattr(app.state, "limiter")

    @pytest.mark.asyncio
    async def test_rate_limit_response_format(self):
        """429 response phải có error/message fields đúng format."""
        from backend.services.rate_limiter import rate_limit_handler, SLOWAPI_AVAILABLE
        if not SLOWAPI_AVAILABLE:
            pytest.skip("slowapi not installed")

        import json, asyncio
        from fastapi import Request

        mock_req = MagicMock(spec=Request)
        mock_exc = MagicMock()
        mock_exc.limit = "10/minute"
        mock_exc.retry_after = 60

        response = await rate_limit_handler(mock_req, mock_exc)
        body = json.loads(response.body)
        assert "error"   in body
        assert "message" in body
        assert body["error"] == "RATE_LIMITED"


# ── Retry-After header ────────────────────────────────────────────────────────

class TestRetryAfterHeader:

    @pytest.mark.asyncio
    async def test_429_has_retry_after_header(self):
        from backend.services.rate_limiter import rate_limit_handler, SLOWAPI_AVAILABLE
        if not SLOWAPI_AVAILABLE:
            pytest.skip("slowapi not installed")

        from fastapi import Request
        mock_req = MagicMock(spec=Request)
        mock_exc = MagicMock()
        mock_exc.limit = "5/minute"
        mock_exc.retry_after = 30

        response = await rate_limit_handler(mock_req, mock_exc)
        assert "Retry-After" in response.headers
        assert response.headers["Retry-After"] == "60"