from __future__ import annotations

import asyncio
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Internal imports (giữ nguyên từ bản gốc) ─────────────────────────────────
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
from .services.cache import get_cache, make_cache_key
from .services.logger import get_logger, setup_logging

# ── Boot ──────────────────────────────────────────────────────────────────────
settings = get_settings()
setup_logging(level=settings.log_level)
log = get_logger("economic_agent.main")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
VECTOR_DIR = DATA_DIR / "vector"

for _d in (RAW_DIR, PROCESSED_DIR, VECTOR_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Services (giữ nguyên) ─────────────────────────────────────────────────────
vector_store = VectorStoreService(persist_directory=str(VECTOR_DIR))
retrieval_api = RetrievalAPI(vector_store)
bind_retrieval_api(retrieval_api)
orchestrator = PromptOrchestrationPipeline(retrieval_api)
trend_engine = TrendEngine(
    weight_financial=settings.weight_financial,
    weight_sentiment=settings.weight_sentiment,
    weight_macro=settings.weight_macro,
)

# ── Job store (in-memory — thay bằng DB khi scale) ───────────────────────────
_jobs: dict[str, dict] = {}


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("economic_agent.startup", extra={"version": "1.1.0"})
    yield
    log.info("economic_agent.shutdown")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Economic Agent System",
    version="1.1.0",
    lifespan=lifespan,
)
app.include_router(retrieval_router)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(AccessLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request models ────────────────────────────────────────────────────────────
class PredictRequest(BaseModel):
    company: str = Field(..., min_length=1)
    ticker: Optional[str] = Field(None, description="Stock ticker, VD: VNM.HM")
    financial_signals: List[str] = Field(default_factory=list)
    sentiment_signals: List[str] = Field(default_factory=list)
    macro_signals: List[str] = Field(default_factory=list)
    enrich_with_market_data: bool = Field(False, description="Gọi yfinance + FRED")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3)
    company: Optional[str] = None
    sector: Optional[str] = None
    year: Optional[str] = None
    source: Optional[str] = None
    document_type: Optional[str] = None
    retrieval_mode: Optional[str] = Field(default="hybrid")
    top_k: int = Field(default=4, ge=1, le=10)


class JobStatus(BaseModel):
    job_id: str
    status: str          # pending | running | done | failed
    result: dict | None = None
    error: str | None = None


# ── Background upload task ────────────────────────────────────────────────────
async def _run_upload(
    job_id: str,
    source_type: str,
    company: str,
    sector: str,
    text: str | None,
    url: str | None,
    file_bytes: bytes | None,
    file_name: str | None,
):
    """Chạy toàn bộ ingestion pipeline trong background."""
    _jobs[job_id] = {"status": "running"}
    try:
        result = await asyncio.to_thread(
            _sync_ingest,
            source_type, company, sector, text, url, file_bytes, file_name,
        )
        _jobs[job_id] = {"status": "done", "result": result}
        log.info("upload.done", extra={"job_id": job_id, "chunks": result.get("chunk_count")})
    except HTTPException as exc:
        _jobs[job_id] = {"status": "failed", "error": exc.detail}
        log.warning("upload.failed", extra={"job_id": job_id, "error": exc.detail})
    except Exception as exc:
        _jobs[job_id] = {"status": "failed", "error": str(exc)}
        log.error("upload.error", extra={"job_id": job_id, "error": str(exc)})


