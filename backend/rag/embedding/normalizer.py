from __future__ import annotations

import re
from typing import Dict

_WS = re.compile(r"[ \t]+")
_MULTI_NL = re.compile(r"\n{3,}")
_NUMERIC = re.compile(
    r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d{4,}|\d+)(?:\s*(%|bps|bn|billion|million|m|b|k|usd|vnd))?",
    re.IGNORECASE,
)


def _context_prefix(metadata: Dict[str, str]) -> str:
    parts: list[str] = []
    for key, label in (
        ("company", "company"),
        ("sector", "sector"),
        ("industry", "industry"),
        ("chunk_type", "chunk_type"),
        ("topic", "topic"),
        ("financial_priorities", "metrics"),
        ("sentiment", "sentiment"),
        ("data_type", "data_type"),
        ("document_type", "document_type"),
    ):
        value = str(metadata.get(key, "")).strip()
        if value and value != "none":
            parts.append(f"{label}:{value}")
    return " | ".join(parts)


def _preserve_numerics(text: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        num = match.group(1).replace(",", "")
        unit = (match.group(2) or "").lower()
        return f" {num}{unit} " if unit else f" {num} "

    return _NUMERIC.sub(_repl, text)


def normalize_chunk_text(text: str, metadata: Dict[str, str] | None = None) -> str:
    meta = metadata or {}
    raw = text.replace("\r\n", "\n").replace("\r", "\n")
    raw = _MULTI_NL.sub("\n\n", raw)
    lines = [_WS.sub(" ", ln.strip()) for ln in raw.split("\n")]
    body = "\n".join(ln for ln in lines if ln)
    body = _preserve_numerics(body)
    body = _WS.sub(" ", body).strip()

    prefix = _context_prefix(meta)
    if prefix:
        return f"{prefix}\n{body}".strip()
    return body


def normalize_query_text(query: str) -> str:
    q = query.replace("\r\n", "\n").strip()
    q = _preserve_numerics(q)
    q = _WS.sub(" ", q)
    return q.strip()
