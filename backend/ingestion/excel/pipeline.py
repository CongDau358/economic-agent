from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from .extractor import extract_workbook
from .metrics import map_metrics
from .normalizer import normalize_table
from .tagger import ExcelChunk, tag_chunks


@dataclass
class ExcelPipelineResult:
    file_format: str
    sheet_count: int
    table_count: int
    data_types: List[str] = field(default_factory=list)
    chunks: List[Dict[str, str]] = field(default_factory=list)
    financial_priorities_found: List[str] = field(default_factory=list)
    sheets_preview: List[str] = field(default_factory=list)


def _chunks_to_records(
    chunks: List[ExcelChunk],
    *,
    company: str,
    sector: str,
    raw_ref: str,
    processed_file: str,
    doc_id: str,
    file_format: str,
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
                "source_type": "excel",
                "file_format": file_format,
                "chunk_type": chunk.chunk_type,
                "sheet_name": chunk.sheet_name,
                "data_type": chunk.data_type,
                "row_range": chunk.row_range,
                "column_headers": chunk.column_headers,
                "date_alignment": chunk.date_alignment,
                "financial_priorities": ",".join(chunk.financial_priorities) or "none",
                "reliability": "high",
                "raw_ref": raw_ref,
                "processed_file": processed_file,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return records


def process_excel_document(
    *,
    path: str,
    company: str,
    sector: str,
    raw_ref: str,
    processed_file: str,
    doc_id: str | None = None,
) -> ExcelPipelineResult:
    resolved_doc_id = doc_id or os.path.basename(path)
    workbook = extract_workbook(path)
    all_chunks: List[ExcelChunk] = []
    data_types: List[str] = []
    priorities: set[str] = set()

    for table in workbook.tables:
        normalized = normalize_table(table)
        mapped = map_metrics(normalized)
        data_types.append(mapped.data_type)
        priorities.update(mapped.financial_priorities)
        all_chunks.extend(tag_chunks(mapped, doc_id=resolved_doc_id))

    records = _chunks_to_records(
        all_chunks,
        company=company,
        sector=sector,
        raw_ref=raw_ref,
        processed_file=processed_file,
        doc_id=resolved_doc_id,
        file_format=workbook.file_format,
    )

    return ExcelPipelineResult(
        file_format=workbook.file_format,
        sheet_count=workbook.sheet_count,
        table_count=len(workbook.tables),
        data_types=sorted(set(data_types)),
        chunks=records,
        financial_priorities_found=sorted(priorities),
        sheets_preview=[t.sheet_name for t in workbook.tables[:12]],
    )