def _sync_ingest(
    source_type: str,
    company: str,
    sector: str,
    text: str | None,
    url: str | None,
    file_bytes: bytes | None,
    file_name: str | None,
) -> dict:
    """
    Đây là toàn bộ logic ingestion từ /upload gốc — tách ra để chạy trong thread.
    Trả về response dict để lưu vào job store.
    """
    source_type = source_type.strip().lower()
    if source_type not in {"pdf", "excel", "news", "text"}:
        raise HTTPException(
            status_code=400,
            detail="source_type must be one of: pdf, excel, news, text",
        )

    extracted_text = ""
    raw_ref = ""
    pdf_pipeline_result = None
    excel_pipeline_result = None
    news_pipeline_result = None
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    if source_type == "pdf":
        if not file_bytes:
            raise HTTPException(status_code=400, detail="file is required for pdf source_type")
        if not (file_name or "").lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="uploaded file must be a PDF")
        raw_path = RAW_DIR / f"{timestamp}_{file_name}"
        raw_path.write_bytes(file_bytes)
        raw_ref = str(raw_path)
        file_errors = validate_document_file(str(raw_path), "pdf")
        if file_errors:
            raise HTTPException(status_code=400, detail="; ".join(file_errors))
        processed_name = f"{timestamp}_{company.replace(' ', '_')}.json"
        pdf_pipeline_result = process_pdf_document(
            path=str(raw_path), company=company, sector=sector,
            raw_ref=raw_ref, processed_file=processed_name, doc_id=processed_name,
        )
        if not pdf_pipeline_result.chunks:
            raise HTTPException(status_code=400, detail="No extractable content found in PDF")

    elif source_type == "excel":
        if not file_bytes:
            raise HTTPException(status_code=400, detail="file is required for excel source_type")
        suffix = (file_name or "").lower()
        if not suffix.endswith((".xlsx", ".xlsm", ".csv")):
            raise HTTPException(status_code=400, detail="uploaded file must be .xlsx, .xlsm, or .csv")
        raw_path = RAW_DIR / f"{timestamp}_{file_name}"
        raw_path.write_bytes(file_bytes)
        raw_ref = str(raw_path)
        file_errors = validate_document_file(str(raw_path), "excel")
        if file_errors:
            raise HTTPException(status_code=400, detail="; ".join(file_errors))
        processed_name = f"{timestamp}_{company.replace(' ', '_')}.json"
        excel_pipeline_result = process_excel_document(
            path=str(raw_path), company=company, sector=sector,
            raw_ref=raw_ref, processed_file=processed_name, doc_id=processed_name,
        )
        if not excel_pipeline_result.chunks:
            raise HTTPException(status_code=400, detail="No extractable content found in Excel")

    elif source_type == "news":
        if not url and not text:
            raise HTTPException(status_code=400, detail="url or text is required for news source_type")
        processed_name = f"{timestamp}_{company.replace(' ', '_')}.json"
        raw_ref = url or "inline_news"
        news_pipeline_result = process_news_article(
            company=company, sector=sector, raw_ref=raw_ref,
            processed_file=processed_name, doc_id=processed_name,
            url=url or "", text=text or "",
        )
        if not news_pipeline_result.chunks:
            raise HTTPException(status_code=400, detail="No extractable content found in news")

    else:  # text
        if not text:
            raise HTTPException(status_code=400, detail="text is required for text source_type")
        extracted_text = text
        raw_ref = "inline_text"

    # ── Build chunk_records ───────────────────────────────────────────────────
    if source_type == "pdf":
        chunk_records = pdf_pipeline_result.chunks
        processed_name = chunk_records[0].get("processed_file", "") if chunk_records else ""
    elif source_type == "excel":
        chunk_records = excel_pipeline_result.chunks
        processed_name = chunk_records[0].get("processed_file", "") if chunk_records else ""
    elif source_type == "news":
        chunk_records = news_pipeline_result.chunks
        processed_name = chunk_records[0].get("processed_file", "") if chunk_records else ""
    else:
        chunks = parse_source(source_type=source_type, text=extracted_text)
        if not chunks:
            raise HTTPException(status_code=400, detail="No extractable content found")
        processed_name = f"{timestamp}_{company.replace(' ', '_')}.json"
        chunk_records = [
            {
                "text": chunk, "company": company, "sector": sector,
                "source_type": source_type, "raw_ref": raw_ref, "processed_file": processed_name,
            }
            for chunk in chunks
        ]

    # ── Validation ────────────────────────────────────────────────────────────
    file_path = raw_ref if source_type in {"pdf", "excel"} else None
    extraction_stats = ExtractionStats(
        char_count=sum(len(str(c.get("text", ""))) for c in chunk_records),
        page_count=pdf_pipeline_result.page_count if pdf_pipeline_result else None,
        table_count=excel_pipeline_result.table_count if excel_pipeline_result else None,
        sheet_count=excel_pipeline_result.sheet_count if excel_pipeline_result else None,
    )
    sample_text = str(chunk_records[0].get("text", ""))[:2000] if chunk_records else extracted_text[:2000]

    validation = validate_ingestion(
        source_type=source_type, records=chunk_records, doc_id=processed_name,
        file_path=file_path, extraction_stats=extraction_stats, sample_text=sample_text,
    )
    if not validation.valid:
        raise HTTPException(status_code=400, detail="; ".join(validation.errors))

    from .memory.lifecycle import apply_processing_lifecycle
    chunk_records = [apply_processing_lifecycle(r) for r in validation.records]

    # ── Save processed + embed ────────────────────────────────────────────────
    processed_path = PROCESSED_DIR / processed_name
    processed = save_processed(
        output_path=str(processed_path),
        company=company, sector=sector, source_type=source_type,
        chunks=chunk_records,
        pipeline=(
            "pdf_processing" if source_type == "pdf"
            else "excel_processing" if source_type == "excel"
            else "news_processing" if source_type == "news"
            else "text_split"
        ),
        document_type=(
            pdf_pipeline_result.document_type if pdf_pipeline_result
            else excel_pipeline_result.data_types[0] if excel_pipeline_result and excel_pipeline_result.data_types
            else news_pipeline_result.content_type if news_pipeline_result
            else None
        ),
        page_count=pdf_pipeline_result.page_count if pdf_pipeline_result else None,
        section_count=(
            pdf_pipeline_result.section_count if pdf_pipeline_result
            else excel_pipeline_result.table_count if excel_pipeline_result
            else None
        ),
        financial_priorities=(
            pdf_pipeline_result.financial_priorities_found if pdf_pipeline_result
            else excel_pipeline_result.financial_priorities_found if excel_pipeline_result
            else news_pipeline_result.topics if news_pipeline_result
            else None
        ),
    )

    update_result = vector_store.update_records(chunk_records)
    embed_result = EmbeddingBatchResult(
        embedded_count=update_result.updated_count,
        skipped_count=update_result.skipped_count,
        duplicate_count=update_result.duplicate_count,
        model=vector_store.embedding_model,
        model_version=update_result.update_version,
    )

    # ── Build response ────────────────────────────────────────────────────────
    response: dict = {
        "message": "data ingested",
        "company": company, "sector": sector, "source_type": source_type,
        "raw_ref": raw_ref, "processed_file": processed_name,
        "chunk_count": len(chunk_records),
        "validation": {
            "valid_chunk_count": validation.valid_chunk_count,
            "duplicate_count": validation.duplicate_count,
            "rejected_chunk_count": validation.rejected_chunk_count,
            "warnings": validation.warnings,
        },
        "embedded_count": embed_result.embedded_count,
        "indexed_count": update_result.updated_count,
        "vector_update": {
            "updated_count": update_result.updated_count,
            "duplicate_count": update_result.duplicate_count,
            "replaced_count": update_result.replaced_count,
            "batch_count": update_result.batch_count,
            "latency_ms": update_result.latency_ms,
            "update_version": update_result.update_version,
            "doc_ids": update_result.doc_ids,
            "skipped_count": update_result.skipped_count,
        },
        "embedding_model": embed_result.model,
        "embedding_version": embed_result.model_version,
        "processed_preview": processed["chunks"][:2],
    }

    if pdf_pipeline_result:
        response["pdf_pipeline"] = {
            "document_type": pdf_pipeline_result.document_type,
            "extractor": pdf_pipeline_result.extractor,
            "page_count": pdf_pipeline_result.page_count,
            "section_count": pdf_pipeline_result.section_count,
            "financial_priorities": pdf_pipeline_result.financial_priorities_found,
            "sections_preview": pdf_pipeline_result.sections_preview,
        }
    if excel_pipeline_result:
        response["excel_pipeline"] = {
            "file_format": excel_pipeline_result.file_format,
            "sheet_count": excel_pipeline_result.sheet_count,
            "table_count": excel_pipeline_result.table_count,
            "data_types": excel_pipeline_result.data_types,
            "financial_priorities": excel_pipeline_result.financial_priorities_found,
            "sheets_preview": excel_pipeline_result.sheets_preview,
        }
    if news_pipeline_result:
        response["news_pipeline"] = {
            "content_type": news_pipeline_result.content_type,
            "publisher": news_pipeline_result.publisher,
            "publication_date": news_pipeline_result.publication_date,
            "topic": news_pipeline_result.topic,
            "topics": news_pipeline_result.topics,
            "industry": news_pipeline_result.industry,
            "sentiment": news_pipeline_result.sentiment,
            "sentiment_score": news_pipeline_result.sentiment_score,
        }
    return response


