"""
backend/services/health.py  (TẠO MỚI)

Deep health check — kiểm tra tất cả dependencies thực tế:
  - ChromaDB vector store
  - Redis cache
  - OpenAI API connectivity
  - Disk space (data directories)

Dùng trong endpoint:

    from .services.health import run_health_check

    @app.get("/health")
    async def health():
        return await run_health_check()
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any

from .logger import get_logger

log = get_logger("economic_agent.health")


# ── Individual checks ─────────────────────────────────────────────────────────

async def _check_chromadb(persist_dir: str) -> dict[str, Any]:
    """Kiểm tra ChromaDB: có connect được không, có bao nhiêu documents."""
    start = time.perf_counter()
    try:
        import chromadb
        client = await asyncio.to_thread(
            chromadb.PersistentClient, path=persist_dir
        )
        collections = await asyncio.to_thread(client.list_collections)
        total_docs = 0
        for col in collections:
            c = await asyncio.to_thread(client.get_collection, col.name)
            total_docs += await asyncio.to_thread(lambda: c.count())

        return {
            "status":      "ok",
            "latency_ms":  round((time.perf_counter() - start) * 1000, 2),
            "collections": len(collections),
            "total_docs":  total_docs,
            "persist_dir": persist_dir,
        }
    except Exception as exc:
        return {
            "status":    "error",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "error":     str(exc),
        }


async def _check_redis(redis_url: str) -> dict[str, Any]:
    """Kiểm tra Redis: ping và lấy memory info."""
    if not redis_url:
        return {"status": "disabled", "note": "REDIS_URL not set — using in-memory cache"}

    start = time.perf_counter()
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(redis_url, decode_responses=True)
        await client.ping()
        info = await client.info("memory")
        await client.aclose()
        return {
            "status":          "ok",
            "latency_ms":      round((time.perf_counter() - start) * 1000, 2),
            "used_memory_mb":  round(info.get("used_memory", 0) / 1024 / 1024, 2),
            "maxmemory_mb":    round(info.get("maxmemory", 0) / 1024 / 1024, 2),
        }
    except ImportError:
        return {"status": "disabled", "note": "redis[asyncio] not installed"}
    except Exception as exc:
        return {
            "status":    "error",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "error":     str(exc),
        }


async def _check_openai(api_key: str, model: str) -> dict[str, Any]:
    """Kiểm tra OpenAI API: list models để xác nhận key hợp lệ."""
    if not api_key or api_key.startswith("test-"):
        return {"status": "skipped", "note": "Skipped in test environment"}

    start = time.perf_counter()
    try:
        import openai
        client = openai.AsyncOpenAI(api_key=api_key)
        await asyncio.wait_for(client.models.list(), timeout=5.0)
        return {
            "status":     "ok",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "model":      model,
        }
    except asyncio.TimeoutError:
        return {"status": "timeout", "latency_ms": 5000, "error": "OpenAI API timeout (5s)"}
    except Exception as exc:
        return {
            "status":    "error",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "error":     str(exc)[:120],
        }


def _check_disk(data_dir: str) -> dict[str, Any]:
    """Kiểm tra dung lượng đĩa cho data directory."""
    try:
        path = Path(data_dir)
        stat = os.statvfs(str(path)) if hasattr(os, "statvfs") else None
        if stat:
            total_gb = round(stat.f_blocks * stat.f_frsize / 1e9, 2)
            free_gb  = round(stat.f_bavail * stat.f_frsize / 1e9, 2)
            used_pct = round((1 - stat.f_bavail / max(stat.f_blocks, 1)) * 100, 1)
            status   = "warning" if free_gb < 1.0 else "ok"
            return {
                "status":   status,
                "path":     str(path),
                "total_gb": total_gb,
                "free_gb":  free_gb,
                "used_pct": used_pct,
            }
        # Windows fallback
        import shutil
        total, used, free = shutil.disk_usage(str(path))
        free_gb  = round(free  / 1e9, 2)
        total_gb = round(total / 1e9, 2)
        used_pct = round(used / total * 100, 1)
        return {
            "status":   "warning" if free_gb < 1.0 else "ok",
            "path":     str(path),
            "total_gb": total_gb,
            "free_gb":  free_gb,
            "used_pct": used_pct,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ── Aggregated health check ───────────────────────────────────────────────────

async def run_health_check(
    include_openai: bool = False,   # tốn thời gian, default off
) -> dict[str, Any]:
    """
    Chạy tất cả health checks song song.
    Trả về status tổng hợp: ok | degraded | error
    """
    from backend.config import get_settings
    settings = get_settings()

    checks_coros = {
        "chromadb": _check_chromadb(settings.chroma_persist_dir),
        "redis":    _check_redis(settings.redis_url),
        "disk":     asyncio.to_thread(_check_disk, settings.raw_data_dir),
    }
    if include_openai:
        checks_coros["openai"] = _check_openai(
            settings.openai_api_key, settings.openai_model
        )

    results = await asyncio.gather(*checks_coros.values(), return_exceptions=True)
    checks = {}
    for name, result in zip(checks_coros.keys(), results):
        if isinstance(result, Exception):
            checks[name] = {"status": "error", "error": str(result)}
        else:
            checks[name] = result

    # Overall status
    statuses = [c.get("status", "error") for c in checks.values()]
    if all(s in ("ok", "skipped", "disabled") for s in statuses):
        overall = "ok"
    elif any(s == "error" for s in statuses):
        overall = "error"
    else:
        overall = "degraded"

    return {
        "status":   overall,
        "version":  "1.1.0",
        "checks":   checks,
    }