from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Sequence

_TABLE_BLOCK_RE = re.compile(r"\[TABLE\].*?\[/TABLE\]", re.DOTALL | re.IGNORECASE)


class ChunkType(str, Enum):
    FINANCIAL_METRIC = "financial_metric"
    FINANCIAL_TABLE = "financial_table"
    NEWS_EVENT = "news_event"
    GENERAL = "general"


@dataclass(frozen=True)
class ChunkProfile:
    name: str
    min_chars: int
    target_chars: int
    max_chars: int
    overlap_chars: int


PROFILES: dict[str, ChunkProfile] = {
    "financial_report": ChunkProfile("financial_report", 900, 2000, 2800, 400),
    "news": ChunkProfile("news", 400, 900, 1400, 160),
    "excel_table": ChunkProfile("excel_table", 200, 1200, 2400, 0),
}

FINANCIAL_METRIC_HINTS = (
    "revenue",
    "profit",
    "net income",
    "earnings",
    "cash flow",
    "balance sheet",
    "income statement",
    "doanh thu",
    "lợi nhuận",
)

NEWS_EVENT_HINTS = (
    "policy",
    "market",
    "regulation",
    "trade",
    "fed",
    "central bank",
    "acquisition",
    "merger",
    "index",
    "chính sách",
    "thị trường",
)


@dataclass
class SemanticChunk:
    text: str
    chunk_id: str
    chunk_type: ChunkType
    chunk_index: int
    context_header: str = ""
    financial_priorities: List[str] = field(default_factory=list)


def make_chunk_id(doc_id: str, *parts: str) -> str:
    key = ":".join([doc_id, *parts])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def infer_chunk_type(text: str, *, source_hint: str = "") -> ChunkType:
    lower = f"{text}\n{source_hint}".lower()
    if "[TABLE]" in lower or "[/TABLE]" in lower:
        return ChunkType.FINANCIAL_TABLE
    if "[news" in lower and any(h in lower for h in NEWS_EVENT_HINTS):
        return ChunkType.NEWS_EVENT
    if any(h in lower for h in FINANCIAL_METRIC_HINTS):
        return ChunkType.FINANCIAL_METRIC
    if "[news" in lower:
        return ChunkType.NEWS_EVENT
    return ChunkType.GENERAL


def _extract_table_blocks(text: str) -> List[tuple[str, bool]]:
    segments: List[tuple[str, bool]] = []
    last = 0
    for match in _TABLE_BLOCK_RE.finditer(text):
        if match.start() > last:
            segments.append((text[last : match.start()], False))
        segments.append((match.group(0), True))
        last = match.end()
    if last < len(text):
        segments.append((text[last:], False))
    if not segments:
        segments.append((text, False))
    return segments


def _split_prose(prose: str, profile: ChunkProfile) -> List[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\n+", prose) if p.strip()]
    if not paragraphs:
        return []

    parts: List[str] = []
    current = ""

    for para in paragraphs:
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= profile.max_chars:
            current = candidate
            continue
        if current:
            parts.append(current)
        if len(para) <= profile.max_chars:
            current = para
            continue
        start = 0
        while start < len(para):
            end = min(start + profile.max_chars, len(para))
            slice_text = para[start:end].strip()
            if slice_text:
                parts.append(slice_text)
            if end >= len(para):
                break
            start = max(end - profile.overlap_chars, start + 1)
        current = ""

    if current:
        parts.append(current)
    return parts


def split_semantic_text(text: str, profile: ChunkProfile) -> List[str]:
    segments = _extract_table_blocks(text)
    output: List[str] = []

    for segment, is_table in segments:
        segment = segment.strip()
        if not segment:
            continue
        if is_table:
            if len(segment) <= profile.max_chars:
                output.append(segment)
            else:
                output.append(segment[: profile.max_chars])
            continue
        output.extend(_split_prose(segment, profile))

    return merge_chunks(output, profile)


def merge_chunks(parts: Sequence[str], profile: ChunkProfile) -> List[str]:
    if not parts:
        return []

    merged: List[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if merged and len(part) < profile.min_chars // 2:
            candidate = f"{merged[-1]}\n\n{part}".strip()
            if len(candidate) <= profile.max_chars:
                merged[-1] = candidate
                continue
        if merged and len(merged[-1]) < profile.min_chars:
            candidate = f"{merged[-1]}\n\n{part}".strip()
            if len(candidate) <= profile.max_chars:
                merged[-1] = candidate
                continue
        merged.append(part)

    return [m for m in merged if len(m) >= 40 or len(merged) == 1]


def build_semantic_chunks(
    *,
    doc_id: str,
    body: str,
    profile_name: str,
    context_header: str,
    source_hint: str = "",
    start_index: int = 0,
) -> List[SemanticChunk]:
    profile = PROFILES[profile_name]
    parts = split_semantic_text(body, profile)
    chunks: List[SemanticChunk] = []

    for idx, part in enumerate(parts):
        full_text = f"{context_header}\n\n{part}".strip() if context_header else part
        chunk_type = infer_chunk_type(full_text, source_hint=source_hint)
        chunk_id = make_chunk_id(doc_id, profile_name, str(start_index + idx), part[:80])
        priorities: List[str] = []
        lower = full_text.lower()
        for label in ("revenue", "profit", "debt", "cash_flow", "growth"):
            if label.replace("_", " ") in lower or label in lower:
                priorities.append(label)

        chunks.append(
            SemanticChunk(
                text=full_text,
                chunk_id=chunk_id,
                chunk_type=chunk_type,
                chunk_index=start_index + idx,
                context_header=context_header,
                financial_priorities=priorities,
            )
        )

    return chunks
