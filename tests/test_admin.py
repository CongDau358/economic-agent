"""
tests/test_admin.py
Tests cho admin endpoints.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── /admin/cache ──────────────────────────────────────────────────────────────

class TestAdminCache:

    @pytest.mark.asyncio
    async def test_clear_cache_returns_ok(self, auth_client):
        from backend.services.cache import InMemoryCache
        mock_cache = InMemoryCache()
        await mock_cache.set("k", "v")

        with patch("backend.admin.get_cache", return_value=mock_cache):
            r = await auth_client.delete("/admin/cache")

        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert await mock_cache.get("k") is None

    @pytest.mark.asyncio
    async def test_clear_cache_requires_auth(self, client):
        """Không có X-API-Key khi AUTH_ENABLED=true → 401."""
        import os
        os.environ["AUTH_ENABLED"] = "true"
        os.environ["API_KEYS"]     = "secret"
        from backend.config import get_settings
        get_settings.cache_clear()

        from backend.main import app
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test") as ac:
            r = await ac.delete("/admin/cache")
        assert r.status_code == 401

        os.environ["AUTH_ENABLED"] = "false"
        get_settings.cache_clear()


# ── /admin/jobs ───────────────────────────────────────────────────────────────

class TestAdminJobs:

    @pytest.mark.asyncio
    async def test_clear_done_jobs(self, auth_client):
        from backend.services.job_store import job_store, JobStatus
        await job_store.create("jdone1", company="A", source_type="text")
        await job_store.update("jdone1", JobStatus.DONE, result={})

        r = await auth_client.delete("/admin/jobs")
        assert r.status_code == 200
        data = r.json()
        assert "removed" in data
        assert data["removed"] >= 1

    @pytest.mark.asyncio
    async def test_clear_jobs_with_status_filter(self, auth_client):
        from backend.services.job_store import job_store, JobStatus
        await job_store.create("jfail1", company="B", source_type="pdf")
        await job_store.update("jfail1", JobStatus.FAILED, error="err")

        r = await auth_client.delete("/admin/jobs?status=failed")
        assert r.status_code == 200
        assert r.json()["status_filter"] == "failed"

    @pytest.mark.asyncio
    async def test_clear_jobs_invalid_status(self, auth_client):
        r = await auth_client.delete("/admin/jobs?status=not_real")
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_pending_jobs_not_deleted_by_default(self, auth_client):
        from backend.services.job_store import job_store, JobStatus
        await job_store.create("jpend1", company="C", source_type="text")
        # pending → không bị xóa khi clear done+failed

        r = await auth_client.delete("/admin/jobs")
        assert r.status_code == 200

        job = await job_store.get("jpend1")
        assert job is not None  # pending vẫn còn


# ── /admin/stats ──────────────────────────────────────────────────────────────

class TestAdminStats:

    @pytest.mark.asyncio
    async def test_stats_returns_200(self, auth_client):
        with patch("backend.admin._get_chroma_collection") as mock_col:
            instance = MagicMock()
            instance.count.return_value = 42
            instance.get.return_value = {
                "ids": ["id1", "id2"],
                "metadatas": [{"company": "VNM"}, {"company": "VNM"}],
            }
            mock_col.return_value = instance
            r = await auth_client.get("/admin/stats")

        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_stats_has_required_keys(self, auth_client):
        with patch("backend.admin._get_chroma_collection") as mock_col:
            instance = MagicMock()
            instance.count.return_value = 0
            instance.get.return_value = {"ids": [], "metadatas": []}
            mock_col.return_value = instance
            r = await auth_client.get("/admin/stats")

        data = r.json()
        assert "vector_store" in data
        assert "jobs"         in data
        assert "cache"        in data
        assert "metrics"      in data

    @pytest.mark.asyncio
    async def test_stats_vector_error_handled(self, auth_client):
        """ChromaDB error không crash /admin/stats."""
        with patch("backend.admin._get_chroma_collection",
                   side_effect=Exception("ChromaDB unavailable")):
            r = await auth_client.get("/admin/stats")

        assert r.status_code == 200
        assert "error" in r.json()["vector_store"]


# ── /admin/documents ──────────────────────────────────────────────────────────

class TestAdminDocuments:

    @pytest.mark.asyncio
    async def test_list_documents_returns_200(self, auth_client):
        with patch("backend.admin._get_chroma_collection") as mock_col:
            instance = MagicMock()
            instance.get.return_value = {
                "ids": ["doc1", "doc2"],
                "metadatas": [
                    {"company": "VNM", "sector": "CS", "source": "report.pdf"},
                    {"company": "VNM", "sector": "CS", "source": "news.html"},
                ],
            }
            mock_col.return_value = instance
            r = await auth_client.get("/admin/documents?company=VNM")

        assert r.status_code == 200
        data = r.json()
        assert "documents" in data
        assert "count"     in data

    @pytest.mark.asyncio
    async def test_list_documents_count_matches(self, auth_client):
        with patch("backend.admin._get_chroma_collection") as mock_col:
            instance = MagicMock()
            instance.get.return_value = {
                "ids": ["d1", "d2", "d3"],
                "metadatas": [{"company": "X"}] * 3,
            }
            mock_col.return_value = instance
            r = await auth_client.get("/admin/documents")

        data = r.json()
        assert data["count"] == len(data["documents"])

    @pytest.mark.asyncio
    async def test_list_documents_limit_query(self, auth_client):
        with patch("backend.admin._get_chroma_collection") as mock_col:
            instance = MagicMock()
            instance.get.return_value = {"ids": [], "metadatas": []}
            mock_col.return_value = instance
            r = await auth_client.get("/admin/documents?limit=5")

        assert r.status_code == 200


# ── /admin/collection DELETE ──────────────────────────────────────────────────

class TestAdminDeleteCollection:

    @pytest.mark.asyncio
    async def test_delete_without_confirm_returns_400(self, auth_client):
        r = await auth_client.delete(
            "/admin/collection",
            json={"company": "VNM", "confirm": False},
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_with_confirm_returns_200(self, auth_client):
        with patch("backend.admin._get_chroma_collection") as mock_col:
            instance = MagicMock()
            instance.get.return_value = {"ids": ["id1", "id2"]}
            instance.delete = MagicMock()
            mock_col.return_value = instance

            r = await auth_client.delete(
                "/admin/collection",
                json={"company": "VNM", "confirm": True},
            )

        assert r.status_code == 200
        data = r.json()
        assert data["company"]  == "VNM"
        assert data["deleted"]  == 2

    @pytest.mark.asyncio
    async def test_delete_calls_collection_delete(self, auth_client):
        with patch("backend.admin._get_chroma_collection") as mock_col:
            instance = MagicMock()
            instance.get.return_value = {"ids": ["id1"]}
            instance.delete = MagicMock()
            mock_col.return_value = instance

            await auth_client.delete(
                "/admin/collection",
                json={"company": "TestCo", "confirm": True},
            )

        instance.delete.assert_called_once_with(ids=["id1"])


# ── /admin/metrics/reset ──────────────────────────────────────────────────────

class TestAdminMetricsReset:

    @pytest.mark.asyncio
    async def test_reset_metrics_returns_ok(self, auth_client):
        from backend.services.metrics import metrics
        metrics.record_call("predict", latency_ms=100.0)
        assert metrics.summary()["total_calls"] > 0

        r = await auth_client.post("/admin/metrics/reset")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert metrics.summary()["total_calls"] == 0