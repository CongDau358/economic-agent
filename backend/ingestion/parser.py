from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, List

import requests
from pypdf import PdfReader


def read_pdf_text(path: str) -> str:
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def read_url_text(url: str) -> str:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.text[:10000]


def parse_source(source_type: str, text: str) -> List[str]:
    normalized = text.replace("\r\n", "\n")
    chunks = [c.strip() for c in normalized.split("\n\n") if c.strip()]
    if not chunks:
        chunks = [normalized.strip()] if normalized.strip() else []
    return chunks


def _normalize_chunk_entry(chunk: str | Dict[str, object]) -> Dict[str, object]:
    if isinstance(chunk, str):
        return {"text": chunk}
    return dict(chunk)


def save_processed(
    output_path: str,
    company: str,
    sector: str,
    source_type: str,
    chunks: List[str] | List[Dict[str, object]],
    *,
    pipeline: str | None = None,
    document_type: str | None = None,
    page_count: int | None = None,
    section_count: int | None = None,
    financial_priorities: List[str] | None = None,
) -> Dict[str, object]:
    normalized_chunks = [_normalize_chunk_entry(c) for c in chunks]
    payload: Dict[str, object] = {
        "company": company,
        "sector": sector,
        "source_type": source_type,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "chunks": normalized_chunks,
    }
    if pipeline:
        payload["pipeline"] = pipeline
    if document_type:
        payload["document_type"] = document_type
    if page_count is not None:
        payload["page_count"] = page_count
    if section_count is not None:
        payload["section_count"] = section_count
    if financial_priorities:
        payload["financial_priorities"] = financial_priorities
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)
    return payload
