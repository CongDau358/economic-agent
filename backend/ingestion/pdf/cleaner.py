from __future__ import annotations

import re


_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_BULLET_NOISE = re.compile(r"\n(?:•|·|▪)\s*")
_PAGE_MARKER = re.compile(r"\[PAGE\s+(\d+)\]", re.IGNORECASE)
_TABLE_BLOCK = re.compile(r"\[TABLE\](.*?)\[/TABLE\]", re.DOTALL | re.IGNORECASE)


def _normalize_table_block(match: re.Match[str]) -> str:
    body = match.group(1)
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if not lines:
        return ""
    return "[TABLE]\n" + "\n".join(lines) + "\n[/TABLE]"


def clean_extracted_text(raw: str) -> str:
    """Normalize PDF text while preserving headings, tables, and page markers."""
    if not raw.strip():
        return ""

    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = _BULLET_NOISE.sub("\n", text)

    # Preserve table blocks through whitespace normalization
    tables: list[str] = []

    def _stash_table(m: re.Match[str]) -> str:
        tables.append(_normalize_table_block(m))
        return f"__TABLE_{len(tables) - 1}__"

    text = _TABLE_BLOCK.sub(_stash_table, text)

    lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if _PAGE_MARKER.match(stripped):
            lines.append(stripped)
            continue
        lines.append(_MULTI_SPACE.sub(" ", stripped))

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    for idx, table in enumerate(tables):
        text = text.replace(f"__TABLE_{idx}__", table)

    return text.strip()
