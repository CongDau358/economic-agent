from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from .constants import HEADING_PATTERNS, SECTION_TITLE_HINTS


@dataclass
class DocumentSection:
    title: str
    body: str
    page_start: int | None = None
    page_end: int | None = None
    is_heading: bool = True


_PAGE_RE = re.compile(r"^\[PAGE\s+(\d+)\]\s*$", re.IGNORECASE)
_HEADING_RES = [re.compile(p, re.IGNORECASE) for p in HEADING_PATTERNS]


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return False
    if stripped.startswith("[TABLE]") or stripped.startswith("[/TABLE]"):
        return False
    if any(rx.match(stripped) for rx in _HEADING_RES):
        return True
    lower = stripped.lower()
    if any(hint in lower for hint in SECTION_TITLE_HINTS) and len(stripped) < 80:
        return True
    if stripped.isupper() and len(stripped.split()) <= 12:
        return True
    return False


def detect_sections(cleaned_text: str) -> List[DocumentSection]:
    """Split cleaned PDF text into heading-attached sections."""
    if not cleaned_text.strip():
        return []

    sections: List[DocumentSection] = []
    current_title = "Document"
    current_lines: List[str] = []
    current_page: int | None = None
    page_start: int | None = None

    def flush() -> None:
        nonlocal current_lines, page_start
        body = "\n".join(current_lines).strip()
        if body:
            sections.append(
                DocumentSection(
                    title=current_title,
                    body=body,
                    page_start=page_start,
                    page_end=current_page,
                )
            )
        current_lines = []

    for line in cleaned_text.split("\n"):
        page_match = _PAGE_RE.match(line.strip())
        if page_match:
            current_page = int(page_match.group(1))
            if page_start is None:
                page_start = current_page
            current_lines.append(line.strip())
            continue

        if _looks_like_heading(line):
            flush()
            current_title = line.strip().rstrip(":")
            page_start = current_page
            current_lines.append(f"## {current_title}")
            continue

        current_lines.append(line)

    flush()

    if not sections:
        return [
            DocumentSection(
                title="Document",
                body=cleaned_text.strip(),
                page_start=None,
                page_end=None,
                is_heading=False,
            )
        ]
    return sections
