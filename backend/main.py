from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import (
    BackgroundTasks, Depends, FastAPI, File, Form,
    HTTPException, Query, Request, UploadFile,
    WebSocket, WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Internal — giữ nguyên từ bản gốc ─────────────────────────────────────────
from .ingestion.parser import parse_source, save_processed
from .ingestion.excel import process_excel_document
from .ingestion.news import process_news_article
from .ingestion.pdf import process_pdf_document
from .ingestion.validation import ExtractionStats, validate_document_file, validate_ingestion
from .rag.embedding.pipeline import EmbeddingBatchResult
from .rag.vector_store import VectorStoreService
from .retrieval.router import bind_retrieval_api, router as retrieval_router
from .retrieval.service import RetrievalAPI
from .orchestration.pipeline import PromptOrchestrationPipeline
from .trend_engine import TrendEngine

# ── Bổ sung mới ───────────────────────────────────────────────────────────────
from .auth import AccessLogMiddleware, require_api_key
from .config import get_settings
from .exception_handlers import register_exception_handlers
from .services.cache import get_cache, make_cache_key
from .services.job_store import JobStatus as JS, job_store
from .services.logger import get_logger, setup_logging
from .services.metrics import metrics, track
from .services.rate_limiter import (
    ASK_LIMIT, PREDICT_LIMIT, UPLOAD_LIMIT,
    limiter, rate_limit_handler, SLOWAPI_AVAILABLE,
)

# ── Boot ──────────────────────────────────────────────────────────────────────
settings = get_settings()
setup_logging(level=settings.log_level)
log = get_logger("economic_agent.main")

BASE_DIR      = Path(__file__).resolve().parent.parent
DATA_DIR      = BASE_DIR / "data"
RAW_DIR       = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
VECTOR_DIR    = DATA_DIR / "vector"

for _d in (RAW_DIR, PROCESSED_DIR, VECTOR_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Services ──────────────────────────────────────────────────────────────────
vector_store  = VectorStoreService(persist_directory=str(VECTOR_DIR))
retrieval_api = RetrievalAPI(vector_store)
bind_retrieval_api(retrieval_api)
orchestrator  = PromptOrchestrationPipeline(retrieval_api)
trend_engine  = TrendEngine(
    weight_financial=settings.weight_financial,
    weight_sentiment=settings.weight_sentiment,
    weight_macro=settings.weight_macro,
)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("economic_agent.startup", extra={"version": "1.1.0"})

    async def _cleanup_loop():
        while True:
            await asyncio.sleep(3600)
            removed = await job_store.cleanup_expired()
            if removed:
                log.info("job_store.cleanup", extra={"removed": removed})

    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()
    log.info("economic_agent.shutdown")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Economic Agent System",
    version="1.1.0",
    description="Financial intelligence agent — RAG + Trend Scoring + Market Data",
    lifespan=lifespan,
)
app.include_router(retrieval_router)

from .admin import admin_router
app.include_router(admin_router)

app.add_middleware(AccessLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if SLOWAPI_AVAILABLE:
    from slowapi.errors import RateLimitExceeded
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

register_exception_handlers(app)


# ── Request models ────────────────────────────────────────────────────────────
class PredictRequest(BaseModel):
    company:                 str           = Field(..., min_length=1)
    ticker:                  Optional[str] = Field(None)
    financial_signals:       List[str]     = Field(default_factory=list)
    sentiment_signals:       List[str]     = Field(default_factory=list)
    macro_signals:           List[str]     = Field(default_factory=list)
    enrich_with_market_data: bool          = Field(False)


class AskRequest(BaseModel):
    question:       str           = Field(..., min_length=3)
    company:        Optional[str] = None
    sector:         Optional[str] = None
    year:           Optional[str] = None
    source:         Optional[str] = None
    document_type:  Optional[str] = None
    retrieval_mode: Optional[str] = Field(default="hybrid")
    top_k:          int           = Field(default=4, ge=1, le=10)


# ── Sync ingestion ────────────────────────────────────────────────────────────
def _sync_ingest(
    source_type: str, company: str, sector: str,
    text: str | None, url: str | None,
    file_bytes: bytes | None, file_name: str | None,
) -> dict:
    source_type = source_type.strip().lower()
    if source_type not in {"pdf", "excel", "news", "text"}:
        raise HTTPException(400, "source_type must be one of: pdf, excel, news, text")

    extracted_text = ""
    raw_ref = ""
    pdf_r = excel_r = news_r = None
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    if source_type == "pdf":
        if not file_bytes:
            raise HTTPException(400, "file is required for pdf source_type")
        if not (file_name or "").lower().endswith(".pdf"):
            raise HTTPException(400, "uploaded file must be a PDF")
        raw_path = RAW_DIR / f"{timestamp}_{file_name}"
        raw_path.write_bytes(file_bytes)
        raw_ref = str(raw_path)
        if errs := validate_document_file(str(raw_path), "pdf"):
            raise HTTPException(400, "; ".join(errs))
        pname = f"{timestamp}_{company.replace(' ', '_')}.json"
        pdf_r = process_pdf_document(
            path=str(raw_path), company=company, sector=sector,
            raw_ref=raw_ref, processed_file=pname, doc_id=pname,
        )
        if not pdf_r.chunks:
            raise HTTPException(400, "No extractable content found in PDF")

    elif source_type == "excel":
        if not file_bytes:
            raise HTTPException(400, "file is required for excel source_type")
        if not (file_name or "").lower().endswith((".xlsx", ".xlsm", ".csv")):
            raise HTTPException(400, "uploaded file must be .xlsx, .xlsm, or .csv")
        raw_path = RAW_DIR / f"{timestamp}_{file_name}"
        raw_path.write_bytes(file_bytes)
        raw_ref = str(raw_path)
        if errs := validate_document_file(str(raw_path), "excel"):
            raise HTTPException(400, "; ".join(errs))
        pname = f"{timestamp}_{company.replace(' ', '_')}.json"
        excel_r = process_excel_document(
            path=str(raw_path), company=company, sector=sector,
            raw_ref=raw_ref, processed_file=pname, doc_id=pname,
        )
        if not excel_r.chunks:
            raise HTTPException(400, "No extractable content found in Excel")

    elif source_type == "news":
        if not url and not text:
            raise HTTPException(400, "url or text is required for news source_type")
        pname = f"{timestamp}_{company.replace(' ', '_')}.json"
        raw_ref = url or "inline_news"
        news_r = process_news_article(
            company=company, sector=sector, raw_ref=raw_ref,
            processed_file=pname, doc_id=pname,
            url=url or "", text=text or "",
        )
        if not news_r.chunks:
            raise HTTPException(400, "No extractable content found in news")

    else:
        if not text:
            raise HTTPException(400, "text is required for text source_type")
        extracted_text = text
        raw_ref = "inline_text"

    # Build chunks
    if source_type == "pdf":
        chunk_records = pdf_r.chunks
        pname = chunk_records[0].get("processed_file", "") if chunk_records else ""
    elif source_type == "excel":
        chunk_records = excel_r.chunks
        pname = chunk_records[0].get("processed_file", "") if chunk_records else ""
    elif source_type == "news":
        chunk_records = news_r.chunks
        pname = chunk_records[0].get("processed_file", "") if chunk_records else ""
    else:
        chunks = parse_source(source_type=source_type, text=extracted_text)
        if not chunks:
            raise HTTPException(400, "No extractable content found")
        pname = f"{timestamp}_{company.replace(' ', '_')}.json"
        chunk_records = [
            {"text": c, "company": company, "sector": sector,
             "source_type": source_type, "raw_ref": raw_ref, "processed_file": pname}
            for c in chunks
        ]

    # Validate
    stats = ExtractionStats(
        char_count=sum(len(str(c.get("text", ""))) for c in chunk_records),
        page_count=pdf_r.page_count if pdf_r else None,
        table_count=excel_r.table_count if excel_r else None,
        sheet_count=excel_r.sheet_count if excel_r else None,
    )
    sample = str(chunk_records[0].get("text", ""))[:2000] if chunk_records else extracted_text[:2000]
    file_path = raw_ref if source_type in {"pdf", "excel"} else None

    validation = validate_ingestion(
        source_type=source_type, records=chunk_records, doc_id=pname,
        file_path=file_path, extraction_stats=stats, sample_text=sample,
    )
    if not validation.valid:
        raise HTTPException(400, "; ".join(validation.errors))

    from .memory.lifecycle import apply_processing_lifecycle
    chunk_records = [apply_processing_lifecycle(r) for r in validation.records]

    # Persist + embed
    processed = save_processed(
        output_path=str(PROCESSED_DIR / pname),
        company=company, sector=sector, source_type=source_type,
        chunks=chunk_records,
        pipeline=(
            "pdf_processing" if source_type == "pdf"
            else "excel_processing" if source_type == "excel"
            else "news_processing" if source_type == "news"
            else "text_split"
        ),
        document_type=(
            pdf_r.document_type if pdf_r
            else excel_r.data_types[0] if excel_r and excel_r.data_types
            else news_r.content_type if news_r else None
        ),
        page_count=pdf_r.page_count if pdf_r else None,
        section_count=(
            pdf_r.section_count if pdf_r
            else excel_r.table_count if excel_r else None
        ),
        financial_priorities=(
            pdf_r.financial_priorities_found if pdf_r
            else excel_r.financial_priorities_found if excel_r
            else news_r.topics if news_r else None
        ),
    )

    update = vector_store.update_records(chunk_records)
    emb = EmbeddingBatchResult(
        embedded_count=update.updated_count,
        skipped_count=update.skipped_count,
        duplicate_count=update.duplicate_count,
        model=vector_store.embedding_model,
        model_version=update.update_version,
    )

    response: dict = {
        "message": "data ingested",
        "company": company, "sector": sector, "source_type": source_type,
        "raw_ref": raw_ref, "processed_file": pname,
        "chunk_count": len(chunk_records),
        "validation": {
            "valid_chunk_count": validation.valid_chunk_count,
            "duplicate_count": validation.duplicate_count,
            "rejected_chunk_count": validation.rejected_chunk_count,
            "warnings": validation.warnings,
        },
        "embedded_count": emb.embedded_count,
        "indexed_count": update.updated_count,
        "vector_update": {
            "updated_count": update.updated_count,
            "duplicate_count": update.duplicate_count,
            "replaced_count": update.replaced_count,
            "batch_count": update.batch_count,
            "latency_ms": update.latency_ms,
            "update_version": update.update_version,
            "doc_ids": update.doc_ids,
            "skipped_count": update.skipped_count,
        },
        "embedding_model": emb.model,
        "embedding_version": emb.model_version,
        "processed_preview": processed["chunks"][:2],
    }
    if pdf_r:
        response["pdf_pipeline"] = {
            "document_type": pdf_r.document_type,
            "extractor": pdf_r.extractor,
            "page_count": pdf_r.page_count,
            "section_count": pdf_r.section_count,
            "financial_priorities": pdf_r.financial_priorities_found,
            "sections_preview": pdf_r.sections_preview,
        }
    if excel_r:
        response["excel_pipeline"] = {
            "file_format": excel_r.file_format,
            "sheet_count": excel_r.sheet_count,
            "table_count": excel_r.table_count,
            "data_types": excel_r.data_types,
            "financial_priorities": excel_r.financial_priorities_found,
            "sheets_preview": excel_r.sheets_preview,
        }
    if news_r:
        response["news_pipeline"] = {
            "content_type": news_r.content_type,
            "publisher": news_r.publisher,
            "publication_date": news_r.publication_date,
            "topic": news_r.topic,
            "topics": news_r.topics,
            "industry": news_r.industry,
            "sentiment": news_r.sentiment,
            "sentiment_score": news_r.sentiment_score,
        }
    return response


# ── Background task ───────────────────────────────────────────────────────────
async def _run_upload(
    job_id: str, source_type: str, company: str, sector: str,
    text: str | None, url: str | None,
    file_bytes: bytes | None, file_name: str | None,
):
    await job_store.update(job_id, JS.RUNNING)
    try:
        result = await asyncio.to_thread(
            _sync_ingest, source_type, company, sector,
            text, url, file_bytes, file_name,
        )
        await job_store.update(job_id, JS.DONE, result=result)
        metrics.record_call("upload", latency_ms=0, is_error=False)
        log.info("upload.done", extra={"job_id": job_id, "chunks": result.get("chunk_count")})
    except HTTPException as exc:
        await job_store.update(job_id, JS.FAILED, error=exc.detail)
        metrics.record_call("upload", latency_ms=0, is_error=True)
        try:
            from .services.notify import notify_job_failed
            await notify_job_failed(job_id=job_id, company=company,
                                    source_type=source_type, error=exc.detail)
        except Exception:
            pass
    except Exception as exc:
        await job_store.update(job_id, JS.FAILED, error=str(exc))
        metrics.record_call("upload", latency_ms=0, is_error=True)
        log.error("upload.error", extra={"job_id": job_id, "error": str(exc)})
        try:
            from .services.notify import notify_job_failed
            await notify_job_failed(job_id=job_id, company=company,
                                    source_type=source_type, error=str(exc))
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health(deep: bool = Query(False)) -> dict:
    """
    Health check cơ bản (mặc định) hoặc deep check với ?deep=true.
    Deep check kiểm tra ChromaDB, Redis, disk — không cần auth.
    """
    base = {
        "status":        "ok",
        "version":       "1.1.0",
        "auth_enabled":  settings.auth_enabled,
        "cache":         "redis" if settings.redis_url else "memory",
        "rate_limiting": SLOWAPI_AVAILABLE,
        "jobs":          job_store.stats,
    }
    if deep:
        from .services.health import run_health_check
        deep_result = await run_health_check(include_openai=False)
        base.update({
            "status": deep_result["status"],
            "checks": deep_result["checks"],
        })
    return base


@app.get("/metrics")
def get_metrics(_: str = Depends(require_api_key)) -> dict:
    """Usage metrics: calls, latency, error rate, cache hit rate."""
    return metrics.summary()


# ── Upload ────────────────────────────────────────────────────────────────────
@app.post("/upload")
@limiter.limit(UPLOAD_LIMIT)
async def upload_data(
    request:      Request,
    background_tasks: BackgroundTasks,
    source_type:  str           = Form(...),
    company:      str           = Form(...),
    sector:       str           = Form(...),
    text:         Optional[str] = Form(default=None),
    url:          Optional[str] = Form(default=None),
    file:         Optional[UploadFile] = File(default=None),
    _: str = Depends(require_api_key),
) -> dict:
    job_id = str(uuid.uuid4())
    await job_store.create(job_id, company=company, source_type=source_type)

    file_bytes: bytes | None = None
    file_name:  str | None   = None
    if file:
        file_bytes = await file.read()
        file_name  = file.filename

    background_tasks.add_task(
        _run_upload, job_id, source_type, company, sector,
        text, url, file_bytes, file_name,
    )
    log.info("upload.queued", extra={"job_id": job_id, "company": company})
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Ingestion queued — poll /jobs/{job_id} để theo dõi",
    }


# ── Jobs ──────────────────────────────────────────────────────────────────────
@app.get("/jobs")
async def list_jobs(
    company: Optional[str] = Query(None),
    status:  Optional[str] = Query(None),
    limit:   int           = Query(50, ge=1, le=200),
    _: str = Depends(require_api_key),
) -> dict:
    js = JS(status) if status else None
    jobs = await job_store.list_jobs(company=company, status=js, limit=limit)
    return {"jobs": jobs, "count": len(jobs)}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str, _: str = Depends(require_api_key)) -> dict:
    job = await job_store.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job.to_dict()


