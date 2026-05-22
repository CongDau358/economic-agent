"""
backend/ingestion/ingestor.py  (TẠO MỚI)

Xử lý tất cả loại nguồn dữ liệu:
  - text   : văn bản thô
  - pdf    : file PDF (pdfplumber)
  - word   : file .docx (python-docx)  ← bản gốc THIẾU package này
  - excel  : .xlsx / .csv (openpyxl / pandas)
  - url    : crawl trang web (BeautifulSoup)

Output: chunk → embed → upsert vào ChromaDB
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

log = logging.getLogger("economic_agent.ingestion")


# ── Text chunker ──────────────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def _doc_id(company: str, source: str, idx: int) -> str:
    raw = f"{company}:{source}:{idx}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Extractors ────────────────────────────────────────────────────────────────

def _extract_text(text: str) -> str:
    return text.strip()


def _extract_pdf(file_bytes: bytes) -> str:
    import pdfplumber
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def _extract_word(file_bytes: bytes) -> str:
    from docx import Document  # python-docx
    doc = Document(BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_excel(file_bytes: bytes, file_name: str = "") -> str:
    if file_name.endswith(".csv"):
        import csv, io
        reader = csv.reader(io.StringIO(file_bytes.decode("utf-8", errors="ignore")))
        return "\n".join(", ".join(row) for row in reader)
    else:
        import openpyxl
        wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
        lines = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                line = " | ".join(str(c) for c in row if c is not None)
                if line:
                    lines.append(line)
        return "\n".join(lines)


def _extract_url(url: str) -> str:
    import requests
    from bs4 import BeautifulSoup
    resp = requests.get(url, timeout=15, headers={"User-Agent": "EconomicAgent/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n")


# ── Main ingest function ──────────────────────────────────────────────────────

def ingest(
    source_type: str,
    company: str,
    sector: str = "",
    text: str | None = None,
    url: str | None = None,
    file_bytes: bytes | None = None,
    file_name: str | None = None,
) -> dict[str, Any]:
    """
    Extract → chunk → embed → upsert to ChromaDB.
    Returns summary dict with chunk count.
    """
    from backend.config import get_settings
    settings = get_settings()

    # ── 1. Extract raw text ───────────────────────────────────────────────────
    source_label = source_type
    try:
        if source_type == "text":
            raw = _extract_text(text or "")
        elif source_type == "pdf":
            raw = _extract_pdf(file_bytes or b"")
            source_label = file_name or "pdf"
        elif source_type == "word":
            raw = _extract_word(file_bytes or b"")
            source_label = file_name or "docx"
        elif source_type == "excel":
            raw = _extract_excel(file_bytes or b"", file_name or "")
            source_label = file_name or "excel"
        elif source_type == "url":
            raw = _extract_url(url or "")
            source_label = url or "url"
        else:
            raise ValueError(f"Loại nguồn không hỗ trợ: {source_type}")
    except Exception as exc:
        log.error("extract.failed", extra={"source_type": source_type, "error": str(exc)})
        raise

    if not raw.strip():
        raise ValueError("Không trích xuất được nội dung từ nguồn dữ liệu")

    # ── 2. Chunk ──────────────────────────────────────────────────────────────
    chunks = _chunk_text(raw, settings.rag_chunk_size, settings.rag_chunk_overlap)
    log.info("ingest.chunks", extra={"company": company, "n": len(chunks), "source": source_label})

    # ── 3. Build metadata ────────────────────────────────────────────────────
    metadata_base: dict[str, Any] = {
        "company": company,
        "sector": sector,
        "source": source_label,
        "source_type": source_type,
        "ingested_at": datetime.utcnow().isoformat(),
    }

    # ── 4. Upsert to ChromaDB ─────────────────────────────────────────────────
    import chromadb
    from langchain_openai import OpenAIEmbeddings

    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    collection = client.get_or_create_collection(settings.chroma_collection_name)
    embedder = OpenAIEmbeddings(model=settings.openai_embedding_model)

    ids, texts, metadatas, embeddings = [], [], [], []
    for i, chunk in enumerate(chunks):
        doc_id = _doc_id(company, source_label, i)
        emb = embedder.embed_query(chunk)
        ids.append(doc_id)
        texts.append(chunk)
        metadatas.append({**metadata_base, "chunk_index": i})
        embeddings.append(emb)

    collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)

    # ── 5. Save raw to disk ───────────────────────────────────────────────────
    raw_dir = Path(settings.raw_data_dir) / company.replace(" ", "_")
    raw_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    (raw_dir / f"{source_type}_{ts}.txt").write_text(raw, encoding="utf-8")

    return {
        "company": company,
        "source": source_label,
        "chunks_upserted": len(chunks),
        "collection": settings.chroma_collection_name,
    }