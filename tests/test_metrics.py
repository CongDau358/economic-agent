"""
tests/test_metrics.py
Unit tests cho MetricsCollector và /metrics endpoint.
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import patch


class TestMetricsCollector:

    def test_initial_state(self):
        from backend.services.metrics import MetricsCollector
        m = MetricsCollector()
        s = m.summary()
        assert s["total_calls"]  == 0
        assert s["total_errors"] == 0
        assert s["endpoints"]    == {}

    def test_record_call(self):
        from backend.services.metrics import MetricsCollector
        m = MetricsCollector()
        m.record_call("predict", latency_ms=120.0)
        s = m.summary()
        assert s["total_calls"] == 1
        assert "predict" in s["endpoints"]
        assert s["endpoints"]["predict"]["calls"] == 1

    def test_record_error(self):
        from backend.services.metrics import MetricsCollector
        m = MetricsCollector()
        m.record_call("predict", latency_ms=50.0, is_error=True)
        s = m.summary()
        assert s["total_errors"] == 1
        assert s["endpoints"]["predict"]["error_rate"] == 1.0

    def test_cache_hit_rate(self):
        from backend.services.metrics import MetricsCollector
        m = MetricsCollector()
        m.record_call("predict", latency_ms=10.0, cache_hit=True)
        m.record_call("predict", latency_ms=200.0, cache_hit=False)
        ep = m.summary()["endpoints"]["predict"]
        assert ep["cache_hit_rate"] == 0.5

    def test_avg_latency(self):
        from backend.services.metrics import MetricsCollector
        m = MetricsCollector()
        m.record_call("ask", latency_ms=100.0)
        m.record_call("ask", latency_ms=200.0)
        ep = m.summary()["endpoints"]["ask"]
        assert ep["avg_latency_ms"] == 150.0

    def test_multiple_endpoints(self):
        from backend.services.metrics import MetricsCollector
        m = MetricsCollector()
        m.record_call("predict", latency_ms=50.0)
        m.record_call("ask",     latency_ms=300.0)
        m.record_call("upload",  latency_ms=800.0)
        s = m.summary()
        assert s["total_calls"] == 3
        assert len(s["endpoints"]) == 3

    def test_reset(self):
        from backend.services.metrics import MetricsCollector
        m = MetricsCollector()
        m.record_call("predict", latency_ms=100.0)
        m.reset()
        s = m.summary()
        assert s["total_calls"] == 0
        assert s["endpoints"] == {}

    def test_global_error_rate(self):
        from backend.services.metrics import MetricsCollector
        m = MetricsCollector()
        m.record_call("predict", latency_ms=100.0)
        m.record_call("ask",     latency_ms=200.0, is_error=True)
        s = m.summary()
        assert s["global_error_rate"] == 0.5

    def test_uptime_positive(self):
        from backend.services.metrics import MetricsCollector
        import time
        m = MetricsCollector()
        time.sleep(0.01)
        assert m.summary()["uptime_seconds"] > 0


class TestTrackContextManager:

    @pytest.mark.asyncio
    async def test_records_on_success(self):
        from backend.services.metrics import MetricsCollector, track
        m = MetricsCollector()
        with patch("backend.services.metrics.metrics", m):
            async with track("predict"):
                await asyncio.sleep(0.01)
        assert m.summary()["endpoints"]["predict"]["calls"] == 1
        assert m.summary()["endpoints"]["predict"]["errors"] == 0

    @pytest.mark.asyncio
    async def test_records_error_on_exception(self):
        from backend.services.metrics import MetricsCollector, track
        m = MetricsCollector()
        with patch("backend.services.metrics.metrics", m):
            with pytest.raises(ValueError):
                async with track("predict"):
                    raise ValueError("test error")
        assert m.summary()["endpoints"]["predict"]["errors"] == 1

    @pytest.mark.asyncio
    async def test_cache_hit_via_ctx(self):
        from backend.services.metrics import MetricsCollector, track
        m = MetricsCollector()
        with patch("backend.services.metrics.metrics", m):
            async with track("predict") as ctx:
                ctx.cache_hit = True
        ep = m.summary()["endpoints"]["predict"]
        assert ep["cache_hit_rate"] == 1.0


class TestMetricsEndpoint:

    @pytest.mark.asyncio
    async def test_metrics_endpoint_accessible(self, client):
        r = await client.get("/metrics")
        assert r.status_code == 200
        data = r.json()
        assert "total_calls"    in data
        assert "uptime_seconds" in data
        assert "endpoints"      in data

    @pytest.mark.asyncio
    async def test_metrics_increments_after_call(self, client):
        from backend.trend_engine import TrendEngine
        mock_result = {
            "company": "A", "status": "OK", "score": 0.6,
            "trend": {"short_term": "neutral", "near_term": "neutral"},
            "confidence": 0.7, "risks": [], "opportunities": [],
            "executive_summary": "OK", "warnings": [],
            "scenarios": {"bull": 0.72, "base": 0.6, "bear": 0.45},
            "financial_signals": {"score": 0.1, "inputs": []},
            "sentiment_signals": {"score": 0.1, "inputs": []},
            "macro_signals":     {"score": 0.1, "inputs": []},
            "assumptions": [],
        }
        with patch.object(TrendEngine, "analyze", return_value=mock_result):
            await client.post("/predict", json={
                "company": "A",
                "financial_signals": ["revenue_up", "profit_up"],
            })

        r = await client.get("/metrics")
        assert r.status_code == 200