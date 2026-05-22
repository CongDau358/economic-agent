"""
backend/models.py  (TẠO MỚI)

Shared Pydantic response models dùng chung cho toàn bộ API.
Import từ đây thay vì định nghĩa inline trong main.py.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Upload / Job ──────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    job_id:  str
    status:  str
    message: str


class JobResponse(BaseModel):
    job_id:      str
    status:      str
    company:     str
    source_type: str
    created_at:  float
    updated_at:  float
    result:      Optional[dict[str, Any]] = None
    error:       Optional[str]            = None


class JobListResponse(BaseModel):
    jobs:  list[JobResponse]
    count: int


# ── Predict ───────────────────────────────────────────────────────────────────

class SignalGroup(BaseModel):
    score:  float
    inputs: list[str]


class TrendResult(BaseModel):
    short_term: str   # bullish | bearish | neutral
    near_term:  str


class ScenarioResult(BaseModel):
    bull: float
    base: float
    bear: float


class PredictResponse(BaseModel):
    company:           str
    status:            str                     # OK | INSUFFICIENT_DATA
    score:             Optional[float]  = None
    trend:             Optional[TrendResult] = None
    confidence:        float
    executive_summary: Optional[str]    = None
    financial_signals: Optional[SignalGroup] = None
    sentiment_signals: Optional[SignalGroup] = None
    macro_signals:     Optional[SignalGroup] = None
    scenarios:         Optional[ScenarioResult] = None
    risks:             list[str]        = Field(default_factory=list)
    opportunities:     list[str]        = Field(default_factory=list)
    assumptions:       list[str]        = Field(default_factory=list)
    warnings:          list[str]        = Field(default_factory=list)
    market_data:       Optional[dict]   = None
    message:           Optional[str]    = None   # khi INSUFFICIENT_DATA
    _cached:           bool             = False


# ── Ask ───────────────────────────────────────────────────────────────────────

class Citation(BaseModel):
    source:  str
    score:   Optional[float] = None
    company: Optional[str]   = None
    snippet: Optional[str]   = None


class AskResponse(BaseModel):
    answer:     str
    citations:  list[Citation] = Field(default_factory=list)
    confidence: Optional[float] = None
    warnings:   list[str]      = Field(default_factory=list)
    status:     str            = "OK"
    _cached:    bool           = False


# ── Health ────────────────────────────────────────────────────────────────────

class JobStats(BaseModel):
    total:   int = 0
    pending: int = 0
    running: int = 0
    done:    int = 0
    failed:  int = 0


class HealthResponse(BaseModel):
    status:        str      = "ok"
    version:       str
    auth_enabled:  bool
    cache:         str
    rate_limiting: bool
    jobs:          JobStats


# ── Metrics ───────────────────────────────────────────────────────────────────

class EndpointMetrics(BaseModel):
    calls:          int
    errors:         int
    error_rate:     float
    avg_latency_ms: float
    cache_hit_rate: float


class MetricsResponse(BaseModel):
    uptime_seconds:    float
    total_calls:       int
    total_errors:      int
    global_error_rate: float
    endpoints:         dict[str, EndpointMetrics]


# ── Error ─────────────────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    field: str
    msg:   str
    type:  str


class ErrorResponse(BaseModel):
    error:   str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)