# ════════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": "1.1.0",
        "auth_enabled": settings.auth_enabled,
        "cache": "redis" if settings.redis_url else "memory",
    }


# ── Upload (async — không block) ──────────────────────────────────────────────
@app.post("/upload")
async def upload_data(
    background_tasks: BackgroundTasks,
    source_type: str = Form(...),
    company: str = Form(...),
    sector: str = Form(...),
    text: Optional[str] = Form(default=None),
    url: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
    _: str = Depends(require_api_key),
) -> dict:
    """
    Nhận request và trả về job_id ngay lập tức.
    Ingestion chạy trong background — poll GET /jobs/{job_id} để theo dõi.
    """
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "pending"}

    file_bytes: bytes | None = None
    file_name: str | None = None
    if file:
        file_bytes = await file.read()
        file_name = file.filename

    background_tasks.add_task(
        _run_upload,
        job_id, source_type, company, sector,
        text, url, file_bytes, file_name,
    )

    log.info("upload.queued", extra={"job_id": job_id, "company": company, "source_type": source_type})
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Ingestion queued — poll /jobs/{job_id} để theo dõi tiến trình",
    }


# ── Job tracking ──────────────────────────────────────────────────────────────
@app.get("/jobs/{job_id}", response_model=JobStatus)
def get_job(
    job_id: str,
    _: str = Depends(require_api_key),
) -> JobStatus:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(job_id=job_id, **job)


