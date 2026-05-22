"""
tests/test_services.py
Unit tests cho cache, job_store, logger, rate_limiter.
"""

from __future__ import annotations

import asyncio
import time
import pytest


# ── Cache ─────────────────────────────────────────────────────────────────────

class TestInMemoryCache:

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        from backend.services.cache import InMemoryCache
        c = InMemoryCache()
        await c.set("k", {"x": 1})
        assert await c.get("k") == {"x": 1}

    @pytest.mark.asyncio
    async def test_miss_returns_none(self):
        from backend.services.cache import InMemoryCache
        c = InMemoryCache()
        assert await c.get("missing") is None

    @pytest.mark.asyncio
    async def test_expired_entry_returns_none(self):
        from backend.services.cache import InMemoryCache
        c = InMemoryCache()
        await c.set("k", "v", ttl=1)
        time.sleep(1.1)
        assert await c.get("k") is None

    @pytest.mark.asyncio
    async def test_delete(self):
        from backend.services.cache import InMemoryCache
        c = InMemoryCache()
        await c.set("k", "v")
        await c.delete("k")
        assert await c.get("k") is None

    @pytest.mark.asyncio
    async def test_clear(self):
        from backend.services.cache import InMemoryCache
        c = InMemoryCache()
        await c.set("a", 1)
        await c.set("b", 2)
        await c.clear()
        assert await c.get("a") is None
        assert await c.get("b") is None

    @pytest.mark.asyncio
    async def test_overwrite(self):
        from backend.services.cache import InMemoryCache
        c = InMemoryCache()
        await c.set("k", "v1")
        await c.set("k", "v2")
        assert await c.get("k") == "v2"

    @pytest.mark.asyncio
    async def test_stats(self):
        from backend.services.cache import InMemoryCache
        c = InMemoryCache(default_ttl=60)
        await c.set("k1", 1)
        await c.set("k2", 2)
        stats = c.stats()
        assert stats["live_keys"] == 2

    @pytest.mark.asyncio
    async def test_concurrent_writes(self):
        from backend.services.cache import InMemoryCache
        c = InMemoryCache()
        await asyncio.gather(*[c.set(f"k{i}", i) for i in range(50)])
        results = await asyncio.gather(*[c.get(f"k{i}") for i in range(50)])
        assert results == list(range(50))


class TestCacheKey:

    def test_deterministic(self):
        from backend.services.cache import make_cache_key
        k1 = make_cache_key("p", company="A", signals=["x", "y"])
        k2 = make_cache_key("p", company="A", signals=["x", "y"])
        assert k1 == k2

    def test_different_inputs_differ(self):
        from backend.services.cache import make_cache_key
        assert make_cache_key("p", a=1) != make_cache_key("p", a=2)

    def test_different_prefix_differs(self):
        from backend.services.cache import make_cache_key
        assert make_cache_key("predict", x=1) != make_cache_key("ask", x=1)

    def test_key_no_whitespace(self):
        from backend.services.cache import make_cache_key
        key = make_cache_key("predict", company="Viet Nam Corp")
        assert " " not in key


# ── Job Store ─────────────────────────────────────────────────────────────────

