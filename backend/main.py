from __future__ import annotations
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .ingestion.parser import parse_source, save_processed
from .ingestion.excel import process_excel_document
from .ingestion.news import process_news_article
from .ingestion.pdf import process_pdf_document
from .ingestion.validation import ExtractionStats, validate_document_file, validate_ingestion
from .rag.vector_store import VectorStoreService
from .services.agent_service import build_rag_answer
from .services.retrieval_governance import apply_retrieval_governance
from .trend_engine import predict_trend


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
VECTOR_DIR = DATA_DIR / "vector"

for directory in (RAW_DIR, PROCESSED_DIR, VECTOR_DIR):
    directory.mkdir(parents=True, exist_ok=True)

vector_store = VectorStoreService(persist_directory=str(VECTOR_DIR))
app = FastAPI(title="Economic Agent System", version="1.0.0")


class PredictRequest(BaseModel):
    company: str = Field(..., min_length=1)
    financial_signals: List[str] = Field(default_factory=list)
    sentiment_signals: List[str] = Field(default_factory=list)
    macro_signals: List[str] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3)
    company: Optional[str] = None
    sector: Optional[str] = None
    year: Optional[str] = None
    source: Optional[str] = None
    document_type: Optional[str] = None
    top_k: int = Field(default=4, ge=1, le=10)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/upload")
