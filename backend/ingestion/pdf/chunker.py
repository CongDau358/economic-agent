from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..chunking.strategy import ChunkType, build_semantic_chunks
from .constants import FINANCIAL_PRIORITIES
from .sections import DocumentSection


@dataclass
class PdfChunk:
    text: str
    chunk_id: str
    section_title: str
    page_ref: str
    chunk_type: str = ChunkType.GENERAL.value
    financial_priorities: List[str] = field(default_factory=list)
    priority_score: int = 0


def detect_financial_priorities(text: str) -> List[str]:
    lower = text.lower()
    found: List[str] = []
    for category, keywords in FINANCIAL_PRIORITIES.items():
        if any(kw in lower for kw in keywords):
            found.append(category)
    return found


def _priority_score(priorities: List[str]) -> int:
    weights = {"revenue": 5, "profit": 5, "debt": 4, "cash_flow": 4, "growth": 3}
    return sum(weights.get(p, 1) for p in priorities)


def _page_ref(section: DocumentSection) -> str:
    if section.page_start and section.page_end and section.page_start != section.page_end:
        return f"{section.page_start}-{section.page_end}"
    if section.page_start:
        return str(section.page_start)
    return "unknown"


def chunk_sections(
    sections: List[DocumentSection],
    *,
    doc_id: str,
) -> List[PdfChunk]:
    chunks: List[PdfChunk] = []
    index = 0

    for section in sections:
        header = f"[Section: {section.title} | Pages: {_page_ref(section)}]"
        semantic = build_semantic_chunks(
            doc_id=doc_id,
            body=section.body,
            profile_name="financial_report",
            context_header=header,
            source_hint=section.title,
            start_index=index,
        )
        index += len(semantic)

        for item in semantic:
            priorities = detect_financial_priorities(item.text) or item.financial_priorities
            chunks.append(
                PdfChunk(
                    text=item.text,
                    chunk_id=item.chunk_id,
                    section_title=section.title,
                    page_ref=_page_ref(section),
                    chunk_type=item.chunk_type.value,
                    financial_priorities=priorities,
                    priority_score=_priority_score(priorities),
                )
            )

    chunks.sort(key=lambda c: c.priority_score, reverse=True)
    return chunks