class TestJobStore:

    @pytest.mark.asyncio
    async def test_create_and_get(self):
        from backend.services.job_store import InMemoryJobStore, JobStatus
        s = InMemoryJobStore()
        job = await s.create("j1", company="VNM", source_type="pdf")
        assert job.status == JobStatus.PENDING
        got = await s.get("j1")
        assert got is not None
        assert got.company == "VNM"

    @pytest.mark.asyncio
    async def test_update_status(self):
        from backend.services.job_store import InMemoryJobStore, JobStatus
        s = InMemoryJobStore()
        await s.create("j2", company="VNM", source_type="text")
        await s.update("j2", JobStatus.RUNNING)
        job = await s.get("j2")
        assert job.status == JobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_update_with_result(self):
        from backend.services.job_store import InMemoryJobStore, JobStatus
        s = InMemoryJobStore()
        await s.create("j3", company="VNM", source_type="text")
        await s.update("j3", JobStatus.DONE, result={"chunk_count": 10})
        job = await s.get("j3")
        assert job.status == JobStatus.DONE
        assert job.result["chunk_count"] == 10

    @pytest.mark.asyncio
    async def test_update_with_error(self):
        from backend.services.job_store import InMemoryJobStore, JobStatus
        s = InMemoryJobStore()
        await s.create("j4", company="VNM", source_type="pdf")
        await s.update("j4", JobStatus.FAILED, error="PDF parse error")
        job = await s.get("j4")
        assert job.status == JobStatus.FAILED
        assert job.error == "PDF parse error"

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        from backend.services.job_store import InMemoryJobStore
        s = InMemoryJobStore()
        assert await s.get("no-such-id") is None

    @pytest.mark.asyncio
    async def test_list_all(self):
        from backend.services.job_store import InMemoryJobStore
        s = InMemoryJobStore()
        await s.create("la1", company="VNM", source_type="pdf")
        await s.create("la2", company="VCB", source_type="text")
        jobs = await s.list_jobs()
        ids = [j["job_id"] for j in jobs]
        assert "la1" in ids
        assert "la2" in ids

    @pytest.mark.asyncio
    async def test_list_filter_by_company(self):
        from backend.services.job_store import InMemoryJobStore
        s = InMemoryJobStore()
        await s.create("fc1", company="Vinamilk", source_type="pdf")
        await s.create("fc2", company="VCB",      source_type="text")
        jobs = await s.list_jobs(company="Vinamilk")
        assert all(j["company"] == "Vinamilk" for j in jobs)

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self):
        from backend.services.job_store import InMemoryJobStore, JobStatus
        s = InMemoryJobStore()
        await s.create("fs1", company="A", source_type="text")
        await s.create("fs2", company="B", source_type="text")
        await s.update("fs1", JobStatus.DONE, result={})
        done_jobs = await s.list_jobs(status=JobStatus.DONE)
        assert all(j["status"] == "done" for j in done_jobs)

    @pytest.mark.asyncio
    async def test_list_limit(self):
        from backend.services.job_store import InMemoryJobStore
        s = InMemoryJobStore()
        for i in range(10):
            await s.create(f"lim{i}", company="A", source_type="text")
        jobs = await s.list_jobs(limit=5)
        assert len(jobs) <= 5

    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        from backend.services.job_store import InMemoryJobStore, JobStatus
        s = InMemoryJobStore(ttl_seconds=0)  # expire ngay
        await s.create("exp1", company="A", source_type="text")
        await s.update("exp1", JobStatus.DONE, result={})
        removed = await s.cleanup_expired()
        assert removed >= 1
        assert await s.get("exp1") is None

    @pytest.mark.asyncio
    async def test_to_dict_keys(self):
        from backend.services.job_store import InMemoryJobStore, JobStatus
        s = InMemoryJobStore()
        await s.create("td1", company="VNM", source_type="pdf")
        job = await s.get("td1")
        d = job.to_dict()
        for key in ("job_id", "status", "company", "source_type",
                    "created_at", "updated_at", "result", "error"):
            assert key in d

    @pytest.mark.asyncio
    async def test_stats(self):
        from backend.services.job_store import InMemoryJobStore, JobStatus
        s = InMemoryJobStore()
        await s.create("st1", company="A", source_type="text")
        await s.create("st2", company="B", source_type="text")
        await s.update("st1", JobStatus.DONE, result={})
        stats = s.stats
        assert stats["total"] >= 2
        assert "done" in stats


# ── Logger ────────────────────────────────────────────────────────────────────

class TestLogger:

    def test_setup_logging_does_not_raise(self):
        from backend.services.logger import setup_logging
        setup_logging(level="WARNING", json_logs=False)

    def test_setup_logging_json(self):
        from backend.services.logger import setup_logging
        setup_logging(level="WARNING", json_logs=True)

    def test_get_logger_returns_logger(self):
        import logging
        from backend.services.logger import get_logger
        log = get_logger("test.module")
        assert isinstance(log, logging.Logger)
        assert log.name == "test.module"

    def test_json_formatter_produces_valid_json(self):
        import json, logging
        from backend.services.logger import JSONFormatter
        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=0, msg="hello world", args=(), exc_info=None,
        )
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["msg"] == "hello world"
        assert parsed["level"] == "INFO"
        assert "ts" in parsed


# ── Rate limiter ──────────────────────────────────────────────────────────────

class TestRateLimiter:

    def test_limiter_importable(self):
        from backend.services.rate_limiter import limiter, SLOWAPI_AVAILABLE
        assert limiter is not None

    def test_limit_constants_defined(self):
        from backend.services.rate_limiter import (
            UPLOAD_LIMIT, PREDICT_LIMIT, ASK_LIMIT, HEALTH_LIMIT
        )
        for limit in (UPLOAD_LIMIT, PREDICT_LIMIT, ASK_LIMIT, HEALTH_LIMIT):
            assert "/" in limit   # format: "N/unit"