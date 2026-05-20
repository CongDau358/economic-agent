from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

@dataclass
class ExtractedPage:
    page_number: int
    text: str
    tables: List[str] = field(default_factory=list)


@dataclass
class ExtractedDocument:
    pages: List[ExtractedPage]
    page_count: int
    extractor: str


def _format_table(rows: List[List[str | None]]) -> str:
    if not rows:
        return ""
    lines: List[str] = []
    for row in rows:
        cells = [str(c or "").strip() for c in row]
        if any(cells):
            lines.append(" | ".join(cells))
    if not lines:
        return ""
    return "[TABLE]\n" + "\n".join(lines) + "\n[/TABLE]"


def _extract_with_pdfplumber(path: str) -> ExtractedDocument | None:
    try:
        import pdfplumber  # noqa: PLC0415
    except ImportError:
        return None

    pages: List[ExtractedPage] = []
    with pdfplumber.open(path) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            tables: List[str] = []
            try:
                raw_tables = page.extract_tables() or []
                for table in raw_tables:
                    formatted = _format_table(table)
                    if formatted:
                        tables.append(formatted)
            except Exception:
                pass
            pages.append(ExtractedPage(page_number=idx, text=text, tables=tables))
    return ExtractedDocument(pages=pages, page_count=len(pages), extractor="pdfplumber")


def _extract_with_pypdf(path: str) -> ExtractedDocument:
    from pypdf import PdfReader  # noqa: PLC0415

    reader = PdfReader(path)
    pages: List[ExtractedPage] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append(ExtractedPage(page_number=idx, text=text, tables=[]))
    return ExtractedDocument(pages=pages, page_count=len(pages), extractor="pypdf")


def extract_pdf(path: str) -> ExtractedDocument:
    """Extract text and tables from PDF; prefers pdfplumber when available."""
    doc = _extract_with_pdfplumber(path)
    if doc is not None and any(p.text or p.tables for p in doc.pages):
        return doc
    return _extract_with_pypdf(path)


def pages_to_raw_text(document: ExtractedDocument) -> str:
    blocks: List[str] = []
    for page in document.pages:
        page_parts: List[str] = [f"[PAGE {page.page_number}]"]
        if page.text:
            page_parts.append(page.text)
        for table in page.tables:
            page_parts.append(table)
        if len(page_parts) > 1:
            blocks.append("\n".join(page_parts))
    return "\n\n".join(blocks).strip()
