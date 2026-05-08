from __future__ import annotations
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .ingestion.parser import parse_source, read_pdf_text, read_url_text, save_processed
from .rag.vector_store import VectorStoreService
from .services.agent_service import build_rag_answer
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
    if source_type not in {"pdf", "news", "text"}:
        raise HTTPException(status_code=400, detail="source_type must be one of: pdf, news, text")

    extracted_text = ""
    raw_ref = ""

    if source_type == "pdf":
        if file is None:
            raise HTTPException(status_code=400, detail="file is required for pdf source_type")
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="uploaded file must be a PDF")
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        raw_path = RAW_DIR / f"{timestamp}_{file.filename}"
        with raw_path.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)
        extracted_text = read_pdf_text(str(raw_path))
        raw_ref = str(raw_path)
    elif source_type == "news":
        if not url:
            raise HTTPException(status_code=400, detail="url is required for news source_type")
        extracted_text = read_url_text(url)
        raw_ref = url
    else:
        if not text:
            raise HTTPException(status_code=400, detail="text is required for text source_type")
        extracted_text = text
        raw_ref = "inline_text"

    chunks = parse_source(source_type=source_type, text=extracted_text)
    if not chunks:
        raise HTTPException(status_code=400, detail="No extractable content found")

    processed_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{company.replace(' ', '_')}.json"
    processed_path = PROCESSED_DIR / processed_name
    processed = save_processed(
        output_path=str(processed_path),
        company=company,
        sector=sector,
        source_type=source_type,
        chunks=chunks,
    )

    vector_store.add_documents(
        [
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
    )

    return {
        "message": "data ingested",
        "company": company,
        "sector": sector,
        "source_type": source_type,
        "raw_ref": raw_ref,
        "processed_file": processed_name,
        "chunk_count": len(chunks),
        "processed_preview": processed["chunks"][:2],
    }


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
    retrieved = vector_store.query(payload.question, top_k=payload.top_k)
    filtered = []
    for item in retrieved:
        metadata = item.metadata
        if payload.company and metadata.get("company") != payload.company:
            continue
        if payload.sector and metadata.get("sector") != payload.sector:
            continue
        filtered.append({"text": item.text, **metadata})

    answer = build_rag_answer(question=payload.question, contexts=filtered)
    return answer
