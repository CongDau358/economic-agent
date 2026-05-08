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


def save_processed(
    output_path: str,
    company: str,
    sector: str,
    source_type: str,
    chunks: List[str],
) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "company": company,
        "sector": sector,
        "source_type": source_type,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "chunks": chunks,
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)
    return payload
