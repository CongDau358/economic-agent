from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from .chunker import PdfChunk, chunk_sections, detect_financial_priorities
from .cleaner import clean_extracted_text
from .constants import DOCUMENT_TYPE_KEYWORDS, SUPPORTED_DOCUMENT_TYPES
from .extractor import extract_pdf, pages_to_raw_text
from .sections import detect_sections


@dataclass
class PdfPipelineResult:
    document_type: str
    extractor: str
    page_count: int
    section_count: int
    chunks: List[Dict[str, str]] = field(default_factory=list)
    sections_preview: List[str] = field(default_factory=list)
    financial_priorities_found: List[str] = field(default_factory=list)


def infer_document_type(text: str, filename: str = "") -> str:
    haystack = f"{filename}\n{text[:8000]}".lower()
    for doc_type, keywords in DOCUMENT_TYPE_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            return doc_type
    return "general_pdf"


def _chunks_to_records(
    chunks: List[PdfChunk],
    *,
    company: str,
    sector: str,
    raw_ref: str,
    processed_file: str,
    doc_id: str,
    document_type: str,
) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    for chunk in chunks:
        records.append(
            {
                "text": chunk.text,
                "chunk_id": chunk.chunk_id,
                "doc_id": doc_id,
                "company": company,
                "sector": sector,
                "source_type": "pdf",
                "document_type": document_type,
                "section_title": chunk.section_title,
                "page_ref": chunk.page_ref,
                "chunk_type": chunk.chunk_type,
                "financial_priorities": ",".join(chunk.financial_priorities) or "none",
                "priority_score": str(chunk.priority_score),
                "reliability": "high",
                "raw_ref": raw_ref,
                "processed_file": processed_file,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return records


def process_pdf_document(
    *,
    path: str,
    company: str,
    sector: str,
    raw_ref: str,
    processed_file: str,
    doc_id: str | None = None,
) -> PdfPipelineResult:
    """
    PDF → extract → clean → sections → chunk → records ready for embedding.
    """
    resolved_doc_id = doc_id or os.path.basename(path)
    extracted = extract_pdf(path)
    raw_text = pages_to_raw_text(extracted)
    if not raw_text.strip():
        return PdfPipelineResult(
            document_type="general_pdf",
            extractor=extracted.extractor,
            page_count=extracted.page_count,
            section_count=0,
        )

    cleaned = clean_extracted_text(raw_text)
    document_type = infer_document_type(cleaned, filename=os.path.basename(path))
    if document_type not in SUPPORTED_DOCUMENT_TYPES:
        document_type = "general_pdf"

    sections = detect_sections(cleaned)
    pdf_chunks = chunk_sections(sections, doc_id=resolved_doc_id)
    records = _chunks_to_records(
        pdf_chunks,
        company=company,
        sector=sector,
        raw_ref=raw_ref,
        processed_file=processed_file,
        doc_id=resolved_doc_id,
        document_type=document_type,
    )

    all_priorities = detect_financial_priorities(cleaned)

    return PdfPipelineResult(
        document_type=document_type,
        extractor=extracted.extractor,
        page_count=extracted.page_count,
        section_count=len(sections),
        chunks=records,
        sections_preview=[s.title for s in sections[:12]],
        financial_priorities_found=all_priorities,
    )
