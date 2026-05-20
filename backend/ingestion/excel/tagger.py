from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..chunking.strategy import ChunkType, make_chunk_id
from .constants import MAX_ROWS_PER_CHUNK
from .metrics import MappedTable


@dataclass
class ExcelChunk:
    text: str
    chunk_id: str
    chunk_type: str
    sheet_name: str
    data_type: str
    row_range: str
    column_headers: str
    date_alignment: str
    financial_priorities: List[str] = field(default_factory=list)


def _header_line(table: MappedTable) -> str:
    cols = sorted(table.metric_columns.values())
    if table.date_column:
        cols = ["date"] + cols
    return " | ".join(cols)


def _format_row(table: MappedTable, row) -> str:
    parts: List[str] = []
    if table.date_column and row.date_value:
        parts.append(f"date={row.date_value}")
    for canon, value in sorted(row.metrics.items()):
        parts.append(f"{canon}={value}")
    return " | ".join(parts)


def _date_alignment(table: MappedTable, rows) -> str:
    dates = [r.date_value for r in rows if r.date_value]
    if not dates:
        return "none"
    if len(set(dates)) == len(dates):
        return "unique"
    return "aligned"


def tag_chunks(table: MappedTable, *, doc_id: str) -> List[ExcelChunk]:
    if not table.rows:
        return []

    chunks: List[ExcelChunk] = []
    header = _header_line(table)

    for batch_start in range(0, len(table.rows), MAX_ROWS_PER_CHUNK):
        batch = table.rows[batch_start : batch_start + MAX_ROWS_PER_CHUNK]
        row_start = batch[0].row_index
        row_end = batch[-1].row_index
        lines = [
            f"[SHEET: {table.sheet_name} | Type: {table.data_type} | Rows: {row_start}-{row_end}]",
            f"[COLUMNS: {header}]",
            "[TABLE]",
            header,
        ]
        for row in batch:
            lines.append(_format_row(table, row))
        lines.append("[/TABLE]")
        text = "\n".join(lines)

        chunk_id = make_chunk_id(doc_id, table.sheet_name, str(row_start), str(row_end))
        chunk_type = (
            ChunkType.FINANCIAL_METRIC.value
            if table.financial_priorities
            else ChunkType.FINANCIAL_TABLE.value
        )

        chunks.append(
            ExcelChunk(
                text=text,
                chunk_id=chunk_id,
                chunk_type=chunk_type,
                sheet_name=table.sheet_name,
                data_type=table.data_type,
                row_range=f"{row_start}-{row_end}",
                column_headers=header,
                date_alignment=_date_alignment(table, batch),
                financial_priorities=table.financial_priorities,
            )
        )

    return chunks
