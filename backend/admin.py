"""
backend/admin.py  (TẠO MỚI)

Admin endpoints — quản trị hệ thống.
Đăng ký vào main.py:

    from .admin import admin_router
    app.include_router(admin_router)

Endpoints:
    DELETE /admin/cache           — xóa cache
    DELETE /admin/jobs            — xóa job history
    GET    /admin/stats           — thống kê tổng hợp
    POST   /admin/reindex         — reindex vector store
    DELETE /admin/collection      — xóa toàn bộ documents của 1 company
    GET    /admin/documents        — liệt kê documents theo company/sector
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .auth import require_api_key
from .config import get_settings
from .services.cache import get_cache
from .services.job_store import job_store
from .services.logger import get_logger
from .services.metrics import metrics

log = get_logger("economic_agent.admin")

admin_router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Request models ────────────────────────────────────────────────────────────

class ReindexRequest(BaseModel):
    company:    Optional[str] = None   # None = reindex toàn bộ
    collection: Optional[str] = None


class DeleteCollectionRequest(BaseModel):
    company: str
    confirm: bool = False              # phải True mới xóa


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_chroma_collection():
    settings = get_settings()
    import chromadb
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return client.get_or_create_collection(settings.chroma_collection_name)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@admin_router.delete("/cache")
async def clear_cache(
    _: str = Depends(require_api_key),
) -> dict:
    """Xóa toàn bộ cache (in-memory hoặc Redis)."""
    cache = get_cache()
    await cache.clear()
    log.info("admin.cache_cleared")
    return {"message": "Cache đã được xóa", "status": "ok"}


@admin_router.delete("/jobs")
async def clear_jobs(
    status: Optional[str] = Query(None, description="Chỉ xóa jobs có status này"),
    _: str = Depends(require_api_key),
) -> dict:
    """Xóa job history (mặc định xóa done + failed, giữ pending + running)."""
    from .services.job_store import JobStatus

    async with job_store._lock:
        if status:
            try:
                target = JobStatus(status)
            except ValueError:
                raise HTTPException(400, f"Status không hợp lệ: {status}")
            removed = [k for k, v in job_store._store.items() if v.status == target]
        else:
            # Chỉ xóa jobs đã kết thúc, không xóa pending/running
            safe = {JobStatus.DONE, JobStatus.FAILED}
            removed = [k for k, v in job_store._store.items() if v.status in safe]

        for k in removed:
            del job_store._store[k]

    log.info("admin.jobs_cleared", extra={"count": len(removed), "status_filter": status})
    return {
        "message": f"Đã xóa {len(removed)} jobs",
        "removed": len(removed),
        "status_filter": status or "done + failed",
    }


@admin_router.get("/stats")
async def get_stats(
    _: str = Depends(require_api_key),
) -> dict:
    """Thống kê tổng hợp: vector store, jobs, cache, metrics."""
    settings = get_settings()

    # Vector store stats
    vector_stats: dict = {}
    try:
        collection = await asyncio.to_thread(_get_chroma_collection)
        total_docs = await asyncio.to_thread(collection.count)
        # Thống kê theo company
        results = await asyncio.to_thread(
            collection.get, include=["metadatas"]
        )
        companies: dict[str, int] = {}
        for meta in (results.get("metadatas") or []):
            co = meta.get("company", "unknown") if meta else "unknown"
            companies[co] = companies.get(co, 0) + 1
        vector_stats = {
            "total_documents": total_docs,
            "companies":       companies,
            "collection":      settings.chroma_collection_name,
        }
    except Exception as exc:
        vector_stats = {"error": str(exc)}

    # Cache stats
    cache = get_cache()
    cache_stats = getattr(cache, "stats", lambda: {})()

    return {
        "vector_store": vector_stats,
        "jobs":         job_store.stats,
        "cache":        cache_stats,
        "metrics":      metrics.summary(),
    }


@admin_router.post("/reindex")
async def reindex(
    body: ReindexRequest,
    _: str = Depends(require_api_key),
) -> dict:
    """
    Reindex: xóa embeddings cũ và embed lại từ processed files.
    Nếu company=None → reindex toàn bộ collection.
    """
    settings = get_settings()
    import json
    from pathlib import Path

    processed_dir = Path(settings.processed_data_dir)
    if not processed_dir.exists():
        raise HTTPException(400, f"Thư mục processed không tồn tại: {processed_dir}")

    # Tìm files cần reindex
    json_files = list(processed_dir.glob("*.json"))
    if body.company:
        safe = body.company.replace(" ", "_").lower()
        json_files = [f for f in json_files if safe in f.name.lower()]

    if not json_files:
        return {"message": "Không tìm thấy documents cần reindex", "reindexed": 0}

    # Load chunks
    all_chunks: list[dict] = []
    for f in json_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            all_chunks.extend(data.get("chunks", []))
        except Exception as exc:
            log.warning("admin.reindex.skip", extra={"file": f.name, "error": str(exc)})

    if not all_chunks:
        return {"message": "Không có chunks để reindex", "reindexed": 0}

    # Re-embed và upsert
    def _do_reindex():
        from .rag.vector_store import VectorStoreService
        vs = VectorStoreService(persist_directory=settings.chroma_persist_dir)
        result = vs.update_records(all_chunks)
        return result.updated_count

    count = await asyncio.to_thread(_do_reindex)
    log.info("admin.reindex.done", extra={"company": body.company, "chunks": count})

    return {
        "message":    f"Reindex hoàn tất: {count} chunks",
        "company":    body.company or "all",
        "files":      len(json_files),
        "reindexed":  count,
    }


@admin_router.delete("/collection")
async def delete_company_documents(
    body: DeleteCollectionRequest,
    _: str = Depends(require_api_key),
) -> dict:
    """
    Xóa toàn bộ documents của một công ty khỏi vector store.
    CẢNH BÁO: không thể hoàn tác. Phải truyền confirm=true.
    """
    if not body.confirm:
        raise HTTPException(
            400,
            f"Để xóa documents của '{body.company}', "
            f"truyền confirm=true trong body. Thao tác không thể hoàn tác."
        )

    def _delete():
        collection = _get_chroma_collection()
        # Lấy IDs của company
        results = collection.get(
            where={"company": body.company},
            include=[],
        )
        ids = results.get("ids", [])
        if ids:
            collection.delete(ids=ids)
        return len(ids)

    deleted = await asyncio.to_thread(_delete)
    log.warning(
        "admin.collection_deleted",
        extra={"company": body.company, "deleted": deleted},
    )
    return {
        "message": f"Đã xóa {deleted} documents của '{body.company}'",
        "company": body.company,
        "deleted": deleted,
    }


@admin_router.get("/documents")
async def list_documents(
    company: Optional[str] = Query(None),
    sector:  Optional[str] = Query(None),
    limit:   int           = Query(20, ge=1, le=100),
    _: str = Depends(require_api_key),
) -> dict:
    """Liệt kê documents trong vector store với filter."""
    def _list():
        collection = _get_chroma_collection()
        where: dict = {}
        if company and sector:
            where = {"$and": [{"company": company}, {"sector": sector}]}
        elif company:
            where = {"company": company}
        elif sector:
            where = {"sector": sector}

        kwargs: dict = {"include": ["metadatas"], "limit": limit}
        if where:
            kwargs["where"] = where

        results = collection.get(**kwargs)
        ids       = results.get("ids", [])
        metadatas = results.get("metadatas", [])
        return [
            {"id": doc_id, **meta}
            for doc_id, meta in zip(ids, metadatas or [])
        ]

    docs = await asyncio.to_thread(_list)
    return {"documents": docs, "count": len(docs)}


@admin_router.post("/metrics/reset")
async def reset_metrics(
    _: str = Depends(require_api_key),
) -> dict:
    """Reset usage metrics về 0."""
    metrics.reset()
    log.info("admin.metrics_reset")
    return {"message": "Metrics đã được reset", "status": "ok"}