# ── Predict ───────────────────────────────────────────────────────────────────
@app.post("/predict")
@limiter.limit(PREDICT_LIMIT)
async def predict(
    request: Request,
    payload: PredictRequest,
    _: str = Depends(require_api_key),
) -> dict:
    async with track("predict") as t:
        cache = get_cache()
        cache_key = make_cache_key(
            "predict",
            company=payload.company,
            ticker=payload.ticker,
            fin=sorted(payload.financial_signals),
            sent=sorted(payload.sentiment_signals),
            macro=sorted(payload.macro_signals),
            enrich=payload.enrich_with_market_data,
        )

        cached = await cache.get(cache_key)
        if cached:
            t.cache_hit = True
            return {**cached, "_cached": True}

        t.cache_hit = False

        # Market data enrichment
        market_context: dict = {}
        extra_macro: list[str] = []
        if payload.enrich_with_market_data and payload.ticker:
            try:
                from .services.market_data import build_market_context
                market_context = await asyncio.to_thread(
                    build_market_context, payload.ticker, include_macro=True
                )
                extra_macro = market_context.pop("derived_macro_signals", [])
            except Exception as exc:
                log.warning("market_data.failed", extra={"ticker": payload.ticker, "error": str(exc)})

        result = trend_engine.analyze(
            company=payload.company,
            financial_signals=payload.financial_signals,
            sentiment_signals=payload.sentiment_signals,
            macro_signals=payload.macro_signals + extra_macro,
        )

        if market_context:
            result["market_data"] = market_context

        await cache.set(cache_key, result)
        log.info("predict.done", extra={"company": payload.company, "score": result.get("score")})
        return result


