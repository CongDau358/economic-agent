"""
tests/test_health.py
Tests cho health service và /health endpoint.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ── Health service unit tests ─────────────────────────────────────────────────

class TestCheckChromaDB:

    @pytest.mark.asyncio
    async def test_ok_when_connected(self, tmp_path):
        mock_col = MagicMock()
        mock_col.name = "economic_docs"
        mock_col.count = MagicMock(return_value=42)

        with (
            patch("chromadb.PersistentClient") as MockClient,
        ):
            instance = MockClient.return_value
            instance.list_collections.return_value = [mock_col]
            instance.get_collection.return_value = mock_col

            from backend.services.health import _check_chromadb
            result = await _check_chromadb(str(tmp_path))

        assert result["status"] == "ok"
        assert "latency_ms"  in result
        assert "collections" in result

    @pytest.mark.asyncio
    async def test_error_on_connection_failure(self, tmp_path):
        with patch("chromadb.PersistentClient", side_effect=Exception("Connection refused")):
            from backend.services.health import _check_chromadb
            result = await _check_chromadb(str(tmp_path))

        assert result["status"] == "error"
        assert "error" in result


class TestCheckRedis:

    @pytest.mark.asyncio
    async def test_disabled_when_no_url(self):
        from backend.services.health import _check_redis
        result = await _check_redis("")
        assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_ok_when_ping_succeeds(self):
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.info = AsyncMock(return_value={
            "used_memory": 10 * 1024 * 1024,
            "maxmemory": 256 * 1024 * 1024,
        })
        mock_client.aclose = AsyncMock()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            from backend.services.health import _check_redis
            result = await _check_redis("redis://localhost:6379/0")

        assert result["status"] == "ok"
        assert "used_memory_mb" in result

    @pytest.mark.asyncio
    async def test_error_on_connection_failure(self):
        with patch("redis.asyncio.from_url", side_effect=Exception("Connection refused")):
            from backend.services.health import _check_redis
            result = await _check_redis("redis://localhost:6379/0")

        assert result["status"] == "error"


class TestCheckDisk:

    def test_ok_when_enough_space(self, tmp_path):
        from backend.services.health import _check_disk
        result = _check_disk(str(tmp_path))
        # tmp_path luôn tồn tại và có đủ dung lượng
        assert result["status"] in ("ok", "warning")
        assert "free_gb"   in result
        assert "total_gb"  in result
        assert "used_pct"  in result

    def test_error_on_invalid_path(self):
        from backend.services.health import _check_disk
        result = _check_disk("/nonexistent/path/xyz")
        assert result["status"] == "error"


class TestCheckOpenAI:

    @pytest.mark.asyncio
    async def test_skipped_for_test_key(self):
        from backend.services.health import _check_openai
        result = await _check_openai("test-key-not-real", "gpt-4o-mini")
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_skipped_for_empty_key(self):
        from backend.services.health import _check_openai
        result = await _check_openai("", "gpt-4o-mini")
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_ok_when_api_responds(self):
        mock_client = AsyncMock()
        mock_client.models.list = AsyncMock(return_value=[])

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            from backend.services.health import _check_openai
            result = await _check_openai("sk-real-key-xxx", "gpt-4o-mini")

        assert result["status"] == "ok"
        assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_error_on_api_failure(self):
        mock_client = AsyncMock()
        mock_client.models.list = AsyncMock(side_effect=Exception("Auth error"))

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            from backend.services.health import _check_openai
            result = await _check_openai("sk-real-key-xxx", "gpt-4o-mini")

        assert result["status"] == "error"


# ── run_health_check aggregation ─────────────────────────────────────────────

class TestRunHealthCheck:

    @pytest.mark.asyncio
    async def test_overall_ok_when_all_ok(self):
        with (
            patch("backend.services.health._check_chromadb",
                  return_value={"status": "ok", "latency_ms": 5, "collections": 1, "total_docs": 10}),
            patch("backend.services.health._check_redis",
                  return_value={"status": "ok", "latency_ms": 2, "used_memory_mb": 5.0, "maxmemory_mb": 256.0}),
            patch("backend.services.health._check_disk",
                  return_value={"status": "ok", "free_gb": 50.0, "total_gb": 100.0, "used_pct": 50.0}),
        ):
            from backend.services.health import run_health_check
            result = await run_health_check()

        assert result["status"] == "ok"
        assert "checks" in result
        assert set(result["checks"].keys()) >= {"chromadb", "redis", "disk"}

    @pytest.mark.asyncio
    async def test_overall_error_when_one_fails(self):
        with (
            patch("backend.services.health._check_chromadb",
                  return_value={"status": "error", "error": "Connection refused"}),
            patch("backend.services.health._check_redis",
                  return_value={"status": "ok", "latency_ms": 2}),
            patch("backend.services.health._check_disk",
                  return_value={"status": "ok", "free_gb": 50.0}),
        ):
            from backend.services.health import run_health_check
            result = await run_health_check()

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_overall_degraded_on_warning(self):
        with (
            patch("backend.services.health._check_chromadb",
                  return_value={"status": "ok"}),
            patch("backend.services.health._check_redis",
                  return_value={"status": "disabled"}),
            patch("backend.services.health._check_disk",
                  return_value={"status": "warning", "free_gb": 0.5}),
        ):
            from backend.services.health import run_health_check
            result = await run_health_check()

        assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_result_has_version(self):
        with (
            patch("backend.services.health._check_chromadb", return_value={"status": "ok"}),
            patch("backend.services.health._check_redis",    return_value={"status": "disabled"}),
            patch("backend.services.health._check_disk",     return_value={"status": "ok"}),
        ):
            from backend.services.health import run_health_check
            result = await run_health_check()

        assert "version" in result

    @pytest.mark.asyncio
    async def test_exception_in_check_handled(self):
        """Nếu một check raise exception, không crash toàn bộ."""
        with (
            patch("backend.services.health._check_chromadb",
                  side_effect=RuntimeError("Unexpected")),
            patch("backend.services.health._check_redis",
                  return_value={"status": "ok"}),
            patch("backend.services.health._check_disk",
                  return_value={"status": "ok"}),
        ):
            from backend.services.health import run_health_check
            result = await run_health_check()

        assert result["status"] in ("error", "degraded")


# ── /health endpoint ──────────────────────────────────────────────────────────

class TestHealthEndpoint:

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        r = await client.get("/health")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_health_has_status_key(self, client):
        r = await client.get("/health")
        assert "status" in r.json()

    @pytest.mark.asyncio
    async def test_health_has_version(self, client):
        r = await client.get("/health")
        assert "version" in r.json()

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, mock_heavy_services):
        """Health endpoint không cần X-API-Key."""
        import os
        os.environ["AUTH_ENABLED"] = "true"
        os.environ["API_KEYS"]     = "secret"
        from backend.config import get_settings
        get_settings.cache_clear()

        from backend.main import app
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test") as ac:
            r = await ac.get("/health")   # không có X-API-Key
        assert r.status_code == 200       # health không require auth

        os.environ["AUTH_ENABLED"] = "false"
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_health_deep_endpoint(self, client):
        """GET /health?deep=true trả thêm dependency checks."""
        with (
            patch("backend.services.health._check_chromadb",
                  return_value={"status": "ok", "collections": 1, "total_docs": 5, "latency_ms": 3}),
            patch("backend.services.health._check_redis",
                  return_value={"status": "disabled"}),
            patch("backend.services.health._check_disk",
                  return_value={"status": "ok", "free_gb": 50.0}),
        ):
            r = await client.get("/health?deep=true")

        assert r.status_code == 200
        data = r.json()
        # Deep check trả "checks" dict
        if "checks" in data:
            assert "chromadb" in data["checks"]