async def upload_data(
    source_type: str = Form(...),
    company: str = Form(...),
    sector: str = Form(...),
    text: Optional[str] = Form(default=None),
    url: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
) -> dict:
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

    if source_type == "pdf":
        if file is None:
            raise HTTPException(status_code=400, detail="file is required for pdf source_type")
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="uploaded file must be a PDF")
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        raw_path = RAW_DIR / f"{timestamp}_{file.filename}"
        with raw_path.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)
        raw_ref = str(raw_path)
        file_errors = validate_document_file(str(raw_path), "pdf")
        if file_errors:
            raise HTTPException(status_code=400, detail="; ".join(file_errors))
        processed_name = f"{timestamp}_{company.replace(' ', '_')}.json"
        pdf_pipeline_result = process_pdf_document(
            path=str(raw_path),
            company=company,
            sector=sector,
            raw_ref=raw_ref,
            processed_file=processed_name,
            doc_id=processed_name,
        )
        if not pdf_pipeline_result.chunks:
            raise HTTPException(status_code=400, detail="No extractable content found in PDF")
    elif source_type == "excel":
        if file is None:
            raise HTTPException(status_code=400, detail="file is required for excel source_type")
        suffix = (file.filename or "").lower()
        if not suffix.endswith((".xlsx", ".xlsm", ".csv")):
            raise HTTPException(
                status_code=400,
                detail="uploaded file must be .xlsx, .xlsm, or .csv",
            )
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        raw_path = RAW_DIR / f"{timestamp}_{file.filename}"
        with raw_path.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)
        raw_ref = str(raw_path)
        file_errors = validate_document_file(str(raw_path), "excel")
        if file_errors:
            raise HTTPException(status_code=400, detail="; ".join(file_errors))
        processed_name = f"{timestamp}_{company.replace(' ', '_')}.json"
        excel_pipeline_result = process_excel_document(
            path=str(raw_path),
            company=company,
            sector=sector,
            raw_ref=raw_ref,
            processed_file=processed_name,
            doc_id=processed_name,
        )
        if not excel_pipeline_result.chunks:
            raise HTTPException(status_code=400, detail="No extractable content found in Excel")
    elif source_type == "news":
        if not url and not text:
            raise HTTPException(
                status_code=400,
                detail="url or text is required for news source_type",
            )
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        processed_name = f"{timestamp}_{company.replace(' ', '_')}.json"
        raw_ref = url or "inline_news"
        news_pipeline_result = process_news_article(
            company=company,
            sector=sector,
            raw_ref=raw_ref,
            processed_file=processed_name,
            doc_id=processed_name,
            url=url or "",
            text=text or "",
        )
        if not news_pipeline_result.chunks:
            raise HTTPException(status_code=400, detail="No extractable content found in news")
    else:
        if not text:
            raise HTTPException(status_code=400, detail="text is required for text source_type")
        extracted_text = text
        raw_ref = "inline_text"

    if source_type == "pdf":
        assert pdf_pipeline_result is not None
        chunk_records = pdf_pipeline_result.chunks
        processed_name = chunk_records[0].get("processed_file", "") if chunk_records else ""
    elif source_type == "excel":
        assert excel_pipeline_result is not None
        chunk_records = excel_pipeline_result.chunks
        processed_name = chunk_records[0].get("processed_file", "") if chunk_records else ""
    elif source_type == "news":
        assert news_pipeline_result is not None
        chunk_records = news_pipeline_result.chunks
        processed_name = chunk_records[0].get("processed_file", "") if chunk_records else ""
    else:
        chunks = parse_source(source_type=source_type, text=extracted_text)
        if not chunks:
            raise HTTPException(status_code=400, detail="No extractable content found")
        processed_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{company.replace(' ', '_')}.json"
        chunk_records = [
            {
                "text": chunk,
                "company": company,
                "sector": sector,
                "source_type": source_type,
                "raw_ref": raw_ref,
                "processed_file": processed_name,
            }
            for chunk in chunks
        ]

    file_path: str | None = None
    extraction_stats = ExtractionStats()
    sample_text = ""

    if source_type == "pdf" and pdf_pipeline_result:
        file_path = raw_ref
        extraction_stats = ExtractionStats(
            char_count=sum(len(str(c.get("text", ""))) for c in chunk_records),
            page_count=pdf_pipeline_result.page_count,
        )
        sample_text = str(chunk_records[0].get("text", "")) if chunk_records else ""
    elif source_type == "excel" and excel_pipeline_result:
        file_path = raw_ref
        extraction_stats = ExtractionStats(
            char_count=sum(len(str(c.get("text", ""))) for c in chunk_records),
            table_count=excel_pipeline_result.table_count,
            sheet_count=excel_pipeline_result.sheet_count,
        )
        sample_text = str(chunk_records[0].get("text", "")) if chunk_records else ""
    elif source_type == "news" and news_pipeline_result:
        extraction_stats = ExtractionStats(
            char_count=sum(len(str(c.get("text", ""))) for c in chunk_records),
        )
        sample_text = str(chunk_records[0].get("text", "")) if chunk_records else ""
    else:
        extraction_stats = ExtractionStats(char_count=len(extracted_text))
        sample_text = extracted_text[:2000]

    validation = validate_ingestion(
        source_type=source_type,
        records=chunk_records,
        doc_id=processed_name,
        file_path=file_path,
        extraction_stats=extraction_stats,
        sample_text=sample_text,
    )
    if not validation.valid:
        raise HTTPException(status_code=400, detail="; ".join(validation.errors))
    from .memory.lifecycle import apply_processing_lifecycle

    chunk_records = [apply_processing_lifecycle(record) for record in validation.records]

    processed_path = PROCESSED_DIR / processed_name
    processed = save_processed(
        output_path=str(processed_path),
        company=company,
        sector=sector,
        source_type=source_type,
        chunks=chunk_records,
        pipeline=(
            "pdf_processing"
            if source_type == "pdf"
            else "excel_processing"
            if source_type == "excel"
            else "news_processing"
            if source_type == "news"
            else "text_split"
        ),
        document_type=(
            pdf_pipeline_result.document_type
            if pdf_pipeline_result
            else excel_pipeline_result.data_types[0]
            if excel_pipeline_result and excel_pipeline_result.data_types
            else news_pipeline_result.content_type
            if news_pipeline_result
            else None
        ),
        page_count=pdf_pipeline_result.page_count if pdf_pipeline_result else None,
        section_count=(
            pdf_pipeline_result.section_count
            if pdf_pipeline_result
            else excel_pipeline_result.table_count
            if excel_pipeline_result
            else None
        ),
        financial_priorities=(
            pdf_pipeline_result.financial_priorities_found
            if pdf_pipeline_result
            else excel_pipeline_result.financial_priorities_found
            if excel_pipeline_result
            else news_pipeline_result.topics
            if news_pipeline_result
            else None
        ),
    )

    embed_result = vector_store.add_documents(chunk_records)

    response = {
        "message": "data ingested",
        "company": company,
        "sector": sector,
        "source_type": source_type,
        "raw_ref": raw_ref,
        "processed_file": processed_name,
        "chunk_count": len(chunk_records),
        "validation": {
            "valid_chunk_count": validation.valid_chunk_count,
            "duplicate_count": validation.duplicate_count,
            "rejected_chunk_count": validation.rejected_chunk_count,
            "warnings": validation.warnings,
        },
        "embedded_count": embed_result.embedded_count,
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


@app.post("/predict")
def predict(payload: PredictRequest) -> dict:
    result = predict_trend(
        financial_signals=payload.financial_signals,
        sentiment_signals=payload.sentiment_signals,
        macro_signals=payload.macro_signals,
    )
    return {
        "summary": result.summary,
        "signals": result.signals,
        "score": result.score,
        "trend": result.trend,
        "risks": result.risks,
        "opportunities": result.opportunities,
        "confidence": result.confidence,
    }


@app.post("/ask")
def ask(payload: AskRequest) -> dict:
    retrieved = vector_store.query(
        payload.question,
        top_k=payload.top_k,
        company=payload.company,
        industry=payload.sector,
        year=payload.year,
        source=payload.source,
        document_type=payload.document_type,
    )
    filtered: list[dict] = []
    distances: list[float] = []
    for item in retrieved:
        metadata = item.metadata
        filtered.append({"text": item.text, **metadata})
        distances.append(item.distance)

    governed_contexts, assessment = apply_retrieval_governance(
        question=payload.question,
        contexts=filtered,
        distances=distances if distances else None,
    )

    answer = build_rag_answer(
        question=payload.question,
        contexts=governed_contexts,
        retrieval_assessment={
            "status": assessment.status,
            "chunk_count": assessment.chunk_count,
            "trusted_chunk_count": assessment.trusted_chunk_count,
            "warnings": assessment.warnings,
            "value": assessment.confidence_value,
            "band": assessment.confidence_band,
            "reasoning": assessment.confidence_reasoning,
        },
    )
    return answer