# ── Ask ───────────────────────────────────────────────────────────────────────
@app.post("/ask")
@limiter.limit(ASK_LIMIT)
async def ask(
    request: Request,
    payload: AskRequest,
    _: str = Depends(require_api_key),
) -> dict:
    async with track("ask") as t:
        cache = get_cache()
        cache_key = make_cache_key(
            "ask",
            q=payload.question,
            company=payload.company,
            sector=payload.sector,
            year=payload.year,
            mode=payload.retrieval_mode,
            top_k=payload.top_k,
        )

        cached = await cache.get(cache_key)
        if cached:
            t.cache_hit = True
            return {**cached, "_cached": True}

        t.cache_hit = False
        result = await asyncio.to_thread(
            orchestrator.run,
            payload.question,
            company=payload.company,
            sector=payload.sector,
            year=payload.year,
            source=payload.source,
            document_type=payload.document_type,
            top_k=payload.top_k,
            retrieval_mode=payload.retrieval_mode or "hybrid",
        )
        response = orchestrator.to_response_dict(result)
        await cache.set(cache_key, response, ttl=1800)
        return response




# ── Search ────────────────────────────────────────────────────────────────────
@app.get("/search")
async def search_documents(
    q:            str           = Query(..., min_length=2, description="Search query"),
    company:      Optional[str] = Query(None),
    sector:       Optional[str] = Query(None),
    source_type:  Optional[str] = Query(None),
    year:         Optional[str] = Query(None),
    top_k:        int           = Query(10, ge=1, le=50),
    hybrid:       bool          = Query(True),
    _: str = Depends(require_api_key),
) -> dict:
    """
    Semantic + keyword search trên toàn bộ knowledge base.
    Hỗ trợ filter theo company, sector, source_type, year.
    Hybrid mode: kết hợp vector similarity + BM25 keyword score.
    """
    from .services.search import search, SearchQuery
    async with track("search") as t:
        t.cache_hit = False
        sq = SearchQuery(
            query=q, company=company, sector=sector,
            source_type=source_type, year=year,
            top_k=top_k, hybrid=hybrid,
        )
        results = await asyncio.to_thread(search, sq)
        return {"query": q, "results": results, "count": len(results)}

