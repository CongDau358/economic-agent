from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List

REQUIRED_STORAGE_FIELDS = (
    "company",
    "industry",
    "year",
    "source",
    "document_type",
    "chunk_id",
)

_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


def extract_year(metadata: Dict[str, str], text: str = "") -> str:
    for key in ("year", "publication_date", "reporting_period", "embedded_at", "ingested_at", "processed_at"):
        value = str(metadata.get(key, "")).strip()
        if not value:
            continue
        match = _YEAR_RE.search(value)
        if match:
            return match.group(1)
    match = _YEAR_RE.search(text[:800])
    if match:
        return match.group(1)
    return str(datetime.now(timezone.utc).year)


def normalize_storage_metadata(record: Dict[str, str]) -> Dict[str, str]:
    meta = {k: str(v) for k, v in record.items() if k != "text"}
    display_text = str(record.get("text", "")).strip()

    meta["company"] = str(meta.get("company", "")).strip() or "unknown"
    meta["industry"] = (
        str(meta.get("industry", "")).strip()
        or str(meta.get("sector", "")).strip()
        or "unknown"
    )
    meta["sector"] = str(meta.get("sector", "")).strip() or meta["industry"]
    meta["source"] = (
        str(meta.get("source", "")).strip()
        or str(meta.get("source_type", "")).strip()
        or "unknown"
    )
    meta["source_type"] = str(meta.get("source_type", "")).strip() or meta["source"]
    meta["document_type"] = (
        str(meta.get("document_type", "")).strip()
        or str(meta.get("data_type", "")).strip()
        or str(meta.get("content_type", "")).strip()
        or str(meta.get("chunk_type", "")).strip()
        or "general"
    )
    meta["year"] = str(meta.get("year", "")).strip() or extract_year(meta, display_text)
    meta["chunk_id"] = str(meta.get("chunk_id", "")).strip()
    meta["source_ref"] = str(meta.get("source_ref", "")).strip() or str(meta.get("raw_ref", "")).strip()
    meta["raw_ref"] = str(meta.get("raw_ref", "")).strip() or meta["source_ref"]
    meta["processed_file"] = str(meta.get("processed_file", "")).strip()
    meta["doc_id"] = str(meta.get("doc_id", "")).strip() or meta.get("processed_file", "")
    meta["stored_at"] = str(meta.get("stored_at", "")).strip() or datetime.now(timezone.utc).isoformat()

    from ...memory.lifecycle import apply_post_validation_lifecycle

    meta = apply_post_validation_lifecycle(meta)
    if display_text:
        meta["text"] = display_text
    return meta


def validate_storage_metadata(metadata: Dict[str, str]) -> List[str]:
    errors: List[str] = []
    for field in REQUIRED_STORAGE_FIELDS:
        value = str(metadata.get(field, "")).strip()
        if not value or value == "unknown" and field in {"company", "chunk_id"}:
            errors.append(f"missing storage metadata: {field}")
    return errors


def build_chroma_filter(
    *,
    company: str | None = None,
    industry: str | None = None,
    year: str | None = None,
    source: str | None = None,
    document_type: str | None = None,
) -> Dict[str, object] | None:
    clauses: List[Dict[str, str]] = []
    if company:
        clauses.append({"company": company})
    if industry:
        clauses.append({"industry": industry})
    if year:
        clauses.append({"year": year})
    if source:
        clauses.append({"source": source})
    if document_type:
        clauses.append({"document_type": document_type})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}
