from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence

from ..rag.storage.metadata import normalize_storage_metadata, validate_storage_metadata

MIN_CHUNK_CHARS = 50
MIN_EXTRACTION_CHARS = 80
MIN_PRINTABLE_RATIO = 0.55
GARBAGE_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

BASE_REQUIRED = ("company", "sector", "source_type", "raw_ref", "processed_file")
CORE_REQUIRED = ("text", "chunk_id", "doc_id", *BASE_REQUIRED)

SOURCE_REQUIRED: Dict[str, tuple[str, ...]] = {
    "pdf": ("chunk_type",),
    "excel": ("sheet_name", "chunk_type", "row_range"),
    "news": ("publisher", "publication_date", "topic", "industry", "sentiment"),
    "text": (),
}


@dataclass
class ValidationResult:
    valid: bool
    records: List[Dict[str, str]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    valid_chunk_count: int = 0
    duplicate_count: int = 0
    rejected_chunk_count: int = 0


@dataclass
class ExtractionStats:
    char_count: int = 0
    page_count: int | None = None
    table_count: int | None = None
    sheet_count: int | None = None


def _text_fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())[:2000]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\n\t")
    return printable / len(text)


def validate_document_file(path: str, source_type: str) -> List[str]:
    errors: List[str] = []
    file_path = Path(path)
    if not file_path.exists():
        return [f"corrupted document: file not found ({path})"]
    if file_path.stat().st_size == 0:
        return [f"corrupted document: empty file ({path})"]

    suffix = file_path.suffix.lower()
    try:
        if source_type == "pdf" or suffix == ".pdf":
            header = file_path.read_bytes()[:8]
            if not header.startswith(b"%PDF"):
                errors.append("corrupted document: invalid PDF header")
        elif source_type == "excel" and suffix in {".xlsx", ".xlsm"}:
            if not zipfile.is_zipfile(file_path):
                errors.append("corrupted document: invalid Excel archive")
        elif suffix == ".csv":
            file_path.read_text(encoding="utf-8-sig")[:1]
    except OSError as exc:
        errors.append(f"corrupted document: cannot read file ({exc})")
    except UnicodeDecodeError:
        errors.append("corrupted document: CSV encoding error")

    return errors


def validate_extraction_quality(
    *,
    source_type: str,
    stats: ExtractionStats | None = None,
    sample_text: str = "",
) -> List[str]:
    errors: List[str] = []
    stats = stats or ExtractionStats()
    char_count = stats.char_count or len(sample_text.strip())

    if char_count < MIN_EXTRACTION_CHARS:
        errors.append(
            f"extraction quality too low: only {char_count} characters extracted"
        )

    if sample_text and GARBAGE_RE.search(sample_text):
        errors.append("extraction quality too low: binary garbage detected in text")

    if sample_text and _printable_ratio(sample_text) < MIN_PRINTABLE_RATIO:
        errors.append("extraction quality too low: low printable character ratio")

    if source_type == "pdf" and stats.page_count == 0:
        errors.append("extraction quality too low: zero pages extracted")

    if source_type == "excel" and stats.table_count == 0 and stats.sheet_count == 0:
        errors.append("extraction quality too low: no tables or sheets extracted")

    return errors


def _ensure_chunk_ids(records: List[Dict[str, str]], doc_id: str) -> List[Dict[str, str]]:
    enriched: List[Dict[str, str]] = []
    for idx, record in enumerate(records):
        row = dict(record)
        text = str(row.get("text", "")).strip()
        if not row.get("chunk_id"):
            row["chunk_id"] = _text_fingerprint(f"{doc_id}:{idx}:{text[:120]}")[:16]
        if not row.get("doc_id"):
            row["doc_id"] = doc_id
        row = normalize_storage_metadata(row)
        enriched.append(row)
    return enriched


def validate_chunk_record(
    record: Dict[str, str],
    source_type: str,
) -> List[str]:
    errors: List[str] = []
    text = str(record.get("text", "")).strip()
    if not text:
        errors.append("empty chunk: missing text")
    elif len(text) < MIN_CHUNK_CHARS:
        errors.append(f"empty chunk: text shorter than {MIN_CHUNK_CHARS} characters")

    for key in CORE_REQUIRED:
        value = str(record.get(key, "")).strip()
        if not value:
            errors.append(f"missing metadata: {key}")

    for key in SOURCE_REQUIRED.get(source_type, ()):
        value = str(record.get(key, "")).strip()
        if not value or value == "unknown":
            errors.append(f"missing metadata: {key}")

    errors.extend(validate_storage_metadata(record))
    return errors


def detect_duplicates(records: Sequence[Dict[str, str]]) -> tuple[List[Dict[str, str]], int]:
    seen_ids: set[str] = set()
    seen_text: set[str] = set()
    unique: List[Dict[str, str]] = []
    duplicates = 0

    for record in records:
        chunk_id = str(record.get("chunk_id", "")).strip()
        fingerprint = _text_fingerprint(str(record.get("text", "")))
        if chunk_id in seen_ids or fingerprint in seen_text:
            duplicates += 1
            continue
        seen_ids.add(chunk_id)
        seen_text.add(fingerprint)
        unique.append(record)

    return unique, duplicates


def validate_ingestion(
    *,
    source_type: str,
    records: List[Dict[str, str]],
    doc_id: str,
    file_path: str | None = None,
    extraction_stats: ExtractionStats | None = None,
    sample_text: str = "",
) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    if file_path:
        errors.extend(validate_document_file(file_path, source_type))

    errors.extend(
        validate_extraction_quality(
            source_type=source_type,
            stats=extraction_stats,
            sample_text=sample_text or " ".join(str(r.get("text", "")) for r in records[:3]),
        )
    )

    if not records:
        errors.append("no chunks produced for ingestion")
        return ValidationResult(
            valid=False,
            errors=errors,
            warnings=warnings,
            rejected_chunk_count=0,
        )

    enriched = _ensure_chunk_ids(records, doc_id)
    valid_records: List[Dict[str, str]] = []
    rejected = 0

    for idx, record in enumerate(enriched):
        chunk_errors = validate_chunk_record(record, source_type)
        if chunk_errors:
            rejected += 1
            for msg in chunk_errors:
                errors.append(f"chunk {idx}: {msg}")
            continue
        valid_records.append(record)

    deduped, duplicate_count = detect_duplicates(valid_records)
    if duplicate_count:
        warnings.append(f"duplicate detection removed {duplicate_count} chunk(s)")

    if not deduped:
        errors.append("no valid chunks after validation")

    is_valid = len(errors) == 0 and len(deduped) > 0
    return ValidationResult(
        valid=is_valid,
        records=deduped if is_valid else [],
        errors=errors,
        warnings=warnings,
        valid_chunk_count=len(deduped),
        duplicate_count=duplicate_count,
        rejected_chunk_count=rejected,
    )