# ── WebSocket streaming ───────────────────────────────────────────────────────
@app.websocket("/ws/analyze")
async def ws_analyze(websocket: WebSocket):
    """
    Real-time analysis stream.
    Client gửi: {"company": "...", "ticker": "...", "question": "..."}
    """
    await websocket.accept()
    payload: dict = {}
    try:
        payload  = await websocket.receive_json()
        company  = payload.get("company", "")
        ticker   = payload.get("ticker")
        question = payload.get("question") or f"Phân tích tổng thể {company}"

        async def emit(type_: str, **kwargs):
            await websocket.send_json({"type": type_, **kwargs})

        await emit("status", msg="Đang truy xuất evidence từ knowledge base...")
        rag_result = await asyncio.to_thread(
            orchestrator.run, question,
            company=company, retrieval_mode="hybrid", top_k=5,
        )
        rag_dict = orchestrator.to_response_dict(rag_result)
        n_src = len(rag_dict.get("citations", []) or rag_dict.get("sources", []))
        await emit("status", msg=f"Tìm thấy {n_src} evidence chunks")

        market_ctx: dict = {}
        extra_macro: list[str] = []
        if ticker:
            await emit("status", msg=f"Đang lấy dữ liệu thị trường cho {ticker}...")
            try:
                from .services.market_data import build_market_context
                market_ctx  = await asyncio.to_thread(build_market_context, ticker)
                extra_macro = market_ctx.pop("derived_macro_signals", [])
            except Exception as exc:
                await emit("status", msg=f"⚠ Không lấy được market data: {exc}")

        await emit("status", msg="Đang chạy trend & risk scoring...")
        trend = trend_engine.analyze(
            company=company,
            financial_signals=[],
            sentiment_signals=[],
            macro_signals=extra_macro,
        )

        metrics.record_call("ws_analyze", latency_ms=0)
        await emit("result", data={
            "company": company,
            "rag":     rag_dict,
            "trend":   trend,
            "market":  market_ctx,
        })
        await emit("done")

    except WebSocketDisconnect:
        log.info("ws.disconnect", extra={"company": payload.get("company", "?")})
    except Exception as exc:
        log.error("ws.error", extra={"error": str(exc)})
        metrics.record_call("ws_analyze", latency_ms=0, is_error=True)
        try:
            await websocket.send_json({"type": "error", "msg": str(exc)})
        except Exception:
            pass