# ── Predict ───────────────────────────────────────────────────────────────────
@app.post("/predict")
async def predict(
    payload: PredictRequest,
    _: str = Depends(require_api_key),
) -> dict:
    """
    Chạy trend scoring. Kết quả được cache theo TTL.
    Nếu enrich_with_market_data=true và ticker được cung cấp,
    tự động lấy dữ liệu thị trường thực từ yfinance + FRED.
    """
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
        return {**cached, "_cached": True}

    # ── Market data enrichment ────────────────────────────────────────────────
    market_context: dict = {}
    extra_macro: list[str] = []
    if payload.enrich_with_market_data and payload.ticker:
        try:
            from .services.market_data import build_market_context
            market_context = await asyncio.to_thread(
                build_market_context, payload.ticker, include_macro=True
            )
            extra_macro = market_context.pop("derived_macro_signals", [])
            log.info("market_data.fetched", extra={"ticker": payload.ticker})
        except Exception as exc:
            log.warning("market_data.failed", extra={"ticker": payload.ticker, "error": str(exc)})

    # ── Trend engine ──────────────────────────────────────────────────────────
    result = trend_engine.analyze(
        company=payload.company,
        financial_signals=payload.financial_signals,
        sentiment_signals=payload.sentiment_signals,
        macro_signals=payload.macro_signals + extra_macro,
    )

    if market_context:
        result["market_data"] = market_context

    await cache.set(cache_key, result)
    log.info(
        "predict.done",
        extra={"company": payload.company, "score": result.get("score"), "trend": result.get("trend")},
    )
    return result


# ── Ask ───────────────────────────────────────────────────────────────────────
@app.post("/ask")
async def ask(
    payload: AskRequest,
    _: str = Depends(require_api_key),
) -> dict:
    """RAG Q&A với cache 30 phút."""
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
        return {**cached, "_cached": True}

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


# ── WebSocket: streaming analysis ────────────────────────────────────────────
@app.websocket("/ws/analyze")
async def ws_analyze(websocket: WebSocket):
    """
    Real-time analysis stream.

    Client gửi:
        {"company": "Vinamilk", "ticker": "VNM.HM", "question": "Rủi ro chính?"}

    Server stream:
        {"type": "status", "msg": "..."}
        {"type": "result", "data": {...}}
        {"type": "done"}
    """
    await websocket.accept()
    payload: dict = {}
    try:
        payload = await websocket.receive_json()
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
        n_chunks = len(rag_dict.get("citations", []) or rag_dict.get("sources", []))
        await emit("status", msg=f"Tìm thấy {n_chunks} evidence chunks")

        # Market data
        market_ctx: dict = {}
        extra_macro: list[str] = []
        if ticker:
            await emit("status", msg=f"Đang lấy dữ liệu thị trường cho {ticker}...")
            try:
                from .services.market_data import build_market_context
                market_ctx = await asyncio.to_thread(build_market_context, ticker)
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

        await emit("result", data={
            "company": company,
            "rag": rag_dict,
            "trend": trend,
            "market": market_ctx,
        })
        await emit("done")

    except WebSocketDisconnect:
        log.info("ws.disconnect", extra={"company": payload.get("company", "?")})
    except Exception as exc:
        log.error("ws.error", extra={"error": str(exc)})
        try:
            await websocket.send_json({"type": "error", "msg": str(exc)})
        except Exception:
            pass