"""
backend/services/job_store.py  (TẠO MỚI)

Job store cho async ingestion tasks.
Mặc định: in-memory (reset khi restart).
Production: thay bằng Redis hoặc DB.

Thay thế dict _jobs trong main.py bằng:
    from .services.job_store import job_store
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"


@dataclass
class Job:
    job_id:     str
    status:     JobStatus
    company:    str
    source_type: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    result:     dict | None = None
    error:      str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id":      self.job_id,
            "status":      self.status.value,
            "company":     self.company,
            "source_type": self.source_type,
            "created_at":  self.created_at,
            "updated_at":  self.updated_at,
            "result":      self.result,
            "error":       self.error,
        }


class InMemoryJobStore:
    """Thread-safe in-memory job store với TTL tự động xóa job cũ."""

    def __init__(self, ttl_seconds: int = 3600):
        self._store: dict[str, Job] = {}
        self._lock = asyncio.Lock()
        self.ttl = ttl_seconds

    async def create(self, job_id: str, company: str, source_type: str) -> Job:
        job = Job(
            job_id=job_id,
            status=JobStatus.PENDING,
            company=company,
            source_type=source_type,
        )
        async with self._lock:
            self._store[job_id] = job
        return job

    async def update(
        self,
        job_id: str,
        status: JobStatus,
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        async with self._lock:
            job = self._store.get(job_id)
            if job:
                job.status = status
                job.updated_at = time.time()
                if result is not None:
                    job.result = result
                if error is not None:
                    job.error = error

    async def get(self, job_id: str) -> Job | None:
        async with self._lock:
            return self._store.get(job_id)

    async def list_jobs(
        self,
        company: str | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[dict]:
        async with self._lock:
            jobs = list(self._store.values())

        # Filter
        if company:
            jobs = [j for j in jobs if j.company.lower() == company.lower()]
        if status:
            jobs = [j for j in jobs if j.status == status]

        # Sort mới nhất trước
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return [j.to_dict() for j in jobs[:limit]]

    async def cleanup_expired(self) -> int:
        """Xóa các job cũ hơn TTL. Gọi định kỳ."""
        cutoff = time.time() - self.ttl
        async with self._lock:
            expired = [
                k for k, v in self._store.items()
                if v.updated_at < cutoff and v.status in (JobStatus.DONE, JobStatus.FAILED)
            ]
            for k in expired:
                del self._store[k]
        return len(expired)

    @property
    def stats(self) -> dict:
        counts: dict[str, int] = {}
        for job in self._store.values():
            counts[job.status.value] = counts.get(job.status.value, 0) + 1
        return {"total": len(self._store), **counts}


# ── Singleton ────────────────────────────────────────────────────────────────
job_store = InMemoryJobStore(ttl_seconds=3600)