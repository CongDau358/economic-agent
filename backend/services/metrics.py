"""
backend/services/metrics.py  (TẠO MỚI)

In-memory metrics tracker — đo lường:
  - Số lần gọi mỗi endpoint
  - Latency trung bình
  - Error rate
  - Cache hit/miss ratio

Xem tại: GET /metrics  (thêm endpoint vào main.py)

Nâng cấp production: export sang Prometheus với prometheus_client
"""

from __future__ import annotations

import time
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EndpointStats:
    calls:        int   = 0
    errors:       int   = 0
    total_ms:     float = 0.0
    cache_hits:   int   = 0
    cache_misses: int   = 0

    @property
    def avg_latency_ms(self) -> float:
        return round(self.total_ms / self.calls, 2) if self.calls else 0.0

    @property
    def error_rate(self) -> float:
        return round(self.errors / self.calls, 4) if self.calls else 0.0

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return round(self.cache_hits / total, 4) if total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls":          self.calls,
            "errors":         self.errors,
            "error_rate":     self.error_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "cache_hit_rate": self.cache_hit_rate,
        }


class MetricsCollector:
    def __init__(self):
        self._stats:      dict[str, EndpointStats] = defaultdict(EndpointStats)
        self._started_at: float = time.time()

    def record_call(
        self,
        endpoint:    str,
        latency_ms:  float,
        is_error:    bool = False,
        cache_hit:   bool | None = None,
    ) -> None:
        s = self._stats[endpoint]
        s.calls      += 1
        s.total_ms   += latency_ms
        if is_error:
            s.errors += 1
        if cache_hit is True:
            s.cache_hits += 1
        elif cache_hit is False:
            s.cache_misses += 1

    def summary(self) -> dict[str, Any]:
        uptime_s = round(time.time() - self._started_at, 1)
        total_calls  = sum(s.calls  for s in self._stats.values())
        total_errors = sum(s.errors for s in self._stats.values())
        return {
            "uptime_seconds": uptime_s,
            "total_calls":    total_calls,
            "total_errors":   total_errors,
            "global_error_rate": round(total_errors / total_calls, 4) if total_calls else 0.0,
            "endpoints": {k: v.to_dict() for k, v in self._stats.items()},
        }

    def reset(self) -> None:
        self._stats.clear()
        self._started_at = time.time()


# ── Singleton ────────────────────────────────────────────────────────────────
metrics = MetricsCollector()


# ── Context manager để đo latency ────────────────────────────────────────────
@asynccontextmanager
async def track(endpoint: str, cache_hit: bool | None = None):
    """
    Dùng trong endpoint:

        async with track("predict") as t:
            result = trend_engine.analyze(...)
            t.cache_hit = False
    """
    start = time.perf_counter()
    is_error = False
    _cache_hit = cache_hit

    class _Ctx:
        cache_hit: bool | None = None

    ctx = _Ctx()
    try:
        yield ctx
    except Exception:
        is_error = True
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        metrics.record_call(
            endpoint=endpoint,
            latency_ms=elapsed_ms,
            is_error=is_error,
            cache_hit=ctx.cache_hit if ctx.cache_hit is not None else _cache_hit,
        )